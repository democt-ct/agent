"""Reranker -- post-retrieval relevance re-scoring.

Re-ranks candidate chunks from the hybrid retriever using a cross-encoder
model, producing a more precise top-K for the Agent's context window.

Supports:
  - Cross-encoder (BAAI/bge-reranker-base, local, no API key needed)
  - Cohere Rerank API (requires COHERE_API_KEY)

The model is lazy-loaded on first call; failures degrade gracefully
(original retrieval order is preserved).
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import config

logger = logging.getLogger(__name__)

# ── Default model (Chinese-friendly, small footprint) ────────────
_DEFAULT_CROSS_ENCODER = "BAAI/bge-reranker-base"


class Reranker:
    """Post-retrieval reranker using a cross-encoder or API.

    Usage:
        reranker = Reranker()
        reranked = reranker.rerank(
            query="年假还剩几天",
            chunks=[{"content": "...", "score": 0.9}, ...],
            top_k=3,
        )
    """

    def __init__(
        self,
        model_name: str | None = None,
        backend: str = "cross-encoder",
    ) -> None:
        """
        Args:
            model_name: Model ID. For cross-encoder, e.g. "BAAI/bge-reranker-base".
                        For cohere, e.g. "rerank-v3.5".  Defaults to config.rerank_model.
            backend:    "cross-encoder" (local) or "cohere" (API).
        """
        self._model_name = model_name or config.rerank_model
        self._backend = backend
        self._model: Any = None  # lazy-loaded
        self._load_error: str | None = None

    # ── Public API ──────────────────────────────────────────────

    def rerank(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Re-rank chunks by relevance to the query.

        Args:
            query:  The original user query (or rewritten query).
            chunks: Candidate chunks from the retriever.
                    Each must have "content" key; "score" and "method" are preserved.
            top_k:  Number of chunks to return after reranking.

        Returns:
            Re-ordered chunks (length ≤ min(top_k, len(chunks))), each with
            an updated "score" and "method" field set to "rerank".
        """
        if not chunks:
            return chunks

        try:
            if self._backend == "cohere":
                return self._rerank_cohere(query, chunks, top_k)
            return self._rerank_cross_encoder(query, chunks, top_k)
        except Exception as e:
            logger.warning("Rerank failed, falling back to original order: %s", e)
            # Degrade gracefully: return original top-K
            return self._preserve_original(chunks, top_k)

    # ── Cross-encoder backend ────────────────────────────────────

    def _rerank_cross_encoder(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        model = self._get_cross_encoder()
        if model is None:
            return self._preserve_original(chunks, top_k)

        # Build (query, chunk) pairs
        pairs = [(query, c.get("content", "")) for c in chunks]

        # Score all pairs
        scores = model.predict(pairs, show_progress_bar=False)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()

        # Pair scores with chunk indices and sort
        indexed = [(i, float(scores[i])) for i in range(len(scores))]
        indexed.sort(key=lambda x: x[1], reverse=True)

        return self._build_reranked(chunks, indexed, top_k)

    def _get_cross_encoder(self) -> Any:
        """Lazy-load the cross-encoder model.  Returns None on failure."""
        if self._model is not None:
            return self._model
        if self._load_error:
            return None

        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model: %s", self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("Reranker model loaded")
            return self._model
        except Exception as e:
            self._load_error = str(e)
            logger.warning("Failed to load reranker model '%s': %s", self._model_name, e)
            return None

    # ── Cohere backend ───────────────────────────────────────────

    def _rerank_cohere(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        import cohere

        api_key = __import__("os").getenv("COHERE_API_KEY", "")
        if not api_key:
            logger.warning("COHERE_API_KEY not set, falling back to original order")
            return self._preserve_original(chunks, top_k)

        client = cohere.Client(api_key=api_key)
        documents = [c.get("content", "") for c in chunks]

        response = client.rerank(
            model=self._model_name,
            query=query,
            documents=documents,
            top_n=min(top_k, len(chunks)),
        )

        indexed = [(r.index, r.relevance_score) for r in response.results]
        return self._build_reranked(chunks, indexed, top_k)

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_reranked(
        chunks: list[dict[str, Any]],
        indexed: list[tuple[int, float]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Re-order chunks by the scored index list and tag them."""
        out: list[dict[str, Any]] = []
        for idx, score in indexed[:top_k]:
            if idx < len(chunks):
                c = dict(chunks[idx])
                c["score"] = round(score, 4)
                c["method"] = "rerank"
                out.append(c)
        return out

    @staticmethod
    def _preserve_original(
        chunks: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Fallback: return the original top-K chunks unchanged."""
        return chunks[:top_k]
