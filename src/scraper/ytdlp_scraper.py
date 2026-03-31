"""
TikTok Scraper using yt-dlp as the extraction backend.

yt-dlp has dedicated TikTok extractors that are actively maintained
to bypass anti-bot measures. This is far more reliable than Playwright.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

import yt_dlp

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


class YtDlpScraper:
    """
    Scrapes TikTok profiles using yt-dlp's built-in TikTok extractor.

    yt-dlp actively maintains TikTok support and handles anti-bot
    measures internally, making this far more reliable than browser
    automation.

    Usage:
        scraper = YtDlpScraper()
        async with scraper:
            data = await scraper.scrape_user("khaby.lame", max_videos=2)
    """

    TIKTOK_BASE_URL = "https://www.tiktok.com"

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        request_delay: float = 1.0,
        **kwargs,  # Accept and ignore extra kwargs for compatibility
    ):
        self.cookies_file = cookies_file
        self.request_delay = request_delay

    async def __aenter__(self) -> "YtDlpScraper":
        return self

    async def __aexit__(self, *args) -> None:
        pass

    def _get_yt_dlp_opts(self, extra_opts: Optional[dict] = None) -> dict:
        """Build yt-dlp options."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "socket_timeout": 30,
            "retries": 3,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.tiktok.com/",
            },
        }
        if self.cookies_file:
            opts["cookiefile"] = self.cookies_file
        if extra_opts:
            opts.update(extra_opts)
        return opts

    async def scrape_user(
        self,
        username: str,
        max_videos: int = 2,
    ) -> ScrapedData:
        """
        Scrape a TikTok user's profile and recent videos.

        Uses yt-dlp to extract video listings from the user's page,
        then extracts metadata from each video.
        """
        start_time = time.time()
        clean_username = username.lstrip("@")
        errors: list[str] = []

        logger.info("yt_dlp_scraping_user", username=clean_username, max_videos=max_videos)

        profile_url = f"{self.TIKTOK_BASE_URL}/@{clean_username}"

        # Step 1: Extract video list from user page
        video_entries = await self._extract_user_videos(profile_url, max_videos)

        if not video_entries:
            raise ScraperError(
                f"No videos found for @{clean_username}. "
                f"The account may be private or TikTok is blocking requests."
            )

        # Step 2: Extract detailed info from each video
        videos: list[TikTokVideoInfo] = []
        user_info_raw: dict = {}

        for entry in video_entries[:max_videos]:
            try:
                video_url = entry.get("url") or entry.get("webpage_url", "")
                if not video_url:
                    video_id = entry.get("id", "")
                    video_url = f"{self.TIKTOK_BASE_URL}/@{clean_username}/video/{video_id}"

                info = await self._extract_video_info(video_url)
                if info:
                    # Capture uploader info from first video
                    if not user_info_raw:
                        user_info_raw = {
                            "uploader": info.get("uploader", clean_username),
                            "uploader_id": info.get("uploader_id", clean_username),
                            "channel_follower_count": info.get("channel_follower_count", 0),
                        }

                    video = self._parse_video_info(info, clean_username)
                    if video:
                        videos.append(video)
                        logger.info("video_scraped", video_id=video.video_id,
                                   views=video.stats.views)

                await asyncio.sleep(self.request_delay)

            except Exception as e:
                error_msg = f"Failed to extract video: {str(e)}"
                errors.append(error_msg)
                logger.warning("video_extract_failed", error=str(e))

        # Step 3: Build user info
        user_info = TikTokUserInfo(
            username=clean_username,
            display_name=user_info_raw.get("uploader", clean_username),
            bio="",  # yt-dlp doesn't extract bio
            profile_url=profile_url,
            is_verified=False,
            stats=TikTokUserStats(
                followers=user_info_raw.get("channel_follower_count", 0),
                video_count=len(videos),
            ),
            videos=videos,
            scraped_at=datetime.now(timezone.utc),
        )

        elapsed = time.time() - start_time
        logger.info(
            "yt_dlp_scraping_complete",
            username=clean_username,
            videos_scraped=len(videos),
            errors=len(errors),
            duration=f"{elapsed:.1f}s",
        )

        return ScrapedData(
            user=user_info,
            errors=errors,
            scrape_duration_seconds=elapsed,
        )

    async def _extract_user_videos(
        self, profile_url: str, max_videos: int
    ) -> list[dict]:
        """Extract video listing from a user's profile page."""
        opts = self._get_yt_dlp_opts({
            "extract_flat": True,  # Don't download, just list
            "playlistend": max_videos,
        })

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    result = ydl.extract_info(profile_url, download=False)
                    if result and "entries" in result:
                        return list(result["entries"])
                    return []
                except Exception as e:
                    logger.error("yt_dlp_user_extract_failed", error=str(e))
                    return []

        return await asyncio.get_event_loop().run_in_executor(None, _extract)

    async def _extract_video_info(self, video_url: str) -> Optional[dict]:
        """Extract detailed info from a single video."""
        opts = self._get_yt_dlp_opts({
            "extract_flat": False,
            "skip_download": True,  # Don't download the video
        })

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    return ydl.extract_info(video_url, download=False)
                except Exception as e:
                    logger.error("yt_dlp_video_extract_failed",
                               url=video_url, error=str(e))
                    return None

        return await asyncio.get_event_loop().run_in_executor(None, _extract)

    def _parse_video_info(
        self, info: dict, username: str
    ) -> Optional[TikTokVideoInfo]:
        """Parse yt-dlp info dict into TikTokVideoInfo."""
        try:
            video_id = str(info.get("id", ""))
            if not video_id:
                return None

            # Extract hashtags from description
            description = info.get("description", "")
            import re
            hashtags = re.findall(r"#(\w+)", description)

            # Parse timestamp
            timestamp = info.get("timestamp")
            created_at = None
            if timestamp:
                created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)

            return TikTokVideoInfo(
                video_id=video_id,
                url=info.get("webpage_url", f"{self.TIKTOK_BASE_URL}/@{username}/video/{video_id}"),
                description=description,
                hashtags=hashtags,
                music_title=info.get("track"),
                music_author=info.get("artist"),
                duration_seconds=info.get("duration"),
                created_at=created_at,
                stats=TikTokVideoStats(
                    views=info.get("view_count", 0) or 0,
                    likes=info.get("like_count", 0) or 0,
                    comments=info.get("comment_count", 0) or 0,
                    shares=info.get("repost_count", 0) or 0,
                ),
                thumbnail_url=info.get("thumbnail"),
            )
        except Exception as e:
            logger.error("video_parse_error", error=str(e))
            return None

    async def download_video(
        self,
        video_url: str,
        output_dir: str | Path = "./data/media/videos",
        video_id: Optional[str] = None,
    ) -> Path:
        """Download a video file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not video_id:
            video_id = video_url.rstrip("/").split("/")[-1]

        output_path = output_dir / f"{video_id}.mp4"
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

        opts = self._get_yt_dlp_opts({
            "outtmpl": str(output_path),
            "format": "mp4/best[ext=mp4]/best",
        })

        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([video_url])

        await asyncio.get_event_loop().run_in_executor(None, _download)

        if not output_path.exists():
            raise ScraperError(f"Download failed: {video_url}")

        return output_path
