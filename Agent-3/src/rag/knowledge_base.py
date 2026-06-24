"""知识库管理 -- RAG 管线的统一对外接口.

Usage:
    kb = KnowledgeBase(kb_name="hr_kb", docs_dir="data/hr/")
    kb.build_index()              # 首次构建(或文档变更后)
    # ... 重启后 ...
    kb = KnowledgeBase(kb_name="hr_kb", docs_dir="data/hr/")
    kb.load_index()               # 加载已有索引
    results = kb.query("年假还剩几天", top_k=5)
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import chromadb
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

from src.config import config
from src.rag.chunker import split_documents
from src.rag.embedder import Embedder
from src.rag.loader import load_documents
from src.rag.retriever import (
    build_bm25,
    rrf_fusion,
    search_bm25,
    search_vector,
)

# Chroma 数据持久化根目录(对齐 .gitignore 中的 chroma_db/)
CHROMA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")


class KnowledgeBase:
    """知识库管理类.

    Attributes:
        kb_name: 知识库名称(如 "hr_kb").
        docs_dir: 原始文档目录.
        dimension: Embedding 维度(768).
    """

    def __init__(
        self,
        kb_name: str,
        docs_dir: str,
        chunk_size: int = 500,
        chunk_overlap: int = 80,
        embedder: Embedder | None = None,
    ) -> None:
        self.kb_name = kb_name
        self.docs_dir = docs_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._embedder: Embedder | None = embedder  # 外部注入共享
        self._chunks_metadata: list[dict[str, Any]] = []
        self._bm25: Any = None
        self._collection: Any = None
        self._client: Any = None
        self._rewriter: Any = None   # LLM client for query rewriting
        self._rewriter_model: str = "deepseek-v4-flash"
        self._reranker: Any = None  # Reranker instance (lazy-loaded)
        self._built = False
        self._cache: dict[str, tuple[float, list[dict]]] = {}  # key → (timestamp, results)
        self._cache_maxsize = 256
        self._last_query_meta: dict[str, Any] = {}  # 最近一次查询的元数据(供 trace 用)

    # ── 公共接口 ──────────────────────────────────────────────

    def build_index(self) -> None:
        """首次构建索引:加载文档 → 分块 → 向量化 → 存 Chroma + 构建 BM25.

        会覆盖已有索引.
        """
        # 1. 加载
        docs = load_documents(self.docs_dir)
        if not docs:
            raise ValueError(f"目录 {self.docs_dir} 下未找到文档")

        # 2. 分块
        chunks = split_documents(docs, self.chunk_size, self.chunk_overlap)
        if not chunks:
            raise ValueError("分块结果为空")

        # 3. 向量化
        embedder = self._get_embedder()
        chunk_texts = [c["content"] for c in chunks]  # type: ignore[arg-type]
        embeddings = embedder.embed_documents(chunk_texts)

        # 校验 embedding 维度与模型输出一致(换模型时提前发现不匹配)
        actual_dim = len(embeddings[0]) if embeddings else 0
        assert actual_dim == embedder.dimension, (
            f"Embedding dimension mismatch: model outputs {actual_dim}, "
            f"expected {embedder.dimension}. Did the model change?"
        )

        # 4. 存 Chroma
        client = self._get_chroma_client()
        collection_name = _sanitize_name(self.kb_name)

        # 删除旧 collection(如果存在)
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        collection = client.create_collection(
            name=collection_name,
            metadata={"kb_name": self.kb_name, "docs_dir": self.docs_dir},
        )

        ids = [f"{c['source']}_{c['chunk_index']}" for c in chunks]
        metadatas = [
            {
                "source": c["source"],
                "title": c.get("title", c["source"]),
                "chunk_index": c["chunk_index"],
            }
            for c in chunks
        ]

        collection.add(
            ids=ids,
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # 5. 构建 BM25 索引
        self._bm25 = build_bm25(chunk_texts)
        self._chunks_metadata = [
            {"content": t, **m} for t, m in zip(chunk_texts, metadatas)
        ]

        # 6. 存储元数据(供 load_index 重建 BM25)
        self._save_metadata()

        self._collection = collection
        self._cache.clear()
        self._built = True

    def load_index(self) -> None:
        """加载已有索引(不需要重新构建)."""
        client = self._get_chroma_client()
        collection_name = _sanitize_name(self.kb_name)

        try:
            self._collection = client.get_collection(collection_name)
        except Exception:
            raise FileNotFoundError(
                f"知识库 '{self.kb_name}' 的索引不存在,请先调用 build_index()"
            )

        # 从 Chroma 读取所有 chunks 重建 BM25
        all_data = self._collection.get(include=["documents", "metadatas"])

        chunk_texts: list[str] = all_data.get("documents") or []
        metadatas: list[dict] = all_data.get("metadatas") or []

        self._chunks_metadata = [
            {"content": t, **m} for t, m in zip(chunk_texts, metadatas)
        ]

        # 尝试从磁盘加载元数据(优先于从 Chroma 重建)
        meta_path = self._metadata_path()
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if len(saved) == len(chunk_texts):
                    self._chunks_metadata = saved

        self._bm25 = build_bm25(chunk_texts)
        self._built = True

    def set_rewriter(self, client: Any, model: str = "deepseek-v4-flash") -> None:
        """设置查询改写器(需要 LLM 客户端).

        Args:
            client: OpenAI 兼容客户端.
            model: 模型名称.
        """
        self._rewriter = client
        self._rewriter_model = model

    def set_reranker(self, reranker: Any) -> None:
        """设置重排序器(Reranker 实例).

        Args:
            reranker: src.rag.reranker.Reranker 实例.
        """
        self._reranker = reranker

    def watch(self) -> None:
        """启动文件监听(后台线程),docs_dir 文件变化时自动重建索引.

        监听 .md / .txt / .pdf / .docx 的增/删/改,
        防抖 2 秒合并连续变化为一次重建.

        Usage:
            kb.watch()
            # 程序继续运行,文件变化自动触发 build_index()
            kb.stop_watch()  # 停止监听
        """
        if hasattr(self, "_observer") and self._observer is not None:
            logger.warning("Already watching %s", self.docs_dir)
            return

        kb = self  # 闭包引用

        class _RebuildHandler(FileSystemEventHandler):
            def __init__(self):
                super().__init__()
                self._timer: threading.Timer | None = None
                self._lock = threading.Lock()

            def _trigger(self, event_path: str):
                with self._lock:
                    if self._timer:
                        self._timer.cancel()
                    logger.info("File changed: %s -- will rebuild in 2s", event_path)
                    self._timer = threading.Timer(2.0, self._rebuild)
                    self._timer.daemon = True
                    self._timer.start()

            def _rebuild(self):
                try:
                    logger.info("Rebuilding index for %s ...", kb.docs_dir)
                    t0 = time.time()
                    kb.build_index()
                    logger.info("Rebuild done in %.1fs", time.time() - t0)
                except Exception as e:
                    logger.error("Rebuild failed: %s", e)

            def on_created(self, event):
                if not event.is_directory:
                    self._trigger(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    self._trigger(event.src_path)

            def on_deleted(self, event):
                if not event.is_directory:
                    self._trigger(event.src_path)

        event_handler = _RebuildHandler()
        self._observer = Observer()
        self._observer.schedule(event_handler, self.docs_dir, recursive=False)
        self._observer.daemon = True
        self._observer.start()
        logger.info("Watching %s for changes ...", self.docs_dir)

    def stop_watch(self) -> None:
        """停止文件监听."""
        if hasattr(self, "_observer") and self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Stopped watching %s", self.docs_dir)

    # FAQ 快速匹配表 -- 高频问题直接返回,不经过向量检索
    _FAQ_PATTERNS: dict[str, str] = {
        "年假": "年假", "病假": "病假", "事假": "事假",
        "请假": "请假", "假期": "假期", "考勤": "考勤",
        "打卡": "打卡", "迟到": "迟到", "加班": "加班",
        "报修": "报修", "网络": "网络", "vpn": "VPN",
        "合同": "合同", "保密": "保密", "合规": "合规",
        "报销": "报销", "预算": "预算", "出差": "出差",
    }

    def query(self, query: str, top_k: int = 10, rewrite: bool = True) -> list[dict[str, Any]]:
        """检索最相关的文档片段.

        FAQ 优先:高频简单问题直接 BM25 匹配,跳过 LLM 改写和向量检索.

        Args:
            query: 检索查询.
            top_k: 返回条数.
            rewrite: 是否启用查询改写(需要已设置 rewriter).

        Returns:
            [{"content": "...", "source": "年假制度.md", "section": "...", "score": 0.94}, ...]
        """
        if not self._built:
            raise RuntimeError("请先调用 build_index() 或 load_index()")

        # ── 缓存检查 ────────────────────────────────────────
        cache_key = f"{query}::top_k={top_k}::rewrite={rewrite}"
        cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        now = time.time()
        cache_hit = False
        cached = self._cache.get(cache_key_hash)
        if cached is not None:
            cached_time, cached_result = cached
            if now - cached_time < config.rag_cache_ttl_seconds:
                logger.debug("RAG cache HIT: %s", query[:40])
                cache_hit = True
                self._last_query_meta = {"cache_hit": True, "rewritten_query": query}
                return cached_result
        logger.debug("RAG cache MISS: %s", query[:40])

        # ── FAQ 快速路径:纯查询类短问题跳过 LLM 改写和向量检索 ──
        faq_key = _match_faq(query, self._FAQ_PATTERNS)
        if faq_key and len(query.strip()) < 30:
            logger.debug("FAQ fast-path: %s → key=%s", query[:40], faq_key)
            bm25_results = search_bm25(
                self._bm25, self._chunks_metadata, faq_key, top_k=top_k
            )
            result = bm25_results[:top_k]
            self._last_query_meta = {
                "cache_hit": False, "rewritten_query": query,
                "rewrite_used": False, "faq_fast_path": True,
                "vector_count": 0, "bm25_count": len(bm25_results),
                "fused_count": len(result), "fusion_method": "bm25_faq",
            }
            if len(self._cache) >= self._cache_maxsize:
                oldest = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest]
            self._cache[cache_key_hash] = (time.time(), result)
            return result

        # 查询改写
        search_query = query
        rewrite_used = False
        if rewrite and self._rewriter:
            try:
                from src.rag.query_rewriter import rewrite_query
                search_query = rewrite_query(
                    self._rewriter, query, self._rewriter_model
                )
                rewrite_used = (search_query != query)
            except Exception as e:
                logger.warning("Query rewrite failed, using original: %s (error: %s)", query[:60], e)
                search_query = query  # 改写失败则回退

        embedder = self._get_embedder()
        query_vector = embedder.embed_query(search_query)

        # 检索宽度:有 reranker 时取更多候选再精选
        retrieval_k = top_k
        rerank_used = False
        if self._reranker and config.rerank_enabled:
            retrieval_k = config.rerank_retrieval_k

        # 向量检索(用改写后的 query)
        vector_results = search_vector(self._collection, query_vector, top_k=retrieval_k)

        # BM25 检索
        bm25_results = search_bm25(
            self._bm25, self._chunks_metadata, search_query, top_k=retrieval_k
        )

        # RRF 融合
        fused = rrf_fusion(vector_results, bm25_results)

        # 重排序(如果启用)
        if self._reranker and config.rerank_enabled:
            result = self._reranker.rerank(
                search_query, fused[:retrieval_k], top_k=config.rerank_top_k
            )
            rerank_used = True
        else:
            result = fused[:top_k]

        # ── 查询元数据(供 trace / 调试)─
        fusion_method = "rerank" if rerank_used else (
            "rrf" if (vector_results and bm25_results) else (
                "vector" if vector_results else "bm25"
            )
        )
        self._last_query_meta = {
            "cache_hit": cache_hit,
            "rewritten_query": search_query,
            "rewrite_used": rewrite_used,
            "vector_count": len(vector_results),
            "bm25_count": len(bm25_results),
            "fused_count": len(fused),
            "fusion_method": fusion_method,
            "rerank_used": rerank_used,
            "retrieval_k": retrieval_k,
            "top_k": top_k,
        }

        # 写入缓存(超出容量时淘汰最旧条目)
        if len(self._cache) >= self._cache_maxsize:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest]
        self._cache[cache_key_hash] = (time.time(), result)

        return result

    def is_index_stale(self) -> bool:
        """判断已有索引是否过期(文档目录中有文件比 meta 文件更新).

        用于服务启动时决定 load_index 还是 build_index:
        - meta 文件不存在 → 视为过期(需首次构建).
        - 任一文档的修改时间晚于 meta 文件 → 过期(需重建).
        - 文档数量与 meta 记录的不一致(增删文件)→ 过期.
        """
        meta_path = self._metadata_path()
        if not os.path.exists(meta_path):
            return True

        meta_mtime = os.path.getmtime(meta_path)
        docs_root = Path(self.docs_dir)
        if not docs_root.exists():
            return False

        doc_files = [
            f for f in docs_root.iterdir()
            if f.is_file()
            and f.suffix.lower() in {".md", ".txt", ".pdf", ".docx"}
            and not f.name.startswith(".")
        ]

        # 任一文档比 meta 新 → 内容有更新
        for f in doc_files:
            if f.stat().st_mtime > meta_mtime:
                return True

        # 文档数量与 meta 中记录的 source 数不一致 → 有增删
        try:
            with open(meta_path, "r", encoding="utf-8") as fp:
                saved = json.load(fp)
            saved_sources = {m.get("source") for m in saved}
            current_sources = {f.name for f in doc_files}
            if saved_sources != current_sources:
                return True
        except (json.JSONDecodeError, OSError):
            return True

        return False

    # ── 内部 ──────────────────────────────────────────────────

    def _get_embedder(self) -> Embedder:
        """返回 Embedder,优先使用外部注入的共享实例."""
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    def _get_chroma_client(self) -> Any:
        if self._client is None:
            os.makedirs(CHROMA_ROOT, exist_ok=True)
            self._client = chromadb.PersistentClient(path=CHROMA_ROOT)
        return self._client

    def _metadata_path(self) -> str:
        return os.path.join(CHROMA_ROOT, f"{_sanitize_name(self.kb_name)}_meta.json")

    def _save_metadata(self) -> None:
        """将 chunks_metadata 存为 JSON,供 load_index 使用."""
        path = self._metadata_path()
        serializable = [
            {k: v for k, v in m.items() if isinstance(v, (str, int, float, bool))}
            for m in self._chunks_metadata
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)


def _sanitize_name(name: str) -> str:
    """清理知识库名称,确保可用作文件名/collection名."""
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _match_faq(query: str, patterns: dict[str, str]) -> str | None:
    """FAQ 关键词匹配:query 中含哪个高频关键词就返回对应检索词.

    用于短查询直接走 BM25 快速路径,跳过 LLM 改写和向量检索.
    """
    qlower = query.lower()
    for keyword, search_term in patterns.items():
        if keyword.lower() in qlower:
            return search_term
    return None
