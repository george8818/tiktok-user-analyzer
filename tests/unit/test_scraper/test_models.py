"""Unit tests for scraper data models."""

import pytest
from datetime import datetime

from src.scraper.models import (
    TikTokVideoStats,
    TikTokVideoInfo,
    TikTokUserStats,
    TikTokUserInfo,
    ScrapedData,
    VideoPrivacyLevel,
)


class TestTikTokVideoStats:
    """Tests for TikTokVideoStats model."""

    def test_engagement_rate_calculation(self, sample_video_stats):
        """Test engagement rate is correctly calculated."""
        expected = (35_000 + 1_200 + 800) / 250_000
        assert abs(sample_video_stats.engagement_rate - expected) < 0.0001

    def test_engagement_rate_zero_views(self):
        """Test engagement rate with zero views."""
        stats = TikTokVideoStats(views=0, likes=10)
        assert stats.engagement_rate == 0.0

    def test_engagement_summary_very_high(self):
        """Test very high engagement label."""
        stats = TikTokVideoStats(views=100, likes=50, comments=20, shares=10)
        assert "Very High" in stats.engagement_summary

    def test_engagement_summary_low(self):
        """Test low engagement label."""
        stats = TikTokVideoStats(views=100_000, likes=100, comments=10, shares=5)
        assert "Low" in stats.engagement_summary

    def test_default_values(self):
        """Test default stat values are zero."""
        stats = TikTokVideoStats()
        assert stats.views == 0
        assert stats.likes == 0
        assert stats.comments == 0
        assert stats.shares == 0
        assert stats.bookmarks == 0


class TestTikTokVideoInfo:
    """Tests for TikTokVideoInfo model."""

    def test_hashtag_string(self, sample_video_info):
        """Test hashtag formatting."""
        hashtag_str = sample_video_info.hashtag_string
        assert "#tech" in hashtag_str
        assert "#coding" in hashtag_str

    def test_hashtag_string_empty(self):
        """Test empty hashtags."""
        video = TikTokVideoInfo(video_id="test", url="https://example.com")
        assert video.hashtag_string == ""

    def test_to_analysis_text_complete(self, sample_video_info):
        """Test full analysis text generation."""
        text = sample_video_info.to_analysis_text()
        assert "7321456789012345678" in text
        assert "Day in my life" in text
        assert "#tech" in text
        assert "250000 views" in text
        assert "Chill Lo-fi Beat" in text

    def test_to_analysis_text_minimal(self):
        """Test analysis text with minimal data."""
        video = TikTokVideoInfo(video_id="test", url="https://example.com")
        text = video.to_analysis_text()
        assert "Video ID: test" in text

    def test_privacy_level_default(self, sample_video_info):
        """Test default privacy level."""
        assert sample_video_info.privacy_level == VideoPrivacyLevel.PUBLIC

    def test_is_ad_default(self, sample_video_info):
        """Test default ad flag."""
        assert sample_video_info.is_ad is False


class TestTikTokUserStats:
    """Tests for TikTokUserStats model."""

    def test_follower_ratio(self, sample_user_stats):
        """Test follower ratio calculation."""
        assert sample_user_stats.follower_ratio == 1_500_000 / 500

    def test_follower_ratio_zero_following(self):
        """Test follower ratio when following zero accounts."""
        stats = TikTokUserStats(followers=1000, following=0)
        assert stats.follower_ratio == 1000.0

    def test_avg_likes_per_video(self, sample_user_stats):
        """Test average likes calculation."""
        expected = 25_000_000 / 150
        assert abs(sample_user_stats.avg_likes_per_video - expected) < 1

    def test_avg_likes_zero_videos(self):
        """Test average likes with zero videos."""
        stats = TikTokUserStats(likes=1000, video_count=0)
        assert stats.avg_likes_per_video == 0.0


class TestTikTokUserInfo:
    """Tests for TikTokUserInfo model."""

    def test_video_count(self, sample_user_info):
        """Test video count property."""
        assert sample_user_info.video_count == 2

    def test_to_analysis_text(self, sample_user_info):
        """Test user analysis text generation."""
        text = sample_user_info.to_analysis_text()
        assert "@testuser" in text
        assert "Test Creator" in text
        assert "1,500,000" in text
        assert "Video 1" in text
        assert "Video 2" in text

    def test_verified_flag(self, sample_user_info):
        """Test verified user flag in analysis text."""
        text = sample_user_info.to_analysis_text()
        assert "Verified: Yes" in text


class TestScrapedData:
    """Tests for ScrapedData model."""

    def test_is_complete_with_data(self, sample_scraped_data):
        """Test completeness check with valid data."""
        assert sample_scraped_data.is_complete is True

    def test_is_complete_with_errors(self, sample_user_info):
        """Test completeness check with errors."""
        data = ScrapedData(
            user=sample_user_info,
            errors=["some error"],
        )
        assert data.is_complete is False

    def test_is_complete_no_videos(self, sample_user_stats):
        """Test completeness check with no videos."""
        user = TikTokUserInfo(
            username="empty",
            profile_url="https://tiktok.com/@empty",
            stats=sample_user_stats,
            videos=[],
        )
        data = ScrapedData(user=user)
        assert data.is_complete is False

    def test_frame_count(self):
        """Test frame count calculation."""
        data = ScrapedData(
            user=TikTokUserInfo(username="test", profile_url="https://example.com"),
            video_frames={
                "vid1": ["/path/frame1.jpg", "/path/frame2.jpg"],
                "vid2": ["/path/frame3.jpg"],
            },
        )
        assert data.frame_count == 3

    def test_frame_count_empty(self, sample_scraped_data):
        """Test frame count with no frames."""
        assert sample_scraped_data.frame_count == 0
