"""混合检索器 -- 向量 + BM25 → RRF 融合.

检索流程:
  向量检索 (语义) ─┐
                    ├── RRF 融合 ──→ 排序结果
  BM25 检索 (关键词) ┘
"""

from __future__ import annotations

from typing import Any

import jieba
from rank_bm25 import BM25Okapi


# ═══════════════════════════════════════════════════════════════════
# BM25 索引
# ═══════════════════════════════════════════════════════════════════


def tokenize_chinese(text: str) -> list[str]:
    """jieba 分词,用于 BM25 索引构建和查询."""
    return list(jieba.cut(text))


def build_bm25(chunks: list[str]) -> BM25Okapi:
    """用 chunk 的纯文本构建 BM25 索引.

    Args:
        chunks: chunk 纯文本列表,每个元素是一段文本.

    Returns:
        BM25Okapi 索引实例.
    """
    tokenized = [tokenize_chinese(c) for c in chunks]
    return BM25Okapi(tokenized)


# ═══════════════════════════════════════════════════════════════════
# 向量检索 (Chroma)
# ═══════════════════════════════════════════════════════════════════


def search_vector(
    collection: Any,
    query_vector: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Chroma 向量相似度检索.

    Returns:
        [{"content": "...", "source": "...", "score": 0.94, "chunk_index": 0}, ...]
    """
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    out: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return out

    for i, chunk_id in enumerate(results["ids"][0]):
        doc_text = results["documents"][0][i] if results["documents"] else ""
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 0.0

        score = 1.0 / (1.0 + distance)  # L2 距离 → 相似度
        out.append({
            "content": doc_text,
            "source": meta.get("source", ""),
            "title": meta.get("title", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "score": round(score, 4),
            "method": "vector",
        })

    return out


# ═══════════════════════════════════════════════════════════════════
# BM25 检索
# ═══════════════════════════════════════════════════════════════════


def search_bm25(
    bm25_index: BM25Okapi,
    chunks_metadata: list[dict[str, Any]],
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """BM25 关键词检索.

    Args:
        bm25_index: 已构建的 BM25 索引.
        chunks_metadata: chunk 元数据列表(与 bm25 索引顺序一致).
        query: 检索查询.
        top_k: 返回条数.

    Returns:
        [{"content": "...", "source": "...", "score": 8.2, "chunk_index": 0}, ...]
    """
    tokenized_query = tokenize_chinese(query)
    scores = bm25_index.get_scores(tokenized_query)

    # 取 top-k
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top_indices = indexed[:top_k]

    out: list[dict[str, Any]] = []
    for idx, score in top_indices:
        if idx < len(chunks_metadata):
            meta = chunks_metadata[idx]
            out.append({
                "content": meta.get("content", ""),
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "score": round(float(score), 4),
                "method": "bm25",
            })

    return out


# ═══════════════════════════════════════════════════════════════════
# RRF 融合
# ═══════════════════════════════════════════════════════════════════


def rrf_fusion(
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    k: int = 10,
    bm25_weight: float = 1.5,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion -- 融合向量检索和 BM25 检索结果.

    每个结果的 RRF 分数 = 1/(k + rank_vector) + 1/(k + rank_bm25)

    Args:
        vector_results: 向量检索结果列表.
        bm25_results: BM25 检索结果列表.
        k: RRF 参数,默认 60.

    Returns:
        按 RRF 分数降序排列的结果列表.
    """
    # chunk_id = source + "::" + chunk_index
    def make_id(r: dict) -> str:
        return f"{r.get('source', '')}::{r.get('chunk_index', 0)}"

    rrf_scores: dict[str, float] = {}
    all_results: dict[str, dict[str, Any]] = {}

    for rank, r in enumerate(vector_results):
        cid = make_id(r)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        all_results[cid] = r

    for rank, r in enumerate(bm25_results):
        cid = make_id(r)
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + bm25_weight / (k + rank + 1)
        if cid not in all_results:
            all_results[cid] = r

    # 按 RRF 分数降序排列
    sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # 归一化到 0-1:最高分 → ~1.0,方便前端直观理解
    max_score = sorted_ids[0][1] if sorted_ids else 1.0

    out: list[dict[str, Any]] = []
    for cid, rrf_score in sorted_ids:
        result = all_results[cid].copy()
        result["score"] = round(rrf_score / max_score, 4) if max_score > 0 else 0.0
        result["method"] = "rrf"
        out.append(result)

    return out
