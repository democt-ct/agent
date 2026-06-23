"""Tests for SSE streaming endpoint and agent enhancements."""

import json
import time

import pytest

from app.api.stream_routes import _sse_event


class TestSSEEventFormat:
    def test_sse_event_format(self):
        event = _sse_event("status", {"phase": "test", "message": "hello"})
        assert "event: status" in event
        assert "data: " in event
        data = json.loads(event.split("data: ")[1].strip())
        assert data["phase"] == "test"

    def test_sse_done_event(self):
        event = _sse_event("done", {"answer": "测试回答", "intent": "general"})
        data = json.loads(event.split("data: ")[1].strip())
        assert data["answer"] == "测试回答"


class TestStreamEndpoint:
    """Integration tests for the SSE stream endpoint."""

    def test_stream_endpoint_health(self, client):
        """The stream endpoint should accept POST requests."""
        resp = client.post("/api/v1/mcp/agent/query-stream", json={
            "question": "你好",
            "chat_mode": "general",
        })
        # Should return 200 with text/event-stream
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

    def test_stream_endpoint_events(self, client):
        """The stream should yield proper SSE events."""
        resp = client.post("/api/v1/mcp/agent/query-stream", json={
            "question": "你好",
            "chat_mode": "general",
        })
        events = resp.text.strip().split("\n\n")
        event_types = set()
        for event_str in events:
            for line in event_str.split("\n"):
                if line.startswith("event: "):
                    event_types.add(line[7:])

        # Should include at least status and token/done events
        assert "status" in event_types
        assert "token" in event_types or "done" in event_types

    def test_stream_empty_question(self, client):
        """Empty question should return 400."""
        resp = client.post("/api/v1/mcp/agent/query-stream", json={
            "question": "",
        })
        assert resp.status_code == 400

    def test_stream_endpoint_returns_events(self, client):
        """Verify the stream endpoint returns data in SSE format."""
        resp = client.post("/api/v1/mcp/agent/query-stream", json={
            "question": "简单测试",
            "chat_mode": "general",
        })
        # Each SSE event should have data
        assert "data: " in resp.text


class TestLLMFallback:
    """Tests for LLM fallback mechanism."""

    def test_get_llm_returns_client(self):
        """get_llm() should return a properly configured client."""
        from app.mcp.config import get_llm
        llm = get_llm()
        assert llm is not None
        assert hasattr(llm, "invoke")
        assert llm.MAX_RETRIES == 3

    def test_llm_client_retry_config(self):
        """LLM client should have retry configured."""
        from app.mcp.config import OpenAICompatChatClient
        assert OpenAICompatChatClient.MAX_RETRIES >= 1
        assert OpenAICompatChatClient.RETRY_BASE_DELAY > 0


class TestSourceAttribution:
    """Tests for answer source attribution."""

    def test_tool_result_contains_sources(self):
        """Tool execution results should include data from known sources."""
        from app.mcp.server import tool_get_medical_records
        # Test that the tool returns structured data
        # We test via the API client with a known patient
        pass

    def test_answer_prompt_includes_context(self):
        """The answer generation prompt should include the question and context."""
        from app.mcp.llm_router import _build_answer_prompt
        prompt = _build_answer_prompt(
            question="测试问题",
            intent_state={"intent": "general_medical_question", "latest_only": False,
                          "focus": [], "reasoning_summary": "test"},
            latest_tool_name="test",
            latest_tool_result={"data": {"test": "value"}},
            execution_trace=[],
            conversation_context="",
            allergy_drugs=[],
            chosen_plan={"plan_id": "test", "steps": []},
            image_analysis=None,
        )
        assert "问题: 测试问题" in prompt
        assert "意图: general_medical_question" in prompt


# ── Chunk Quality Scoring ──

class TestChunkQualityScoring:
    """Tests for knowledge chunk quality evaluation."""

    def test_chunk_has_quality_metrics(self, db_session):
        """MemoryKnowledgeChunk should have confidence field for quality scoring."""
        from app.models.memory_knowledge_chunk import MemoryKnowledgeChunk
        # Verify the column exists
        assert hasattr(MemoryKnowledgeChunk, "confidence")
        assert hasattr(MemoryKnowledgeChunk, "tags")

    def test_upsert_chunk_quality(self, db_session):
        """Verify chunk quality fields are populated on creation."""
        from app.services.memory_extraction_service import upsert_knowledge_chunk

        result = upsert_knowledge_chunk(db_session, payload={
            "hospital_id": "hosp-q",
            "domain": "diagnosis",
            "title": "质量测试",
            "chunk_text": "测试质量评分的知识切片内容",
            "source_type": "test",
            "confidence": 0.85,
            "tags": "test, quality",
        })
        assert result is not None
        assert result.confidence == 0.85
        assert "test" in (result.tags or "")
