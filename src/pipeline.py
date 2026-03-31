"""
Pipeline Orchestrator.

Orchestrates the full workflow from scraping to profile generation:
1. Scrape TikTok user profile and videos
2. Download videos
3. Extract frames
4. Analyze video content with LLM
5. Generate user profile
6. Start Q&A agent
"""

import time
from pathlib import Path
from typing import Optional

from src.logging_config import get_logger
from src.config import Settings
from src.scraper.tiktok_scraper import TikTokScraper, MockTikTokScraper
from src.scraper.ytdlp_scraper import YtDlpScraper
from src.scraper.video_downloader import VideoDownloader
from src.scraper.frame_extractor import FrameExtractor
from src.scraper.models import ScrapedData
from src.analyzer.video_analyzer import VideoAnalyzer
from src.analyzer.profile_generator import ProfileGenerator
from src.analyzer.models import UserProfile, VideoAnalysisResult
from src.agent.chat_agent import ChatAgent
from src.storage.repository import Repository

logger = get_logger(__name__)


class PipelineError(Exception):
    """Raised when the pipeline encounters a critical error."""


class AnalysisPipeline:
    """
    End-to-end pipeline for TikTok user analysis.

    Orchestrates scraping, video processing, LLM analysis,
    and profile generation into a single workflow.

    Usage:
        pipeline = AnalysisPipeline(settings)
        await pipeline.initialize()
        profile = await pipeline.analyze_user("username")
        agent = pipeline.create_agent(profile)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._repo: Optional[Repository] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize pipeline components."""
        self._repo = Repository(self.settings.storage.database_url)
        await self._repo.initialize()
        self._initialized = True
        logger.info("pipeline_initialized")

    async def close(self) -> None:
        """Clean up resources."""
        if self._repo:
            await self._repo.close()

    async def analyze_user(
        self,
        username: str,
        max_videos: int = 2,
        use_mock: bool = False,
        skip_download: bool = False,
    ) -> UserProfile:
        """
        Run the full analysis pipeline for a TikTok user.

        Args:
            username: TikTok username to analyze
            max_videos: Max videos to scrape and analyze
            use_mock: Use mock scraper for testing
            skip_download: Skip video download (use metadata only)

        Returns:
            Generated UserProfile

        Raises:
            PipelineError: For critical pipeline failures
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        clean_username = username.lstrip("@")

        logger.info(
            "pipeline_started",
            username=clean_username,
            max_videos=max_videos,
            use_mock=use_mock,
        )

        # Step 1: Check cache
        cached_profile = await self._repo.get_profile(clean_username)
        if cached_profile:
            logger.info("profile_loaded_from_cache", username=clean_username)
            return cached_profile

        # Step 2: Scrape user data
        scraped_data = await self._scrape_user(clean_username, max_videos, use_mock)

        # Step 3: Download videos and extract frames
        frame_paths: dict[str, list[Path]] = {}
        if not skip_download and not use_mock:
            frame_paths = await self._process_videos(scraped_data)

        # Step 4: Analyze videos with LLM
        video_analyses = await self._analyze_videos(scraped_data, frame_paths)

        # Step 5: Generate user profile
        profile = await self._generate_profile(scraped_data.user, video_analyses)

        # Step 6: Save to database
        if self._repo:
            await self._repo.save_profile(profile)
            for va in video_analyses:
                await self._repo.save_video_analysis(clean_username, va)

        elapsed = time.time() - start_time
        logger.info(
            "pipeline_complete",
            username=clean_username,
            duration_seconds=f"{elapsed:.2f}",
            videos_analyzed=len(video_analyses),
        )

        return profile

    async def _scrape_user(
        self,
        username: str,
        max_videos: int,
        use_mock: bool,
    ) -> ScrapedData:
        """Step 1: Scrape user profile and video metadata."""
        logger.info("step_scraping", username=username)

        if use_mock:
            scraper_kwargs = {
                "request_delay": self.settings.scraper.request_delay,
            }
            async with MockTikTokScraper(**scraper_kwargs) as scraper:
                data = await scraper.scrape_user(username, max_videos=max_videos)
        else:
            # Use yt-dlp based scraper (much more reliable than Playwright)
            scraper = YtDlpScraper(
                request_delay=self.settings.scraper.request_delay,
            )
            async with scraper:
                data = await scraper.scrape_user(username, max_videos=max_videos)

        if not data.user:
            raise PipelineError(f"Failed to scrape user: @{username}")

        logger.info(
            "scraping_complete",
            username=username,
            videos_found=len(data.user.videos),
        )
        return data

    async def _process_videos(
        self,
        scraped_data: ScrapedData,
    ) -> dict[str, list[Path]]:
        """Step 2: Download videos and extract frames."""
        logger.info("step_processing_videos", count=len(scraped_data.user.videos))

        self.settings.storage.ensure_dirs()
        downloader = VideoDownloader(
            output_dir=self.settings.storage.media_dir / "videos",
            max_retries=self.settings.scraper.max_retries,
        )
        extractor = FrameExtractor(
            output_dir=self.settings.storage.media_dir / "frames",
        )

        frame_paths: dict[str, list[Path]] = {}

        for video in scraped_data.user.videos:
            try:
                # Download video
                video_path = await downloader.download(video.url, video.video_id)

                # Extract frames
                frames = await extractor.extract_frames(
                    video_path,
                    num_frames=self.settings.agent.frames_per_video,
                    video_id=video.video_id,
                )
                frame_paths[video.video_id] = frames

            except Exception as e:
                logger.warning(
                    "video_processing_failed",
                    video_id=video.video_id,
                    error=str(e),
                )

        return frame_paths

    async def _analyze_videos(
        self,
        scraped_data: ScrapedData,
        frame_paths: dict[str, list[Path]],
    ) -> list[VideoAnalysisResult]:
        """Step 3: Analyze videos using LLM."""
        logger.info("step_analyzing_videos", count=len(scraped_data.user.videos))

        analyzer = VideoAnalyzer(
            api_key=self.settings.llm.anthropic_api_key,
            model=self.settings.llm.model,
            vision_model=self.settings.llm.vision_model,
            max_tokens=self.settings.llm.max_tokens,
            temperature=self.settings.llm.temperature,
        )

        results: list[VideoAnalysisResult] = []

        for video in scraped_data.user.videos:
            try:
                frames = frame_paths.get(video.video_id, [])
                if frames:
                    analysis = await analyzer.analyze_video(video, frames)
                else:
                    # Metadata-only analysis
                    analysis = await self._metadata_only_analysis(analyzer, video)
                results.append(analysis)
            except Exception as e:
                logger.warning(
                    "video_analysis_failed",
                    video_id=video.video_id,
                    error=str(e),
                )

        return results

    async def _metadata_only_analysis(
        self,
        analyzer: VideoAnalyzer,
        video,
    ) -> VideoAnalysisResult:
        """Generate analysis from metadata only (no video frames)."""
        import anthropic

        prompt = (
            f"Analyze this TikTok video based on its metadata:\n\n"
            f"{video.to_analysis_text()}\n\n"
            f"Generate a JSON analysis with: content_summary, content_category, "
            f"content_themes, tone, target_audience, engagement_hooks.\n"
            f"Respond ONLY with JSON."
        )

        client = anthropic.Anthropic(api_key=analyzer.client.api_key)
        response = client.messages.create(
            model=analyzer.model,
            max_tokens=1024,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = response.content[0].text.strip()
        text = analyzer._clean_json_response(text)
        data = json.loads(text)

        return VideoAnalysisResult(
            video_id=video.video_id,
            video_url=video.url,
            content_summary=data.get("content_summary", ""),
            content_category=data.get("content_category", ""),
            content_themes=data.get("content_themes", []),
            tone=data.get("tone", ""),
            target_audience=data.get("target_audience", ""),
            engagement_hooks=data.get("engagement_hooks", []),
            description=video.description,
            hashtags=video.hashtags,
            views=video.stats.views,
            likes=video.stats.likes,
            comments=video.stats.comments,
        )

    async def _generate_profile(
        self,
        user_info,
        video_analyses: list[VideoAnalysisResult],
    ) -> UserProfile:
        """Step 4: Generate comprehensive user profile."""
        logger.info("step_generating_profile", username=user_info.username)

        generator = ProfileGenerator(
            api_key=self.settings.llm.anthropic_api_key,
            model=self.settings.llm.model,
            max_tokens=self.settings.llm.max_tokens,
            temperature=self.settings.llm.temperature,
        )

        return await generator.generate_profile(user_info, video_analyses)

    def create_agent(
        self,
        profile: UserProfile,
    ) -> ChatAgent:
        """Create a conversational agent from a generated profile."""
        return ChatAgent(
            api_key=self.settings.llm.anthropic_api_key,
            user_profile=profile,
            model=self.settings.llm.model,
            max_tokens=self.settings.llm.max_tokens,
            temperature=self.settings.llm.temperature,
            max_conversation_turns=self.settings.agent.max_conversation_turns,
        )

    async def get_cached_profiles(self) -> list[dict]:
        """List all cached profiles."""
        if not self._repo:
            return []
        return await self._repo.list_profiles()
