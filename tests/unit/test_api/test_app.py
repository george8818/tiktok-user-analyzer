"""Unit tests for the FastAPI endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.api.app import app


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health endpoint returns 200."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestAPIModels:
    """Tests for API request/response models."""

    def test_analyze_request_defaults(self):
        """Test AnalyzeRequest default values."""
        from src.api.app import AnalyzeRequest
        req = AnalyzeRequest(username="testuser")
        assert req.max_videos == 2
        assert req.use_mock is False

    def test_analyze_request_custom(self):
        """Test AnalyzeRequest with custom values."""
        from src.api.app import AnalyzeRequest
        req = AnalyzeRequest(username="testuser", max_videos=3, use_mock=True)
        assert req.max_videos == 3
        assert req.use_mock is True

    def test_chat_request(self):
        """Test ChatRequest model."""
        from src.api.app import ChatRequest
        req = ChatRequest(message="What does this user post about?")
        assert req.session_id is None

    def test_chat_request_with_session(self):
        """Test ChatRequest with session ID."""
        from src.api.app import ChatRequest
        req = ChatRequest(message="Follow up", session_id="sess-123")
        assert req.session_id == "sess-123"

    def test_health_response(self):
        """Test HealthResponse model."""
        from src.api.app import HealthResponse
        resp = HealthResponse(status="healthy", version="0.1.0")
        assert resp.status == "healthy"

    def test_analyze_response(self):
        """Test AnalyzeResponse model."""
        from src.api.app import AnalyzeResponse
        resp = AnalyzeResponse(
            username="testuser",
            creator_type="tech",
            niche="coding",
            profile_summary="A tech creator",
            videos_analyzed=2,
            confidence_score=0.8,
            primary_topics=["tech", "coding"],
        )
        assert resp.username == "testuser"
        assert resp.confidence_score == 0.8

    def test_chat_response(self):
        """Test ChatResponse model."""
        from src.api.app import ChatResponse
        resp = ChatResponse(
            response="This user creates tech content.",
            session_id="sess-123",
            turn_count=1,
            follow_up_suggestions=["What are their top videos?"],
        )
        assert resp.turn_count == 1
        assert len(resp.follow_up_suggestions) == 1

    def test_profile_list_item(self):
        """Test ProfileListItem model."""
        from src.api.app import ProfileListItem
        item = ProfileListItem(
            username="testuser",
            creator_type="tech",
            niche="coding",
            videos_analyzed=2,
        )
        assert item.updated_at is None
