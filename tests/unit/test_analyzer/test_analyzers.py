"""Unit tests for video analyzer and profile generator."""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from src.analyzer.video_analyzer import VideoAnalyzer, VideoAnalysisError
from src.analyzer.profile_generator import ProfileGenerator, ProfileGenerationError


class TestVideoAnalyzer:
    """Tests for VideoAnalyzer."""

    def test_clean_json_response_markdown(self):
        """Test cleaning JSON from markdown code blocks."""
        text = '```json\n{"key": "value"}\n```'
        result = VideoAnalyzer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_response_plain(self):
        """Test cleaning already clean JSON."""
        text = '{"key": "value"}'
        result = VideoAnalyzer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_clean_json_response_triple_backticks(self):
        """Test cleaning with only triple backticks."""
        text = '```\n{"key": "value"}\n```'
        result = VideoAnalyzer._clean_json_response(text)
        assert result == '{"key": "value"}'

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        analyzer = VideoAnalyzer(api_key="test-key")
        assert analyzer.model == "claude-sonnet-4-20250514"
        assert analyzer.vision_model == "claude-sonnet-4-20250514"
        assert analyzer.max_tokens == 4096

    def test_init_with_custom_model(self):
        """Test initialization with custom models."""
        analyzer = VideoAnalyzer(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            vision_model="claude-sonnet-4-20250514",
        )
        assert analyzer.model == "claude-sonnet-4-20250514"
        assert analyzer.vision_model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_analyze_frames_empty(self):
        """Test analyzing empty frame list."""
        analyzer = VideoAnalyzer(api_key="test-key")
        result = await analyzer.analyze_frames([])
        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_video_with_mock_client(
        self, sample_video_info, tmp_path
    ):
        """Test video analysis with mocked API client."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(
            type="text",
            text=json.dumps({
                "content_summary": "Test video summary",
                "content_category": "tech",
                "content_subcategories": ["coding"],
                "content_themes": ["programming"],
                "production_quality": "professional",
                "editing_style": "quick cuts",
                "visual_aesthetic": "modern",
                "music_mood": "chill",
                "has_voiceover": True,
                "has_dialogue": False,
                "target_audience": "developers",
                "tone": "educational",
                "engagement_hooks": ["tutorial"],
                "call_to_action": "Follow for more",
            }),
        )]

        analyzer = VideoAnalyzer(api_key="test-key")
        analyzer.client = MagicMock()
        analyzer.client.messages.create.return_value = mock_response

        result = await analyzer.analyze_video(sample_video_info, [])
        assert result.content_category == "tech"
        assert result.video_id == sample_video_info.video_id


class TestProfileGenerator:
    """Tests for ProfileGenerator."""

    def test_clean_json_response(self):
        """Test JSON cleaning."""
        text = '```json\n{"test": true}\n```'
        assert ProfileGenerator._clean_json_response(text) == '{"test": true}'

    def test_estimate_influence_tier_mega(self):
        """Test mega tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(5_000_000) == "mega"

    def test_estimate_influence_tier_macro(self):
        """Test macro tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(750_000) == "macro"

    def test_estimate_influence_tier_mid(self):
        """Test mid-tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(200_000) == "mid-tier"

    def test_estimate_influence_tier_micro(self):
        """Test micro tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(50_000) == "micro"

    def test_estimate_influence_tier_nano(self):
        """Test nano tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(5_000) == "nano"

    def test_estimate_influence_tier_aspiring(self):
        """Test aspiring tier classification."""
        gen = ProfileGenerator(api_key="test-key")
        assert gen.estimate_influence_tier(500) == "aspiring"

    def test_parse_content_patterns(self):
        """Test parsing content patterns from JSON."""
        data = [
            {
                "pattern_type": "theme",
                "description": "Recurring pattern",
                "frequency": "weekly",
                "examples": ["example1"],
            }
        ]
        patterns = ProfileGenerator._parse_content_patterns(data)
        assert len(patterns) == 1
        assert patterns[0].pattern_type == "theme"

    def test_parse_audience_segments(self):
        """Test parsing audience segments from JSON."""
        data = [
            {
                "segment_name": "Young Pros",
                "age_range": "25-35",
                "interests": ["tech"],
                "engagement_level": "high",
                "description": "Tech professionals",
            }
        ]
        segments = ProfileGenerator._parse_audience_segments(data)
        assert len(segments) == 1
        assert segments[0].segment_name == "Young Pros"

    def test_parse_brand_personality(self):
        """Test parsing brand personality."""
        data = {
            "primary_archetype": "The Creator",
            "secondary_archetype": "The Explorer",
            "tone_of_voice": "casual",
            "values": ["authenticity"],
            "differentiators": ["unique voice"],
        }
        bp = ProfileGenerator._parse_brand_personality(data)
        assert bp is not None
        assert bp.primary_archetype == "The Creator"

    def test_parse_brand_personality_none(self):
        """Test parsing None brand personality."""
        result = ProfileGenerator._parse_brand_personality(None)
        assert result is None

    def test_format_video_analysis(self, sample_video_analysis):
        """Test video analysis formatting for prompt."""
        gen = ProfileGenerator(api_key="test-key")
        text = gen._format_video_analysis(sample_video_analysis)
        assert "7321456789012345678" in text
        assert "lifestyle" in text
        assert "250,000" in text
