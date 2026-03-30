"""
Video downloader for TikTok videos using yt-dlp.

Downloads videos from TikTok URLs and stores them locally
for frame extraction and analysis.
"""

import asyncio
from pathlib import Path
from typing import Optional

from src.logging_config import get_logger

logger = get_logger(__name__)


class DownloadError(Exception):
    """Raised when video download fails."""


class VideoDownloader:
    """
    Downloads TikTok videos using yt-dlp.

    Handles video download with proper error handling, retry logic,
    and output path management.

    Usage:
        downloader = VideoDownloader(output_dir="./data/media")
        path = await downloader.download("https://tiktok.com/@user/video/123")
    """

    def __init__(
        self,
        output_dir: str | Path = "./data/media",
        max_retries: int = 3,
        timeout: int = 60,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.timeout = timeout

    def _get_yt_dlp_opts(self, output_path: Path) -> dict:
        """Build yt-dlp options dictionary."""
        return {
            "outtmpl": str(output_path),
            "format": "mp4/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": self.timeout,
            "retries": self.max_retries,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.tiktok.com/",
            },
        }

    async def download(
        self,
        video_url: str,
        video_id: Optional[str] = None,
    ) -> Path:
        """
        Download a TikTok video.

        Args:
            video_url: Full URL to the TikTok video
            video_id: Optional video ID for naming the output file

        Returns:
            Path to the downloaded video file

        Raises:
            DownloadError: If the download fails after retries
        """
        if not video_id:
            video_id = video_url.rstrip("/").split("/")[-1]

        output_path = self.output_dir / f"{video_id}.mp4"

        # Skip if already downloaded
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info("video_already_downloaded", video_id=video_id, path=str(output_path))
            return output_path

        logger.info("downloading_video", url=video_url, video_id=video_id)

        try:
            # Run yt-dlp in a thread to avoid blocking
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._download_sync,
                video_url,
                output_path,
            )

            if not output_path.exists():
                raise DownloadError(f"Download completed but file not found: {output_path}")

            file_size = output_path.stat().st_size
            logger.info(
                "video_downloaded",
                video_id=video_id,
                path=str(output_path),
                size_bytes=file_size,
            )
            return output_path

        except Exception as e:
            # Cleanup partial download
            if output_path.exists():
                output_path.unlink()
            raise DownloadError(f"Failed to download video {video_url}: {str(e)}") from e

    def _download_sync(self, url: str, output_path: Path) -> None:
        """Synchronous download using yt-dlp."""
        import yt_dlp

        opts = self._get_yt_dlp_opts(output_path)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    async def download_multiple(
        self,
        video_urls: list[str],
        video_ids: Optional[list[str]] = None,
    ) -> dict[str, Path]:
        """
        Download multiple videos concurrently.

        Args:
            video_urls: List of video URLs to download
            video_ids: Optional list of video IDs (same order as URLs)

        Returns:
            Dictionary mapping video_id to downloaded file path
        """
        if video_ids is None:
            video_ids = [url.rstrip("/").split("/")[-1] for url in video_urls]

        results: dict[str, Path] = {}

        # Download sequentially to respect rate limits
        for url, vid_id in zip(video_urls, video_ids):
            try:
                path = await self.download(url, vid_id)
                results[vid_id] = path
            except DownloadError as e:
                logger.error("download_failed", video_id=vid_id, error=str(e))

        return results

    def cleanup(self, video_id: Optional[str] = None) -> None:
        """
        Remove downloaded video files.

        Args:
            video_id: Specific video ID to remove. If None, removes all.
        """
        if video_id:
            path = self.output_dir / f"{video_id}.mp4"
            if path.exists():
                path.unlink()
                logger.info("video_cleaned_up", video_id=video_id)
        else:
            for mp4_file in self.output_dir.glob("*.mp4"):
                mp4_file.unlink()
            logger.info("all_videos_cleaned_up")
