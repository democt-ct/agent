import hashlib
import math
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import DATA_DIR
from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk

# Optional dependencies: loaded lazily to avoid importing torch / sentence-transformers
# at module level when the project uses OpenAI-compatible embeddings.
_chromadb = None
_OpenAIEmbeddings = None
_HuggingFaceEmbeddings = None
_chromadb_lock = threading.Lock()
_openai_embeddings_lock = threading.Lock()
_hf_embeddings_lock = threading.Lock()


def _get_chromadb():
    global _chromadb
    if _chromadb is not None:
        return _chromadb
    with _chromadb_lock:
        if _chromadb is not None:
            return _chromadb
        try:
            import chromadb as _mod  # type: ignore
            _chromadb = _mod
        except Exception:
            _chromadb = False
        return _chromadb


def _get_openai_embeddings():
    global _OpenAIEmbeddings
    if _OpenAIEmbeddings is not None:
        return _OpenAIEmbeddings
    with _openai_embeddings_lock:
        if _OpenAIEmbeddings is not None:
            return _OpenAIEmbeddings
        try:
            from langchain_openai import OpenAIEmbeddings as _cls  # type: ignore
            _OpenAIEmbeddings = _cls
        except Exception:
            _OpenAIEmbeddings = False
        return _OpenAIEmbeddings


def _get_hf_embeddings():
    global _HuggingFaceEmbeddings
    if _HuggingFaceEmbeddings is not None:
        return _HuggingFaceEmbeddings
    with _hf_embeddings_lock:
        if _HuggingFaceEmbeddings is not None:
            return _HuggingFaceEmbeddings
        try:
            from langchain_huggingface import HuggingFaceEmbeddings as _cls  # type: ignore
            _HuggingFaceEmbeddings = _cls
        except Exception:
            _HuggingFaceEmbeddings = False
        return _HuggingFaceEmbeddings


VECTOR_DIMENSION = max(64, int(os.getenv("KNOWLEDGE_VECTOR_DIMENSION", "256")))
CHROMA_PATH = os.getenv("KNOWLEDGE_CHROMA_PATH", os.path.join(DATA_DIR, "chroma_knowledge"))
CHROMA_COLLECTION = os.getenv("KNOWLEDGE_CHROMA_COLLECTION", "memory_knowledge_chunks")
EMBEDDING_PROVIDER = os.getenv("KNOWLEDGE_EMBEDDING_PROVIDER", "auto").strip().lower()
EMBEDDING_MODEL = os.getenv("KNOWLEDGE_EMBEDDING_MODEL", os.getenv("TEXT_EMBEDDING_MODEL", "text-embedding-3-small")).strip()
EMBEDDING_API_BASE = os.getenv("KNOWLEDGE_EMBEDDING_API_BASE", "").strip()
EMBEDDING_API_KEY = os.getenv("KNOWLEDGE_EMBEDDING_API_KEY", "").strip()
EMBEDDING_DIMENSIONS = os.getenv("KNOWLEDGE_EMBEDDING_DIMENSIONS", "").strip()
HF_EMBEDDING_MODEL = os.getenv("KNOWLEDGE_HF_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5").strip()
HF_EMBEDDING_DEVICE = os.getenv("KNOWLEDGE_HF_DEVICE", "auto").strip()

# ---- Reranker configuration ----
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2").strip()
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "auto").strip()
RERANKER_CANDIDATE_LIMIT = int(os.getenv("RERANKER_CANDIDATE_LIMIT", "20"))
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "5"))

# ---- Query Rewrite configuration ----
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

# Lazy load for CrossEncoder
_CrossEncoder = None
_CrossEncoder_lock = threading.Lock()

def _get_cross_encoder():
    global _CrossEncoder
    if _CrossEncoder is not None:
        return _CrossEncoder
    with _CrossEncoder_lock:
        if _CrossEncoder is not None:
            return _CrossEncoder
        try:
            from sentence_transformers import CrossEncoder as _CE
            _CrossEncoder = _CE
        except Exception:
            _CrossEncoder = False
        return _CrossEncoder


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+")
_PUNCT_PATTERN = re.compile(r"[\s\-\_/,:;.!?，。；、（）()【】\[\]{}<>\"'“”‘’`~|\\]+")


@dataclass
class KnowledgeRetrievalHit:
    chunk: MemoryKnowledgeChunk
    vector_score: float
    keyword_score: float
    metadata_score: float
    recency_score: float
    final_score: float
    match_reasons: List[str]

    @property
    def citation(self) -> str:
        title = (self.chunk.title or "").strip()
        domain = (self.chunk.domain or "").strip()
        source_type = (self.chunk.source_type or "").strip()
        source_ref = (self.chunk.source_ref or "").strip()
        pieces = [piece for piece in [domain, title, source_type] if piece]
        base = " / ".join(pieces) if pieces else (self.chunk.id or "knowledge-chunk")
        if source_ref:
            return f"{base} [{source_ref}]"
        return base


def _normalize_text(value: Optional[str]) -> str:
    return " ".join((value or "").strip().split())


def _clip_text(value: str, *, max_chars: int = 240) -> str:
    text = _normalize_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _split_tokens(text: str) -> List[str]:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return []
    tokens: List[str] = []
    for match in _TOKEN_PATTERN.finditer(normalized):
        token = match.group(0).strip()
        if not token:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(token[i : i + 2] for i in range(max(0, len(token) - 1)))
            if len(token) >= 3:
                tokens.extend(token[i : i + 3] for i in range(max(0, len(token) - 2)))
        else:
            tokens.append(token)
    return [token for token in tokens if token]


def _hash_to_index(token: str, dimension: int) -> int:
    digest = hashlib.sha1(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dimension


class HashTextEmbedder:
    def __init__(self, dimension: int = VECTOR_DIMENSION) -> None:
        self.dimension = dimension
        self.backend_name = f"hash-{dimension}"

    def embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        tokens = _split_tokens(text)
        if not tokens:
            return vector
        for token in tokens:
            index = _hash_to_index(token, self.dimension)
            weight = 1.0 + min(len(token), 12) * 0.03
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text)


def _slugify_backend_name(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized or "embeddings"


def _backend_collection_suffix(value: str) -> str:
    digest = hashlib.sha1((value or "").encode("utf-8")).hexdigest()
    return digest[:12]


def _parse_embedding_dimensions() -> Optional[int]:
    if not EMBEDDING_DIMENSIONS:
        return None
    try:
        value = int(EMBEDDING_DIMENSIONS)
    except ValueError:
        return None
    return value if value > 0 else None


def _resolve_hf_device(device_env: Optional[str] = None) -> str:
    configured = (device_env or HF_EMBEDDING_DEVICE or "").strip().lower()
    if configured and configured not in {"", "auto"}:
        return configured
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class LangChainTextEmbedder:
    def __init__(
        self,
        *,
        provider: str,
        model_name: str,
        api_base: str = "",
        api_key: str = "",
        dimensions: Optional[int] = None,
        device: str = "cpu",
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.api_base = api_base.strip()
        self.api_key = api_key.strip()
        self.dimensions = dimensions
        self.device = device
        self._embeddings = None
        self._init_lock = threading.Lock()
        self._fallback = HashTextEmbedder()
        self.backend_name = self._build_backend_name()

    def _build_backend_name(self) -> str:
        if self.provider == "openai":
            return _slugify_backend_name(f"openai-{self.model_name}")
        return _slugify_backend_name(f"{self.provider}-{self.model_name}")

    def _build_embeddings(self):
        if self.provider == "openai":
            OpenAIEmbeddings = _get_openai_embeddings()
            if not OpenAIEmbeddings:
                raise RuntimeError("langchain_openai is not installed")
            kwargs = {"model": self.model_name}
            if self.api_base:
                kwargs["base_url"] = self.api_base
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.dimensions:
                kwargs["dimensions"] = self.dimensions
            return OpenAIEmbeddings(**kwargs)

        if self.provider in {"hf", "huggingface", "sentence_transformers", "sentence-transformers"}:
            HuggingFaceEmbeddings = _get_hf_embeddings()
            if not HuggingFaceEmbeddings:
                raise RuntimeError("langchain_huggingface is not installed")
            return HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": self.device},
                encode_kwargs={"normalize_embeddings": True},
            )

        raise RuntimeError(f"Unsupported embedding provider: {self.provider}")

    def _get_embeddings(self):
        if self._embeddings is not None:
            return self._embeddings
        with self._init_lock:
            if self._embeddings is None:
                self._embeddings = self._build_embeddings()
        return self._embeddings

    def embed_text(self, text: str) -> List[float]:
        try:
            return list(self._get_embeddings().embed_query(text))
        except Exception:
            return self._fallback.embed_query(text)

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        try:
            return [list(vector) for vector in self._get_embeddings().embed_documents(list(texts))]
        except Exception:
            return self._fallback.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text)

    def warmup(self) -> None:
        self._get_embeddings()


def _build_embedding_backend():
    provider = EMBEDDING_PROVIDER
    dimensions = _parse_embedding_dimensions()
    candidate_order: List[str] = []
    if provider and provider != "auto":
        candidate_order = [provider]
    else:
        if EMBEDDING_API_BASE or EMBEDDING_API_KEY:
            candidate_order.append("openai")
        if HF_EMBEDDING_MODEL:
            candidate_order.append("sentence_transformers")

    for candidate in candidate_order:
        try:
            if candidate == "openai":
                if not _get_openai_embeddings():
                    continue
                return LangChainTextEmbedder(
                    provider="openai",
                    model_name=EMBEDDING_MODEL,
                    api_base=EMBEDDING_API_BASE,
                    api_key=EMBEDDING_API_KEY,
                    dimensions=dimensions,
                )
            if candidate in {"hf", "huggingface", "sentence_transformers", "sentence-transformers"}:
                if not _get_hf_embeddings():
                    continue
                return LangChainTextEmbedder(
                    provider="sentence_transformers",
                    model_name=HF_EMBEDDING_MODEL,
                    device=_resolve_hf_device(),
                )
            if candidate == "local_hash":
                return HashTextEmbedder()
        except Exception:
            continue

    return HashTextEmbedder()


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _metadata_value(value: Optional[str]) -> str:
    return (value or "").strip() or "__global__"


def _allowed_for_time_window(chunk: MemoryKnowledgeChunk, now: Optional[datetime] = None) -> bool:
    current = now or _now_utc()
    effective_from = _to_utc(getattr(chunk, "effective_from", None))
    expires_at = _to_utc(getattr(chunk, "expires_at", None))
    if effective_from and effective_from > current:
        return False
    if expires_at and expires_at < current:
        return False
    return True


def _build_chunk_document(chunk: MemoryKnowledgeChunk) -> str:
    parts = [
        f"domain: {chunk.domain or ''}",
        f"title: {chunk.title or ''}",
        f"source_type: {chunk.source_type or ''}",
        f"tags: {chunk.tags or ''}",
        f"text: {chunk.chunk_text or ''}",
    ]
    if chunk.source_ref:
        parts.append(f"source_ref: {chunk.source_ref}")
    if chunk.version:
        parts.append(f"version: {chunk.version}")
    return "\n".join(part for part in parts if part.strip())


def _build_chunk_metadata(chunk: MemoryKnowledgeChunk) -> Dict[str, str]:
    return {
        "chunk_id": chunk.id,
        "hospital_id": _metadata_value(chunk.hospital_id),
        "domain": _metadata_value(chunk.domain),
        "source_type": _metadata_value(chunk.source_type),
        "source_ref": _metadata_value(chunk.source_ref),
        "version": _metadata_value(chunk.version),
        "title": _normalize_text(chunk.title),
        "tags": _metadata_value(chunk.tags),
        "embedding_key": _metadata_value(chunk.embedding_key),
    }


def _rewrite_query(query_text: str) -> str:
    """Use LLM to rewrite the user query for better retrieval quality.

    Lightweight reformulation that preserves original intent while expanding
    medical terminology and abbreviations. Falls back to the original query
    on any error.
    """
    if not query_text or not query_text.strip():
        return query_text

    try:
        from app.mcp.config import get_llm

        llm = get_llm()
        prompt = (
            "你是一个医疗知识检索助手。请将用户的查询改写成更适合向量检索的形式：\n"
            "1. 保留原始查询的核心意图\n"
            "2. 补充相关的医学术语和常用同义词\n"
            "3. 扩展缩写和简称（例如 高血压 → 高血压病, 糖尿病 → 糖尿病 mellitus）\n"
            "4. 只返回改写后的查询文本，不要解释，不要前缀\n\n"
            f"原始查询：{query_text}"
        )
        response = llm.invoke(prompt)
        rewritten = response.content.strip()
        if rewritten:
            return rewritten
    except Exception:
        import logging
        logging.getLogger("app.services.knowledge_retrieval").exception(
            "Query rewrite failed, falling back to original query"
        )
    return query_text


class Reranker:
    """Cross-Encoder reranker for knowledge retrieval results.

    Uses BAAI/bge-reranker-v2-m3 (or configured model) to re-rank
    candidate chunks with a Cross-Encoder for better precision.
    Falls back gracefully if the model is not available.
    """

    def __init__(self) -> None:
        self._model = None
        self._model_lock = threading.Lock()
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        if not RERANKER_ENABLED:
            self._available = False
            return False
        CE = _get_cross_encoder()
        if not CE:
            self._available = False
            return False
        self._available = True
        return True

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            CE = _get_cross_encoder()
            if not CE:
                return None
            try:
                device = _resolve_hf_device(RERANKER_DEVICE)
                self._model = CE(
                    RERANKER_MODEL,
                    device=device,
                    max_length=512,
                )
            except Exception:
                self._model = None
            return self._model

    def rerank(
        self,
        query: str,
        candidates: List[KnowledgeRetrievalHit],
        top_k: int = RERANKER_TOP_K,
    ) -> List[KnowledgeRetrievalHit]:
        """Re-rank candidates with Cross-Encoder and return top_k."""
        if not self.available or not candidates:
            return candidates[:top_k]

        model = self._load_model()
        if model is None:
            return candidates[:top_k]

        if len(candidates) <= top_k:
            return candidates

        # Build (query, document) pairs
        pairs = []
        for hit in candidates:
            doc = _build_chunk_document(hit.chunk)
            pairs.append((query, doc))

        try:
            scores = model.predict(
                pairs,
                batch_size=min(8, len(pairs)),
                show_progress_bar=False,
            )
        except Exception:
            return candidates[:top_k]

        # Attach Cross-Encoder scores and re-sort
        scored: List[tuple[float, KnowledgeRetrievalHit]] = []
        for i, hit in enumerate(candidates):
            ce_score = float(scores[i]) if i < len(scores) else 0.0
            # Blend: 70% Cross-Encoder + 30% original final_score
            blended = 0.7 * ce_score + 0.3 * hit.final_score
            scored.append((blended, hit))

        scored.sort(key=lambda x: x[0], reverse=True)
        reranked = [hit for _, hit in scored[:top_k]]

        # Mark rerank reason
        for hit in reranked:
            if "rerank" not in hit.match_reasons:
                hit.match_reasons.append("rerank")

        return reranked

    def warmup(self) -> None:
        if not self.available:
            return
        self._load_model()


class HybridKnowledgeRetriever:
    def __init__(self) -> None:
        self.embedder = _build_embedding_backend()
        self.reranker = Reranker()
        self._lock = threading.Lock()
        self._sync_lock = threading.Lock()
        self._embedding_cache_lock = threading.Lock()
        self._chroma_client = None
        self._collection = None
        backend_name = getattr(self.embedder, "backend_name", "embeddings")
        self.collection_name = f"{CHROMA_COLLECTION}__{_backend_collection_suffix(str(backend_name))}"
        self._synced_once = False
        self._chunk_embedding_cache: Dict[str, tuple[str, List[float]]] = {}

    def _get_collection(self):
        chromadb = _get_chromadb()
        if not chromadb:
            return None
        with self._lock:
            if self._collection is not None:
                return self._collection
            try:
                os.makedirs(CHROMA_PATH, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
                self._collection = self._chroma_client.get_or_create_collection(name=self.collection_name)
            except Exception:
                self._collection = None
                self._chroma_client = None
            return self._collection

    def _ensure_index_synced(self, db: Session) -> None:
        if self._synced_once:
            return
        with self._sync_lock:
            if self._synced_once:
                return
            chunks = (
                db.query(MemoryKnowledgeChunk)
                .order_by(MemoryKnowledgeChunk.updated_at.desc(), MemoryKnowledgeChunk.created_at.desc())
                .all()
            )
            for chunk in chunks:
                self.upsert_chunk(chunk)
            self._synced_once = True

    def _chunk_embedding_cache_key(self, chunk: MemoryKnowledgeChunk) -> str:
        updated_at = getattr(chunk, "updated_at", None) or getattr(chunk, "created_at", None)
        stamp = _to_utc(updated_at).isoformat() if isinstance(updated_at, datetime) else str(updated_at or "")
        return f"{chunk.id}:{stamp}"

    def _get_chunk_embedding(self, chunk: MemoryKnowledgeChunk) -> List[float]:
        cache_key = self._chunk_embedding_cache_key(chunk)
        with self._embedding_cache_lock:
            cached = self._chunk_embedding_cache.get(chunk.id)
            if cached and cached[0] == cache_key:
                return cached[1]

        document = _build_chunk_document(chunk)
        embedding = self.embedder.embed_text(document)
        with self._embedding_cache_lock:
            self._chunk_embedding_cache[chunk.id] = (cache_key, embedding)
        return embedding

    def _fetch_candidate_chunks(
        self,
        db: Session,
        *,
        query_text: str,
        hospital_id: Optional[str],
        domain: Optional[str],
        limit: int,
    ) -> List[MemoryKnowledgeChunk]:
        query = db.query(MemoryKnowledgeChunk)
        if hospital_id:
            query = query.filter(or_(MemoryKnowledgeChunk.hospital_id == hospital_id, MemoryKnowledgeChunk.hospital_id.is_(None)))
        if domain:
            query = query.filter(MemoryKnowledgeChunk.domain == domain)
        candidates = query.order_by(MemoryKnowledgeChunk.updated_at.desc(), MemoryKnowledgeChunk.created_at.desc()).all()
        if not candidates:
            return []
        if len(candidates) <= max(limit * 12, 40):
            return candidates

        query_tokens = [token for token in _split_tokens(query_text) if len(token) >= 2]
        ranked: List[tuple[int, MemoryKnowledgeChunk]] = []
        for chunk in candidates:
            score = 0
            haystack = " ".join(
                [
                    chunk.title or "",
                    chunk.chunk_text or "",
                    chunk.tags or "",
                    chunk.domain or "",
                    chunk.source_type or "",
                ]
            ).lower()
            for token in query_tokens:
                if token.lower() in haystack:
                    score += 1
            if score:
                ranked.append((score, chunk))
        if ranked:
            ranked.sort(key=lambda item: (item[0], item[1].updated_at or item[1].created_at), reverse=True)
            return [item[1] for item in ranked[: max(limit * 16, 60)]]
        return candidates[: max(limit * 16, 60)]

    def _query_chroma_ids(
        self,
        query_text: str,
        *,
        hospital_id: Optional[str],
        domain: Optional[str],
        limit: int,
    ) -> List[str]:
        collection = self._get_collection()
        if collection is None:
            return []
        try:
            query_embedding = self.embedder.embed_query(query_text)
            where = {}
            filters = []
            if hospital_id:
                filters.append({"$or": [{"hospital_id": hospital_id}, {"hospital_id": "__global__"}]})
            if domain:
                filters.append({"domain": domain})
            if filters:
                where = filters[0] if len(filters) == 1 else {"$and": filters}
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(12, limit * 4),
                where=where or None,
            )
            ids = (result.get("ids") or [[]])[0]
            return [str(item) for item in ids if item]
        except Exception:
            return []

    def upsert_chunk(self, chunk: MemoryKnowledgeChunk) -> None:
        collection = self._get_collection()
        if collection is None:
            return
        try:
            document = _build_chunk_document(chunk)
            metadata = _build_chunk_metadata(chunk)
            embedding = self._get_chunk_embedding(chunk)
            collection.upsert(
                ids=[chunk.id],
                documents=[document],
                metadatas=[metadata],
                embeddings=[embedding],
            )
        except Exception:
            return

    def delete_chunk(self, chunk_id: str) -> None:
        collection = self._get_collection()
        if collection is None:
            return
        try:
            collection.delete(ids=[chunk_id])
            with self._embedding_cache_lock:
                self._chunk_embedding_cache.pop(chunk_id, None)
        except Exception:
            return

    def _score_keywords(self, query_text: str, chunk: MemoryKnowledgeChunk) -> float:
        query_tokens = [token for token in _split_tokens(query_text) if token]
        if not query_tokens:
            return 0.0
        title = (chunk.title or "").lower()
        text = " ".join([chunk.chunk_text or "", chunk.tags or "", chunk.domain or "", chunk.source_type or ""]).lower()
        hits = 0.0
        for token in query_tokens:
            lowered = token.lower()
            if lowered in title:
                hits += 2.0
            elif lowered in text:
                hits += 1.0
        coverage = hits / max(2.0, float(len(query_tokens)))
        return max(0.0, min(1.0, coverage))

    def _score_metadata(
        self,
        chunk: MemoryKnowledgeChunk,
        *,
        hospital_id: Optional[str],
        domain: Optional[str],
    ) -> tuple[float, List[str]]:
        reasons: List[str] = []
        score = 0.0
        if hospital_id:
            if chunk.hospital_id == hospital_id:
                score += 0.55
                reasons.append("hospital_match")
            elif chunk.hospital_id is None:
                score += 0.25
                reasons.append("global_chunk")
        else:
            score += 0.15
        if domain and chunk.domain == domain:
            score += 0.25
            reasons.append("domain_match")
        if chunk.source_type:
            score += 0.05
        if _allowed_for_time_window(chunk):
            score += 0.1
        else:
            score -= 0.3
            reasons.append("time_window_filtered")
        score = max(0.0, min(1.0, score))
        return score, reasons

    def _score_recency(self, chunk: MemoryKnowledgeChunk) -> float:
        reference = _to_utc(getattr(chunk, "effective_from", None)) or _to_utc(getattr(chunk, "updated_at", None)) or _to_utc(getattr(chunk, "created_at", None))
        if not reference:
            return 0.0
        age_days = max(0.0, (_now_utc() - reference).total_seconds() / 86400.0)
        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.8
        if age_days <= 180:
            return 0.5
        return 0.2

    def _merge_candidate_chunks(
        self,
        db: Session,
        *,
        query_text: str,
        hospital_id: Optional[str],
        domain: Optional[str],
        limit: int,
    ) -> List[MemoryKnowledgeChunk]:
        candidate_map: Dict[str, MemoryKnowledgeChunk] = {}
        chroma_ids = self._query_chroma_ids(query_text, hospital_id=hospital_id, domain=domain, limit=limit)
        if chroma_ids:
            rows = db.query(MemoryKnowledgeChunk).filter(MemoryKnowledgeChunk.id.in_(chroma_ids)).all()
            for row in rows:
                candidate_map[row.id] = row

        for row in self._fetch_candidate_chunks(
            db,
            query_text=query_text,
            hospital_id=hospital_id,
            domain=domain,
            limit=limit,
        ):
            candidate_map[row.id] = row

        now = _now_utc()
        if not candidate_map:
            return []

        scored = []
        query_embedding = self.embedder.embed_query(query_text)
        for chunk in candidate_map.values():
            if not _allowed_for_time_window(chunk, now=now):
                continue
            chunk_embedding = self._get_chunk_embedding(chunk)
            vector_score = _cosine_similarity(query_embedding, chunk_embedding)
            keyword_score = self._score_keywords(query_text, chunk)
            metadata_score, metadata_reasons = self._score_metadata(chunk, hospital_id=hospital_id, domain=domain)
            recency_score = self._score_recency(chunk)
            final_score = round(
                0.58 * vector_score
                + 0.22 * keyword_score
                + 0.12 * metadata_score
                + 0.08 * recency_score
                + min(float(chunk.confidence or 0.0), 1.0) * 0.04,
                6,
            )
            reasons = []
            if vector_score >= 0.3:
                reasons.append("vector")
            if keyword_score >= 0.3:
                reasons.append("keyword")
            reasons.extend(metadata_reasons)
            scored.append(
                KnowledgeRetrievalHit(
                    chunk=chunk,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    metadata_score=metadata_score,
                    recency_score=recency_score,
                    final_score=final_score,
                    match_reasons=reasons or ["retrieved"],
                )
            )

        scored.sort(
            key=lambda item: (
                item.final_score,
                item.vector_score,
                item.keyword_score,
                item.chunk.updated_at or item.chunk.created_at,
            ),
            reverse=True,
        )

        filtered = []
        for hit in scored:
            if hit.final_score <= 0.01:
                continue
            filtered.append(hit.chunk)
            if len(filtered) >= max(limit, 1):
                break
        return filtered

    def search(
        self,
        db: Session,
        *,
        query_text: str,
        hospital_id: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[KnowledgeRetrievalHit]:
        self._ensure_index_synced(db)

        # --- Query Rewrite: optionally reformulate the query for better retrieval ---
        if QUERY_REWRITE_ENABLED:
            rewritten = _rewrite_query(query_text)
        else:
            rewritten = query_text
        query_text = rewritten  # use rewritten query for the rest of the pipeline

        candidate_map: Dict[str, MemoryKnowledgeChunk] = {}
        chroma_ids = self._query_chroma_ids(query_text, hospital_id=hospital_id, domain=domain, limit=limit)
        if chroma_ids:
            rows = db.query(MemoryKnowledgeChunk).filter(MemoryKnowledgeChunk.id.in_(chroma_ids)).all()
            for row in rows:
                candidate_map[row.id] = row

        for row in self._fetch_candidate_chunks(
            db,
            query_text=query_text,
            hospital_id=hospital_id,
            domain=domain,
            limit=limit,
        ):
            candidate_map[row.id] = row

        now = _now_utc()
        hits: List[KnowledgeRetrievalHit] = []
        query_embedding = self.embedder.embed_query(query_text)
        for chunk in candidate_map.values():
            if not _allowed_for_time_window(chunk, now=now):
                continue
            chunk_embedding = self._get_chunk_embedding(chunk)
            vector_score = _cosine_similarity(query_embedding, chunk_embedding)
            keyword_score = self._score_keywords(query_text, chunk)
            metadata_score, metadata_reasons = self._score_metadata(chunk, hospital_id=hospital_id, domain=domain)
            recency_score = self._score_recency(chunk)
            final_score = round(
                0.58 * vector_score
                + 0.22 * keyword_score
                + 0.12 * metadata_score
                + 0.08 * recency_score
                + min(float(chunk.confidence or 0.0), 1.0) * 0.04,
                6,
            )
            reasons = []
            if vector_score >= 0.3:
                reasons.append("vector")
            if keyword_score >= 0.3:
                reasons.append("keyword")
            reasons.extend(metadata_reasons)
            hits.append(
                KnowledgeRetrievalHit(
                    chunk=chunk,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    metadata_score=metadata_score,
                    recency_score=recency_score,
                    final_score=final_score,
                    match_reasons=reasons or ["retrieved"],
                )
            )

        hits.sort(
            key=lambda item: (
                item.final_score,
                item.vector_score,
                item.keyword_score,
                item.chunk.updated_at or item.chunk.created_at,
            ),
            reverse=True,
        )

        # --- Reranker: Cross-Encoder re-ranking ---
        if self.reranker.available and len(hits) > RERANKER_TOP_K:
            candidates_for_rerank = hits[: min(len(hits), RERANKER_CANDIDATE_LIMIT)]
            hits = self.reranker.rerank(query_text, candidates_for_rerank, top_k=RERANKER_TOP_K)

        return hits[: max(limit, 1)]

    def build_context(
        self,
        db: Session,
        *,
        query_text: str,
        hospital_id: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 3,
    ) -> Optional[str]:
        hits = self.search(
            db,
            query_text=query_text,
            hospital_id=hospital_id,
            domain=domain,
            limit=limit,
        )
        if not hits:
            return None

        lines = ["Relevant knowledge evidence:"]
        for index, hit in enumerate(hits, start=1):
            chunk = hit.chunk
            citation = hit.citation
            text = _clip_text(chunk.chunk_text, max_chars=260)
            source_parts = [f"score={hit.final_score:.3f}", f"vector={hit.vector_score:.3f}", f"keyword={hit.keyword_score:.3f}"]
            if hit.match_reasons:
                source_parts.append(f"reasons={','.join(hit.match_reasons)}")
            source_line = "; ".join(source_parts)
            lines.append(f"{index}. [{citation}] ({source_line}) {text}")
        return "\n".join(lines)

    def warmup(self) -> None:
        warmup_text = "患者复诊与病历摘要"
        try:
            if hasattr(self.embedder, "warmup"):
                self.embedder.warmup()
            else:
                self.embedder.embed_query(warmup_text)
        except Exception:
            pass
        # Warm up reranker
        try:
            self.reranker.warmup()
        except Exception:
            pass


_RETRIEVER = None
_RETRIEVER_LOCK = threading.Lock()


def get_knowledge_retriever() -> HybridKnowledgeRetriever:
    global _RETRIEVER
    if _RETRIEVER is not None:
        return _RETRIEVER
    with _RETRIEVER_LOCK:
        if _RETRIEVER is not None:
            return _RETRIEVER
        _RETRIEVER = HybridKnowledgeRetriever()
        return _RETRIEVER
