"""
Shared test fixtures and configuration for the test suite.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Set test environment before importing app modules
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key-for-testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_data/test.db"
os.environ["MEDIA_DIR"] = "./test_data/media"
os.environ["REPORTS_DIR"] = "./test_data/reports"

from src.scraper.models import (
    TikTokUserInfo,
    TikTokUserStats,
    TikTokVideoInfo,
    TikTokVideoStats,
    ScrapedData,
)
from src.analyzer.models import (
    FrameAnalysis,
    VideoAnalysisResult,
    UserProfile,
    ContentPattern,
    AudienceSegment,
    BrandPersonality,
)
from src.agent.memory import ConversationMemory


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_video_stats() -> TikTokVideoStats:
    """Create sample video statistics."""
    return TikTokVideoStats(
        views=250_000,
        likes=35_000,
        comments=1_200,
        shares=800,
        bookmarks=500,
    )


@pytest.fixture
def sample_video_info(sample_video_stats) -> TikTokVideoInfo:
    """Create a sample video info object."""
    return TikTokVideoInfo(
        video_id="7321456789012345678",
        url="https://www.tiktok.com/@testuser/video/7321456789012345678",
        description="Day in my life as a software engineer 💻 #tech #coding #dayinmylife",
        hashtags=["tech", "coding", "dayinmylife", "softwareengineer", "fyp"],
        music_title="Chill Lo-fi Beat",
        music_author="Lo-fi Producer",
        duration_seconds=45.0,
        created_at=datetime(2024, 12, 1, 10, 30, 0),
        stats=sample_video_stats,
    )


@pytest.fixture
def sample_video_info_2() -> TikTokVideoInfo:
    """Create a second sample video for comparison tests."""
    return TikTokVideoInfo(
        video_id="7321456789012345679",
        url="https://www.tiktok.com/@testuser/video/7321456789012345679",
        description="Trying the viral ramen recipe 🍜 #cooking #viral #foodtiktok",
        hashtags=["cooking", "viral", "foodtiktok", "ramen", "recipe"],
        music_title="Upbeat Kitchen",
        music_author="Cooking Tunes",
        duration_seconds=60.0,
        created_at=datetime(2024, 11, 28, 15, 0, 0),
        stats=TikTokVideoStats(
            views=180_000,
            likes=28_000,
            comments=900,
            shares=600,
            bookmarks=400,
        ),
    )


@pytest.fixture
def sample_user_stats() -> TikTokUserStats:
    """Create sample user statistics."""
    return TikTokUserStats(
        followers=1_500_000,
        following=500,
        likes=25_000_000,
        video_count=150,
    )


@pytest.fixture
def sample_user_info(
    sample_user_stats, sample_video_info, sample_video_info_2
) -> TikTokUserInfo:
    """Create a sample user info object with videos."""
    return TikTokUserInfo(
        username="testuser",
        display_name="Test Creator",
        bio="Tech + Lifestyle content 🎬 | 1.5M fam | DM for collabs",
        avatar_url="https://p16-sign.tiktokcdn.com/example-avatar.jpg",
        profile_url="https://www.tiktok.com/@testuser",
        is_verified=True,
        region="US",
        stats=sample_user_stats,
        videos=[sample_video_info, sample_video_info_2],
        scraped_at=datetime(2024, 12, 5, 12, 0, 0),
    )


@pytest.fixture
def sample_scraped_data(sample_user_info) -> ScrapedData:
    """Create sample scraped data."""
    return ScrapedData(
        user=sample_user_info,
        video_frames={},
        video_files={},
        errors=[],
        scrape_duration_seconds=5.2,
    )


@pytest.fixture
def sample_frame_analysis() -> FrameAnalysis:
    """Create a sample frame analysis."""
    return FrameAnalysis(
        frame_index=0,
        scene_description="Person sitting at a desk with multiple monitors showing code",
        objects_detected=["desk", "monitors", "keyboard", "coffee cup", "laptop"],
        text_detected="VS Code editor visible on main screen",
        mood_tone="focused, professional",
        setting="Modern home office",
    )


@pytest.fixture
def sample_video_analysis() -> VideoAnalysisResult:
    """Create a sample video analysis result."""
    return VideoAnalysisResult(
        video_id="7321456789012345678",
        video_url="https://www.tiktok.com/@testuser/video/7321456789012345678",
        content_summary="A day-in-the-life vlog showing the creator's routine as a software engineer, including coding sessions, coffee breaks, and workout time.",
        content_category="lifestyle",
        content_subcategories=["tech", "vlog", "day-in-my-life"],
        content_themes=["tech life", "productivity", "work-life balance"],
        frame_analyses=[],
        production_quality="semi-professional",
        editing_style="Quick cuts with smooth transitions, text overlays",
        visual_aesthetic="Clean, modern, minimalist",
        music_mood="Chill, lo-fi",
        has_voiceover=True,
        has_dialogue=False,
        target_audience="Young professionals aged 22-35 interested in tech careers",
        tone="casual",
        engagement_hooks=["relatable morning routine", "satisfying desk setup reveal"],
        call_to_action="Follow for more tech content",
        description="Day in my life as a software engineer 💻 #tech #coding #dayinmylife",
        hashtags=["tech", "coding", "dayinmylife"],
        views=250_000,
        likes=35_000,
        comments=1_200,
    )


@pytest.fixture
def sample_video_analysis_2() -> VideoAnalysisResult:
    """Second video analysis for comparison."""
    return VideoAnalysisResult(
        video_id="7321456789012345679",
        video_url="https://www.tiktok.com/@testuser/video/7321456789012345679",
        content_summary="A cooking video showing the creator trying a viral ramen recipe from scratch with commentary on each step.",
        content_category="food",
        content_subcategories=["cooking", "recipe", "viral"],
        content_themes=["viral recipes", "cooking at home", "food content"],
        production_quality="casual",
        editing_style="Step-by-step with text overlays",
        visual_aesthetic="Warm, cozy kitchen setting",
        target_audience="Food enthusiasts and casual home cooks aged 18-30",
        tone="enthusiastic",
        engagement_hooks=["viral recipe promise", "taste test reaction"],
        description="Trying the viral ramen recipe 🍜",
        hashtags=["cooking", "viral", "foodtiktok"],
        views=180_000,
        likes=28_000,
        comments=900,
    )


@pytest.fixture
def sample_user_profile(
    sample_video_analysis, sample_video_analysis_2
) -> UserProfile:
    """Create a complete sample user profile."""
    return UserProfile(
        username="testuser",
        display_name="Test Creator",
        bio="Tech + Lifestyle content 🎬 | 1.5M fam | DM for collabs",
        profile_summary=(
            "Test Creator is a versatile content creator based in the US who primarily "
            "creates tech lifestyle and food content on TikTok. With 1.5M followers, "
            "they have established themselves as a mid-to-macro tier influencer who "
            "blends tech industry insights with relatable everyday content like cooking "
            "and personal vlogs."
        ),
        creator_type="lifestyle/tech",
        niche="tech professional lifestyle",
        estimated_influence_tier="macro",
        primary_topics=["tech", "lifestyle", "coding", "cooking", "day-in-my-life"],
        content_format="Short-form vlogs with quick cuts and text overlays",
        posting_style="Mix of tech lifestyle vlogs and viral trend participation",
        content_patterns=[
            ContentPattern(
                pattern_type="theme",
                description="Alternates between tech career content and lifestyle/food content",
                frequency="consistent",
                examples=["coding vlogs", "recipe videos"],
            ),
            ContentPattern(
                pattern_type="format",
                description="Relies on text overlays and lo-fi music",
                frequency="always",
                examples=["text-heavy edits", "music-driven pacing"],
            ),
        ],
        audience_segments=[
            AudienceSegment(
                segment_name="Young Tech Professionals",
                age_range="22-35",
                interests=["technology", "careers", "productivity"],
                engagement_level="high",
                description="Software engineers and tech workers who relate to the creator's content",
            ),
            AudienceSegment(
                segment_name="General Lifestyle Viewers",
                age_range="18-30",
                interests=["lifestyle", "food", "trends"],
                engagement_level="medium",
                description="Casual viewers drawn to viral content and lifestyle vlogs",
            ),
        ],
        primary_audience_description="Young tech professionals and lifestyle enthusiasts aged 18-35",
        brand_personality=BrandPersonality(
            primary_archetype="The Creator",
            secondary_archetype="The Explorer",
            tone_of_voice="Casual, relatable, informative",
            values=["authenticity", "work-life balance", "creativity"],
            differentiators=["tech insider perspective", "diverse content range"],
        ),
        engagement_strategy="Combines relatable daily content with trending formats",
        community_building="Engages through comments and relatable content themes",
        growth_potential="Strong potential for brand partnerships in tech and lifestyle",
        strengths=["Diverse content range", "Strong production quality", "Relatable persona"],
        areas_for_improvement=["Could post more consistently", "Niche could be more focused"],
        collaboration_opportunities=["Tech brands", "Food brands", "Productivity apps"],
        videos_analyzed=2,
        video_analyses=[sample_video_analysis, sample_video_analysis_2],
        generated_at=datetime(2024, 12, 5, 12, 30, 0),
        confidence_score=0.78,
    )


@pytest.fixture
def conversation_memory() -> ConversationMemory:
    """Create a fresh conversation memory."""
    return ConversationMemory(max_turns=10)


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Mock response")]
    client.messages.create.return_value = mock_response
    return client


@pytest.fixture
def test_data_dir(tmp_path) -> Path:
    """Create a temporary test data directory."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    (data_dir / "media").mkdir()
    (data_dir / "media" / "videos").mkdir()
    (data_dir / "media" / "frames").mkdir()
    (data_dir / "reports").mkdir()
    return data_dir


# Test data directory initialization
@pytest.fixture(autouse=True)
def setup_test_dirs():
    """Ensure test directories exist."""
    Path("./test_data").mkdir(exist_ok=True)
    Path("./test_data/media").mkdir(exist_ok=True)
    yield
    # Cleanup handled by pytest-tmp or manual
