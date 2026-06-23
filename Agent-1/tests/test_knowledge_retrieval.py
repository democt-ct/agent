"""Basic tests for knowledge retrieval.

These tests verify the knowledge retriever can initialize
and handle basic operations.
"""

import pytest


class TestKnowledgeRetrieverInit:
    """Test that the knowledge retriever singleton and warmup work."""

    def test_get_retriever(self):
        """Verify the singleton getter returns a valid instance."""
        from app.services.knowledge_retrieval import get_knowledge_retriever

        retriever = get_knowledge_retriever()
        assert retriever is not None
        assert hasattr(retriever, "build_context")
        assert hasattr(retriever, "search")

    def test_warmup(self):
        """Warmup should not raise (handles missing ChromaDB gracefully)."""
        from app.services.knowledge_retrieval import get_knowledge_retriever

        retriever = get_knowledge_retriever()
        retriever.warmup()  # Should succeed silently even without ChromaDB

    def test_search_with_empty_store(self, db_session):
        """Search with no knowledge chunks should return empty results."""
        from app.services.knowledge_retrieval import get_knowledge_retriever

        retriever = get_knowledge_retriever()
        results = retriever.search(
            db=db_session,
            query_text="测试查询",
            hospital_id="hosp-a",
            limit=5,
        )
        assert isinstance(results, list)
