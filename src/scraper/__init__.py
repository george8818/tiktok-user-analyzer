"""
TikTok Scraper Module.
Handles profile scraping, video downloading, and frame extraction.
"""

from src.scraper.models import (
    ScrapedData,
    TikTokUserInfo,
    TikTokUserStats,
    TikTokVideoInfo,
    TikTokVideoStats,
)
from src.scraper.tiktok_scraper import TikTokScraper
from src.scraper.ytdlp_scraper import YtDlpScraper
from src.scraper.video_downloader import VideoDownloader
from src.scraper.frame_extractor import FrameExtractor

__all__ = [
    "TikTokScraper",
    "YtDlpScraper",
    "VideoDownloader",
    "FrameExtractor",
    "ScrapedData",
    "TikTokUserInfo",
    "TikTokUserStats",
    "TikTokVideoInfo",
    "TikTokVideoStats",
]
