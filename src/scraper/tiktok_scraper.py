"""
TikTok Profile Scraper using Playwright browser automation.

Extracts user profile information and video metadata from TikTok.
Uses headless browser to render JavaScript-heavy TikTok pages.
"""

import asyncio
import json
import re
import time
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.logging_config import get_logger
from src.scraper.models import (
    TikTokUserInfo,
    TikTokUserStats,
    TikTokVideoInfo,
    TikTokVideoStats,
    ScrapedData,
)

logger = get_logger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors."""


class ProfileNotFoundError(ScraperError):
    """Raised when a TikTok profile is not found."""


class RateLimitError(ScraperError):
    """Raised when TikTok rate limits the request."""


class TikTokScraper:
    """
    Scrapes TikTok user profiles and video metadata using Playwright.

    This scraper uses headless browser automation to extract data from
    TikTok's JavaScript-rendered pages. It implements retry logic,
    rate limiting, and graceful error handling.

    Usage:
        scraper = TikTokScraper(headless=True, timeout=30)
        async with scraper:
            data = await scraper.scrape_user("username", max_videos=2)
    """

    TIKTOK_BASE_URL = "https://www.tiktok.com"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        browser_type: str = "chromium",
        headless: bool = True,
        timeout: int = 30,
        max_retries: int = 3,
        request_delay: float = 2.0,
    ):
        self.browser_type = browser_type
        self.headless = headless
        self.timeout = timeout * 1000  # Convert to milliseconds for Playwright
        self.max_retries = max_retries
        self.request_delay = request_delay
        self._browser = None
        self._context = None
        self._playwright = None

    async def __aenter__(self) -> "TikTokScraper":
        """Initialize browser on context entry."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser on context exit."""
        await self._close_browser()

    async def _init_browser(self) -> None:
        """Initialize the Playwright browser instance."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        browser_launcher = getattr(self._playwright, self.browser_type)
        self._browser = await browser_launcher.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        self._context = await self._browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Block unnecessary resources for faster scraping
        await self._context.route(
            re.compile(r"\.(mp4|webm|ogg|mp3|wav|flac)$"),
            lambda route: route.abort(),
        )

        logger.info(
            "browser_initialized",
            browser_type=self.browser_type,
            headless=self.headless,
        )

    async def _close_browser(self) -> None:
        """Close the browser and cleanup resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("browser_closed")

    def _build_profile_url(self, username: str) -> str:
        """Build the full profile URL for a username."""
        clean_username = username.lstrip("@")
        return f"{self.TIKTOK_BASE_URL}/@{clean_username}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def _fetch_page_data(self, url: str) -> dict:
        """
        Navigate to a URL and extract the SIGI_STATE or __UNIVERSAL_DATA_FOR_REHYDRATION__
        JSON data embedded in TikTok pages.

        Args:
            url: The TikTok URL to scrape

        Returns:
            Dictionary of extracted page data

        Raises:
            ProfileNotFoundError: If the profile doesn't exist
            RateLimitError: If rate limited by TikTok
            ScraperError: For other scraping failures
        """
        if not self._context:
            raise ScraperError("Browser not initialized. Use 'async with' context manager.")

        page = await self._context.new_page()
        try:
            logger.info("navigating_to_url", url=url)

            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            if response and response.status == 404:
                raise ProfileNotFoundError(f"Profile not found: {url}")
            if response and response.status == 429:
                raise RateLimitError("Rate limited by TikTok")
            if response and response.status >= 400:
                raise ScraperError(f"HTTP error {response.status} for {url}")

            # Wait for page content to load
            await page.wait_for_load_state("networkidle", timeout=self.timeout)

            # Try to extract embedded JSON data
            page_data = await self._extract_page_json(page)

            if not page_data:
                # Fallback: try to extract from HTML directly
                page_data = await self._extract_from_html(page)

            return page_data

        finally:
            await page.close()
            # Respect rate limiting
            await asyncio.sleep(self.request_delay)

    async def _extract_page_json(self, page) -> Optional[dict]:
        """
        Extract the embedded JSON state from TikTok's page.
        TikTok embeds user/video data in script tags as JSON.
        """
        selectors = [
            'script#__UNIVERSAL_DATA_FOR_REHYDRATION__',
            'script#SIGI_STATE',
            'script#__NEXT_DATA__',
        ]

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    content = await element.inner_text()
                    data = json.loads(content)
                    logger.info("extracted_json_state", selector=selector)
                    return data
            except (json.JSONDecodeError, Exception) as e:
                logger.debug("json_extraction_failed", selector=selector, error=str(e))
                continue

        return None

    async def _extract_from_html(self, page) -> dict:
        """
        Fallback: Extract user data directly from HTML elements.
        Used when embedded JSON is not available.
        """
        data = {}

        try:
            # Extract username
            title = await page.title()
            if title:
                match = re.search(r"@(\w+)", title)
                if match:
                    data["username"] = match.group(1)

            # Extract bio
            bio_el = await page.query_selector('[data-e2e="user-bio"]')
            if bio_el:
                data["bio"] = await bio_el.inner_text()

            # Extract display name
            name_el = await page.query_selector('[data-e2e="user-subtitle"]')
            if not name_el:
                name_el = await page.query_selector('h1[data-e2e="user-title"]')
            if name_el:
                data["display_name"] = await name_el.inner_text()

            # Extract stats
            stats_selectors = {
                "following": '[data-e2e="following-count"]',
                "followers": '[data-e2e="followers-count"]',
                "likes": '[data-e2e="likes-count"]',
            }
            for stat_name, selector in stats_selectors.items():
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    data[f"stats_{stat_name}"] = self._parse_stat_number(text)

            # Extract video links
            video_links = await page.query_selector_all('[data-e2e="user-post-item"] a')
            data["video_urls"] = []
            for link in video_links[:10]:  # Limit to 10 videos
                href = await link.get_attribute("href")
                if href:
                    data["video_urls"].append(href)

            logger.info("extracted_from_html", fields=list(data.keys()))

        except Exception as e:
            logger.warning("html_extraction_error", error=str(e))

        return data

    @staticmethod
    def _parse_stat_number(text: str) -> int:
        """
        Parse TikTok's abbreviated stat numbers (e.g., '1.2M', '500K').

        Args:
            text: The text representation of the number

        Returns:
            Integer value of the stat
        """
        text = text.strip().upper()
        multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

        for suffix, multiplier in multipliers.items():
            if text.endswith(suffix):
                try:
                    return int(float(text[:-1]) * multiplier)
                except ValueError:
                    return 0

        try:
            return int(text.replace(",", ""))
        except ValueError:
            return 0

    def _parse_user_from_universal_data(self, data: dict) -> Optional[TikTokUserInfo]:
        """Parse user info from __UNIVERSAL_DATA_FOR_REHYDRATION__ format."""
        try:
            # Navigate the nested structure
            default_scope = data.get("__DEFAULT_SCOPE__", {})
            user_detail = default_scope.get("webapp.user-detail", {})
            user_info = user_detail.get("userInfo", {})

            if not user_info:
                return None

            user = user_info.get("user", {})
            stats = user_info.get("stats", {})

            return TikTokUserInfo(
                username=user.get("uniqueId", ""),
                display_name=user.get("nickname", ""),
                bio=user.get("signature", ""),
                avatar_url=user.get("avatarLarger", user.get("avatarMedium", "")),
                profile_url=f"{self.TIKTOK_BASE_URL}/@{user.get('uniqueId', '')}",
                is_verified=user.get("verified", False),
                region=user.get("region", None),
                stats=TikTokUserStats(
                    followers=stats.get("followerCount", 0),
                    following=stats.get("followingCount", 0),
                    likes=stats.get("heartCount", stats.get("heart", 0)),
                    video_count=stats.get("videoCount", 0),
                ),
            )
        except Exception as e:
            logger.error("user_parse_error", error=str(e), data_keys=list(data.keys()))
            return None

    def _parse_user_from_html_data(self, data: dict) -> Optional[TikTokUserInfo]:
        """Parse user info from HTML-extracted data."""
        username = data.get("username", "")
        if not username:
            return None

        return TikTokUserInfo(
            username=username,
            display_name=data.get("display_name", username),
            bio=data.get("bio", ""),
            profile_url=self._build_profile_url(username),
            stats=TikTokUserStats(
                followers=data.get("stats_followers", 0),
                following=data.get("stats_following", 0),
                likes=data.get("stats_likes", 0),
            ),
        )

    async def _scrape_video_page(self, video_url: str) -> Optional[TikTokVideoInfo]:
        """
        Scrape metadata for a single video page.

        Args:
            video_url: Full URL to the TikTok video

        Returns:
            TikTokVideoInfo or None if scraping fails
        """
        try:
            data = await self._fetch_page_data(video_url)

            # Try to parse from universal data
            video_info = self._parse_video_from_data(data, video_url)
            if video_info:
                return video_info

            # Fallback: create basic info from URL
            video_id = video_url.rstrip("/").split("/")[-1]
            return TikTokVideoInfo(
                video_id=video_id,
                url=video_url,
                description=data.get("description", ""),
            )
        except Exception as e:
            logger.warning("video_scrape_failed", url=video_url, error=str(e))
            return None

    def _parse_video_from_data(self, data: dict, video_url: str) -> Optional[TikTokVideoInfo]:
        """Parse video info from page data."""
        try:
            default_scope = data.get("__DEFAULT_SCOPE__", {})
            video_detail = default_scope.get("webapp.video-detail", {})
            item_info = video_detail.get("itemInfo", {})
            item = item_info.get("itemStruct", {})

            if not item:
                return None

            # Extract hashtags from challenges
            challenges = item.get("challenges", [])
            hashtags = [c.get("title", "") for c in challenges if c.get("title")]

            # Extract text hashtags from description
            desc = item.get("desc", "")
            text_tags = re.findall(r"#(\w+)", desc)
            all_hashtags = list(set(hashtags + text_tags))

            stats_data = item.get("stats", {})
            music = item.get("music", {})

            return TikTokVideoInfo(
                video_id=item.get("id", video_url.rstrip("/").split("/")[-1]),
                url=video_url,
                description=desc,
                hashtags=all_hashtags,
                music_title=music.get("title"),
                music_author=music.get("authorName"),
                duration_seconds=item.get("video", {}).get("duration"),
                stats=TikTokVideoStats(
                    views=stats_data.get("playCount", 0),
                    likes=stats_data.get("diggCount", 0),
                    comments=stats_data.get("commentCount", 0),
                    shares=stats_data.get("shareCount", 0),
                    bookmarks=stats_data.get("collectCount", 0),
                ),
            )
        except Exception as e:
            logger.debug("video_parse_error", error=str(e))
            return None

    async def scrape_user(
        self,
        username: str,
        max_videos: int = 2,
    ) -> ScrapedData:
        """
        Scrape a TikTok user's profile and their recent videos.

        Args:
            username: TikTok username (with or without @)
            max_videos: Maximum number of videos to scrape (default: 2)

        Returns:
            ScrapedData containing user info, video info, and any errors

        Raises:
            ProfileNotFoundError: If the user profile doesn't exist
            ScraperError: For critical scraping failures
        """
        start_time = time.time()
        errors: list[str] = []
        clean_username = username.lstrip("@")

        logger.info("scraping_user", username=clean_username, max_videos=max_videos)

        # Step 1: Scrape user profile
        profile_url = self._build_profile_url(clean_username)
        page_data = await self._fetch_page_data(profile_url)

        # Parse user info
        user_info = self._parse_user_from_universal_data(page_data)
        if not user_info:
            user_info = self._parse_user_from_html_data(page_data)
        if not user_info:
            raise ScraperError(f"Failed to parse user profile for @{clean_username}")

        logger.info(
            "user_profile_scraped",
            username=user_info.username,
            followers=user_info.stats.followers,
        )

        # Step 2: Get video URLs
        video_urls = page_data.get("video_urls", [])
        if not video_urls:
            # Try to extract from universal data
            default_scope = page_data.get("__DEFAULT_SCOPE__", {})
            item_list = default_scope.get("webapp.user-detail", {}).get("itemList", [])
            for item in item_list[:max_videos]:
                vid_id = item.get("id", "")
                if vid_id:
                    video_urls.append(
                        f"{self.TIKTOK_BASE_URL}/@{clean_username}/video/{vid_id}"
                    )

        # Step 3: Scrape individual videos
        videos_to_scrape = video_urls[:max_videos]
        for url in videos_to_scrape:
            try:
                video_info = await self._scrape_video_page(url)
                if video_info:
                    user_info.videos.append(video_info)
            except Exception as e:
                error_msg = f"Failed to scrape video {url}: {str(e)}"
                errors.append(error_msg)
                logger.warning("video_scrape_error", url=url, error=str(e))

        elapsed = time.time() - start_time
        logger.info(
            "scraping_complete",
            username=clean_username,
            videos_scraped=len(user_info.videos),
            errors=len(errors),
            duration_seconds=f"{elapsed:.2f}",
        )

        return ScrapedData(
            user=user_info,
            errors=errors,
            scrape_duration_seconds=elapsed,
        )


class MockTikTokScraper(TikTokScraper):
    """
    Mock scraper for testing and demo purposes.
    Returns realistic synthetic data without actual web scraping.
    """

    def __init__(self, **kwargs):
        # Don't initialize browser for mock
        self.browser_type = kwargs.get("browser_type", "chromium")
        self.headless = True
        self.timeout = 30000
        self.max_retries = 1
        self.request_delay = 0
        self._browser = None
        self._context = None
        self._playwright = None

    async def __aenter__(self) -> "MockTikTokScraper":
        return self

    async def __aexit__(self, *args) -> None:
        pass

    async def scrape_user(
        self,
        username: str,
        max_videos: int = 2,
    ) -> ScrapedData:
        """Return mock data for testing."""
        from datetime import datetime, timedelta

        clean_username = username.lstrip("@")
        start_time = time.time()

        mock_videos = [
            TikTokVideoInfo(
                video_id=f"mock_video_{i}",
                url=f"https://www.tiktok.com/@{clean_username}/video/mock_video_{i}",
                description=self._get_mock_description(i),
                hashtags=self._get_mock_hashtags(i),
                music_title=f"Trending Sound #{i}",
                music_author="Popular Artist",
                duration_seconds=30.0 + i * 15,
                created_at=datetime.utcnow() - timedelta(days=i * 3),
                stats=TikTokVideoStats(
                    views=100_000 * (3 - i),
                    likes=15_000 * (3 - i),
                    comments=500 * (3 - i),
                    shares=200 * (3 - i),
                    bookmarks=300 * (3 - i),
                ),
            )
            for i in range(min(max_videos, 2))
        ]

        user_info = TikTokUserInfo(
            username=clean_username,
            display_name=f"{clean_username.title()} Creator",
            bio="Digital creator | Living my best life ✨ | DM for collabs",
            profile_url=f"https://www.tiktok.com/@{clean_username}",
            is_verified=True,
            region="US",
            stats=TikTokUserStats(
                followers=1_500_000,
                following=500,
                likes=25_000_000,
                video_count=150,
            ),
            videos=mock_videos,
            scraped_at=datetime.utcnow(),
        )

        elapsed = time.time() - start_time

        return ScrapedData(
            user=user_info,
            scrape_duration_seconds=elapsed,
        )

    @staticmethod
    def _get_mock_description(index: int) -> str:
        descriptions = [
            "Day in my life as a tech worker in SF 🌉 #dayinmylife #techlife #sanfrancisco",
            "Trying the viral pasta recipe everyone's talking about 🍝 #cooking #viral #foodtiktok",
            "POV: You finally understand recursion 💻 #coding #programmer #tech",
        ]
        return descriptions[index % len(descriptions)]

    @staticmethod
    def _get_mock_hashtags(index: int) -> list[str]:
        hashtag_sets = [
            ["dayinmylife", "techlife", "sanfrancisco", "vlog", "fyp"],
            ["cooking", "viral", "foodtiktok", "recipe", "pasta"],
            ["coding", "programmer", "tech", "learntocode", "python"],
        ]
        return hashtag_sets[index % len(hashtag_sets)]
