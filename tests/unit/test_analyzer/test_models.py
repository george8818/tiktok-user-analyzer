"""Unit tests for analyzer data models."""

import pytest
from datetime import datetime

from src.analyzer.models import (
    FrameAnalysis,
    VideoAnalysisResult,
    UserProfile,
    ContentPattern,
    AudienceSegment,
    BrandPersonality,
)


class TestFrameAnalysis:
    """Tests for FrameAnalysis model."""

    def test_creation(self, sample_frame_analysis):
        """Test basic creation."""
        assert sample_frame_analysis.frame_index == 0
        assert "monitors" in sample_frame_analysis.objects_detected
        assert "office" in sample_frame_analysis.setting.lower()

    def test_minimal_creation(self):
        """Test creation with minimal fields."""
        fa = FrameAnalysis(frame_index=0, scene_description="A scene")
        assert fa.objects_detected == []
        assert fa.text_detected == ""


class TestVideoAnalysisResult:
    """Tests for VideoAnalysisResult model."""

    def test_complete_analysis(self, sample_video_analysis):
        """Test a complete video analysis object."""
        assert sample_video_analysis.video_id == "7321456789012345678"
        assert sample_video_analysis.content_category == "lifestyle"
        assert "tech life" in sample_video_analysis.content_themes
        assert sample_video_analysis.views == 250_000

    def test_engagement_hooks(self, sample_video_analysis):
        """Test engagement hooks are populated."""
        assert len(sample_video_analysis.engagement_hooks) > 0

    def test_default_values(self):
        """Test default values for optional fields."""
        result = VideoAnalysisResult(
            video_id="test",
            content_summary="Test",
            content_category="test",
        )
        assert result.has_voiceover is False
        assert result.has_dialogue is False
        assert result.views == 0
        assert result.hashtags == []


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_complete_profile(self, sample_user_profile):
        """Test a complete user profile."""
        assert sample_user_profile.username == "testuser"
        assert sample_user_profile.creator_type == "lifestyle/tech"
        assert sample_user_profile.videos_analyzed == 2
        assert sample_user_profile.confidence_score == 0.78

    def test_to_context_string(self, sample_user_profile):
        """Test context string generation for agent."""
        context = sample_user_profile.to_context_string()

        # Should contain key sections
        assert "@testuser" in context
        assert "Profile Summary" in context
        assert "Creator Classification" in context
        assert "Topics & Themes" in context
        assert "Content Patterns" in context
        assert "Audience Segments" in context
        assert "Brand Personality" in context
        assert "Engagement & Growth" in context
        assert "Strengths" in context
        assert "Video Analysis Details" in context

    def test_to_context_string_includes_video_details(self, sample_user_profile):
        """Test that context string includes video-level details."""
        context = sample_user_profile.to_context_string()
        assert "7321456789012345678" in context
        assert "lifestyle" in context.lower()

    def test_profile_primary_topics(self, sample_user_profile):
        """Test primary topics list."""
        assert "tech" in sample_user_profile.primary_topics
        assert "cooking" in sample_user_profile.primary_topics

    def test_brand_personality(self, sample_user_profile):
        """Test brand personality data."""
        bp = sample_user_profile.brand_personality
        assert bp is not None
        assert bp.primary_archetype == "The Creator"
        assert "authenticity" in bp.values

    def test_content_patterns(self, sample_user_profile):
        """Test content patterns."""
        patterns = sample_user_profile.content_patterns
        assert len(patterns) == 2
        assert patterns[0].pattern_type == "theme"

    def test_audience_segments(self, sample_user_profile):
        """Test audience segments."""
        segments = sample_user_profile.audience_segments
        assert len(segments) == 2
        assert segments[0].segment_name == "Young Tech Professionals"

    def test_profile_minimal(self):
        """Test profile with minimal fields."""
        profile = UserProfile(
            username="minimal",
            profile_summary="A minimal profile",
            creator_type="unknown",
            niche="general",
            primary_topics=["general"],
            content_format="short video",
            posting_style="casual",
        )
        assert profile.videos_analyzed == 0
        assert profile.confidence_score == 0.0
        context = profile.to_context_string()
        assert "@minimal" in context


class TestContentPattern:
    """Tests for ContentPattern model."""

    def test_creation(self):
        """Test pattern creation."""
        pattern = ContentPattern(
            pattern_type="theme",
            description="Recurring cooking content",
            frequency="weekly",
            examples=["recipe video", "kitchen tour"],
        )
        assert pattern.pattern_type == "theme"
        assert len(pattern.examples) == 2


class TestAudienceSegment:
    """Tests for AudienceSegment model."""

    def test_creation(self):
        """Test segment creation."""
        segment = AudienceSegment(
            segment_name="Gen Z Creators",
            age_range="18-24",
            interests=["content creation", "social media"],
            engagement_level="high",
            description="Young aspiring creators",
        )
        assert segment.segment_name == "Gen Z Creators"


class TestBrandPersonality:
    """Tests for BrandPersonality model."""

    def test_creation(self):
        """Test brand personality creation."""
        bp = BrandPersonality(
            primary_archetype="The Creator",
            secondary_archetype="The Explorer",
            tone_of_voice="casual and fun",
            values=["creativity", "authenticity"],
            differentiators=["unique perspective"],
        )
        assert bp.primary_archetype == "The Creator"
        assert len(bp.values) == 2
