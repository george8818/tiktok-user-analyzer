"""
System tests for the TikTok User Analyzer.

Tests the full system behavior including API endpoints,
pipeline orchestration, and error handling.
"""

import os
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from src.api.app import app, _pipeline, _agents
from src.config import Settings
from src.pipeline import AnalysisPipeline


class TestSystemHealth:
    """System-level health and configuration tests."""

    @pytest.mark.asyncio
    async def test_api_health_endpoint(self):
        """Test the API health endpoint returns correct response."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "0.1.0"

    def test_environment_configuration(self):
        """Test that environment variables are properly handled."""
        # Test default values
        os.environ.pop("SCRAPER_TIMEOUT", None)
        from src.config import ScraperSettings
        settings = ScraperSettings()
        assert settings.timeout == 30  # Default

    def test_settings_initialization(self, tmp_path):
        """Test settings initialization creates required directories."""
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test.db"
        os.environ["MEDIA_DIR"] = str(tmp_path / "media")
        os.environ["REPORTS_DIR"] = str(tmp_path / "reports")

        from src.config import StorageSettings
        storage = StorageSettings()
        storage.ensure_dirs()

        assert (tmp_path / "media").exists()
        assert (tmp_path / "reports").exists()


class TestSystemPipeline:
    """System tests for the analysis pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, tmp_path):
        """Test pipeline can be initialized."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/sys_test.db"

        settings = Settings()
        settings.storage.database_url = f"sqlite+aiosqlite:///{tmp_path}/sys_test.db"

        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()
        assert pipeline._initialized

        profiles = await pipeline.get_cached_profiles()
        assert isinstance(profiles, list)

        await pipeline.close()

    @pytest.mark.asyncio
    async def test_pipeline_mock_analysis(self, tmp_path):
        """Test full pipeline with mock scraper."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key"

        settings = Settings()
        settings.storage.database_url = f"sqlite+aiosqlite:///{tmp_path}/mock_test.db"

        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()

        # Mock the LLM calls
        mock_profile_json = {
            "profile_summary": "A test creator with diverse content.",
            "creator_type": "lifestyle",
            "niche": "general",
            "estimated_influence_tier": "macro",
            "primary_topics": ["lifestyle", "tech"],
            "content_format": "short vlogs",
            "posting_style": "casual",
            "content_patterns": [],
            "audience_segments": [],
            "primary_audience_description": "Young adults",
            "brand_personality": None,
            "engagement_strategy": "Trending content",
            "community_building": "Comment engagement",
            "growth_potential": "High",
            "strengths": ["Diverse content"],
            "areas_for_improvement": ["Consistency"],
            "collaboration_opportunities": ["Brands"],
            "confidence_score": 0.75,
        }

        mock_video_json = {
            "content_summary": "A lifestyle vlog",
            "content_category": "lifestyle",
            "content_themes": ["daily life"],
            "tone": "casual",
            "target_audience": "young adults",
            "engagement_hooks": ["relatable content"],
        }

        import json
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text")]

        # Alternate between video and profile responses
        call_count = {"n": 0}

        def mock_create(**kwargs):
            call_count["n"] += 1
            resp = MagicMock()
            if call_count["n"] <= 2:
                resp.content = [MagicMock(type="text", text=json.dumps(mock_video_json))]
            else:
                resp.content = [MagicMock(type="text", text=json.dumps(mock_profile_json))]
            return resp

        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.side_effect = mock_create
            instance.api_key = "sk-ant-test-key"

            profile = await pipeline.analyze_user(
                username="system_test_user",
                max_videos=2,
                use_mock=True,
                skip_download=True,
            )

        assert profile is not None
        assert profile.username == "system_test_user"

        await pipeline.close()


class TestSystemErrorHandling:
    """System tests for error handling."""

    @pytest.mark.asyncio
    async def test_api_404_for_unknown_profile(self):
        """Test API returns 404 for unknown profiles."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/profiles/nonexistent_user_12345")

        # Should return 404 or 503 (if pipeline not initialized)
        assert response.status_code in (404, 503)

    @pytest.mark.asyncio
    async def test_api_handles_missing_pipeline(self):
        """Test API gracefully handles missing pipeline."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/profiles")

        # Should return 503 if pipeline not initialized, or 200 if it is
        assert response.status_code in (200, 503)

    def test_config_missing_api_key(self):
        """Test configuration handles missing API key."""
        from src.config import LLMSettings
        from pydantic import ValidationError

        saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValidationError):
                LLMSettings(ANTHROPIC_API_KEY="")
        finally:
            if saved_key:
                os.environ["ANTHROPIC_API_KEY"] = saved_key
