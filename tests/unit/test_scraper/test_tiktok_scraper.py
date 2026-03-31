"""Unit tests for TikTok scraper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scraper.tiktok_scraper import (
    TikTokScraper,
    MockTikTokScraper,
    ScraperError,
    ProfileNotFoundError,
)


class TestTikTokScraper:
    """Tests for TikTokScraper."""

    def test_build_profile_url(self):
        """Test profile URL building."""
        scraper = TikTokScraper.__new__(TikTokScraper)
        scraper.TIKTOK_BASE_URL = "https://www.tiktok.com"

        assert scraper._build_profile_url("user") == "https://www.tiktok.com/@user"
        assert scraper._build_profile_url("@user") == "https://www.tiktok.com/@user"

    def test_parse_stat_number_plain(self):
        """Test parsing plain numbers."""
        assert TikTokScraper._parse_stat_number("1000") == 1000
        assert TikTokScraper._parse_stat_number("1,000") == 1000

    def test_parse_stat_number_k(self):
        """Test parsing K-suffixed numbers."""
        assert TikTokScraper._parse_stat_number("1.5K") == 1500
        assert TikTokScraper._parse_stat_number("500K") == 500_000

    def test_parse_stat_number_m(self):
        """Test parsing M-suffixed numbers."""
        assert TikTokScraper._parse_stat_number("1.5M") == 1_500_000
        assert TikTokScraper._parse_stat_number("25M") == 25_000_000

    def test_parse_stat_number_b(self):
        """Test parsing B-suffixed numbers."""
        assert TikTokScraper._parse_stat_number("1B") == 1_000_000_000
        assert TikTokScraper._parse_stat_number("2.5B") == 2_500_000_000

    def test_parse_stat_number_invalid(self):
        """Test parsing invalid numbers."""
        assert TikTokScraper._parse_stat_number("abc") == 0
        assert TikTokScraper._parse_stat_number("") == 0

    def test_parse_user_from_universal_data(self):
        """Test parsing user data from TikTok's universal data format."""
        scraper = TikTokScraper.__new__(TikTokScraper)
        scraper.TIKTOK_BASE_URL = "https://www.tiktok.com"

        data = {
            "__DEFAULT_SCOPE__": {
                "webapp.user-detail": {
                    "userInfo": {
                        "user": {
                            "uniqueId": "testuser",
                            "nickname": "Test User",
                            "signature": "Bio text here",
                            "verified": True,
                            "region": "US",
                            "avatarLarger": "https://example.com/avatar.jpg",
                        },
                        "stats": {
                            "followerCount": 100000,
                            "followingCount": 500,
                            "heartCount": 5000000,
                            "videoCount": 200,
                        },
                    }
                }
            }
        }

        user_info = scraper._parse_user_from_universal_data(data)
        assert user_info is not None
        assert user_info.username == "testuser"
        assert user_info.display_name == "Test User"
        assert user_info.bio == "Bio text here"
        assert user_info.is_verified is True
        assert user_info.stats.followers == 100_000
        assert user_info.stats.following == 500
        assert user_info.stats.likes == 5_000_000

    def test_parse_user_from_universal_data_empty(self):
        """Test parsing with empty data returns None."""
        scraper = TikTokScraper.__new__(TikTokScraper)
        result = scraper._parse_user_from_universal_data({})
        assert result is None

    def test_parse_user_from_html_data(self):
        """Test parsing from HTML-extracted data."""
        scraper = TikTokScraper.__new__(TikTokScraper)
        scraper.TIKTOK_BASE_URL = "https://www.tiktok.com"

        data = {
            "username": "htmluser",
            "display_name": "HTML User",
            "bio": "Extracted from HTML",
            "stats_followers": 50000,
            "stats_following": 200,
            "stats_likes": 1000000,
        }

        user_info = scraper._parse_user_from_html_data(data)
        assert user_info is not None
        assert user_info.username == "htmluser"
        assert user_info.stats.followers == 50000

    def test_parse_user_from_html_data_no_username(self):
        """Test HTML parsing with no username returns None."""
        scraper = TikTokScraper.__new__(TikTokScraper)
        scraper.TIKTOK_BASE_URL = "https://www.tiktok.com"
        result = scraper._parse_user_from_html_data({})
        assert result is None

    def test_parse_video_from_data(self):
        """Test video info parsing from page data."""
        scraper = TikTokScraper.__new__(TikTokScraper)

        data = {
            "__DEFAULT_SCOPE__": {
                "webapp.video-detail": {
                    "itemInfo": {
                        "itemStruct": {
                            "id": "12345",
                            "desc": "Test video #test #viral",
                            "challenges": [{"title": "test"}, {"title": "viral"}],
                            "music": {
                                "title": "Song Name",
                                "authorName": "Artist",
                            },
                            "video": {"duration": 30},
                            "stats": {
                                "playCount": 100000,
                                "diggCount": 10000,
                                "commentCount": 500,
                                "shareCount": 200,
                                "collectCount": 100,
                            },
                        }
                    }
                }
            }
        }

        video = scraper._parse_video_from_data(data, "https://tiktok.com/v/12345")
        assert video is not None
        assert video.video_id == "12345"
        assert "test" in video.hashtags
        assert "viral" in video.hashtags
        assert video.stats.views == 100_000
        assert video.music_title == "Song Name"


class TestMockTikTokScraper:
    """Tests for MockTikTokScraper."""

    @pytest.mark.asyncio
    async def test_mock_scraper_returns_data(self):
        """Test that mock scraper returns valid data."""
        scraper = MockTikTokScraper()
        async with scraper:
            data = await scraper.scrape_user("testuser", max_videos=2)

        assert data.user.username == "testuser"
        assert len(data.user.videos) == 2
        assert data.user.stats.followers == 1_500_000
        assert data.is_complete

    @pytest.mark.asyncio
    async def test_mock_scraper_max_videos(self):
        """Test mock scraper respects max_videos."""
        scraper = MockTikTokScraper()
        async with scraper:
            data = await scraper.scrape_user("testuser", max_videos=1)

        assert len(data.user.videos) == 1

    @pytest.mark.asyncio
    async def test_mock_scraper_strips_at(self):
        """Test mock scraper strips @ from username."""
        scraper = MockTikTokScraper()
        async with scraper:
            data = await scraper.scrape_user("@testuser")

        assert data.user.username == "testuser"

    @pytest.mark.asyncio
    async def test_mock_scraper_has_realistic_stats(self):
        """Test mock data has realistic stat values."""
        scraper = MockTikTokScraper()
        async with scraper:
            data = await scraper.scrape_user("creator")

        for video in data.user.videos:
            assert video.stats.views > 0
            assert video.stats.likes > 0
            assert video.stats.engagement_rate > 0
