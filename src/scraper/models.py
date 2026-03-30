"""
Data models for TikTok scraper module.
Defines the structure of scraped data from TikTok profiles and videos.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class VideoPrivacyLevel(str, Enum):
    """Video privacy/visibility level."""
    PUBLIC = "public"
    FRIENDS = "friends"
    PRIVATE = "private"


class TikTokVideoStats(BaseModel):
    """Statistics for a single TikTok video."""

    views: int = Field(default=0, ge=0, description="Number of views")
    likes: int = Field(default=0, ge=0, description="Number of likes")
    comments: int = Field(default=0, ge=0, description="Number of comments")
    shares: int = Field(default=0, ge=0, description="Number of shares")
    bookmarks: int = Field(default=0, ge=0, description="Number of bookmarks")

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate as (likes + comments + shares) / views."""
        if self.views == 0:
            return 0.0
        return (self.likes + self.comments + self.shares) / self.views

    @property
    def engagement_summary(self) -> str:
        """Human-readable engagement summary."""
        rate = self.engagement_rate * 100
        if rate > 10:
            return f"Very High ({rate:.1f}%)"
        elif rate > 5:
            return f"High ({rate:.1f}%)"
        elif rate > 2:
            return f"Moderate ({rate:.1f}%)"
        else:
            return f"Low ({rate:.1f}%)"


class TikTokVideoInfo(BaseModel):
    """Information about a single TikTok video."""

    video_id: str = Field(description="Unique video identifier")
    url: str = Field(description="Full URL to the video")
    description: str = Field(default="", description="Video caption/description")
    hashtags: list[str] = Field(default_factory=list, description="Hashtags used")
    music_title: Optional[str] = Field(default=None, description="Background music title")
    music_author: Optional[str] = Field(default=None, description="Background music author")
    duration_seconds: Optional[float] = Field(
        default=None, ge=0, description="Video duration in seconds"
    )
    created_at: Optional[datetime] = Field(default=None, description="Video creation timestamp")
    stats: TikTokVideoStats = Field(
        default_factory=TikTokVideoStats, description="Video engagement stats"
    )
    thumbnail_url: Optional[str] = Field(default=None, description="Video thumbnail URL")
    privacy_level: VideoPrivacyLevel = Field(
        default=VideoPrivacyLevel.PUBLIC, description="Video privacy level"
    )
    is_ad: bool = Field(default=False, description="Whether the video is a promoted/ad post")

    @property
    def hashtag_string(self) -> str:
        """Hashtags as a single string."""
        return " ".join(f"#{tag}" for tag in self.hashtags)

    def to_analysis_text(self) -> str:
        """Convert video info to text suitable for LLM analysis."""
        parts = [
            f"Video ID: {self.video_id}",
            f"Description: {self.description}" if self.description else "Description: (none)",
            f"Hashtags: {self.hashtag_string}" if self.hashtags else "Hashtags: (none)",
        ]
        if self.music_title:
            parts.append(f"Music: {self.music_title} by {self.music_author or 'Unknown'}")
        if self.duration_seconds:
            parts.append(f"Duration: {self.duration_seconds:.1f}s")
        if self.stats:
            parts.append(
                f"Stats: {self.stats.views} views, {self.stats.likes} likes, "
                f"{self.stats.comments} comments, {self.stats.shares} shares"
            )
            parts.append(f"Engagement: {self.stats.engagement_summary}")
        if self.created_at:
            parts.append(f"Posted: {self.created_at.isoformat()}")
        return "\n".join(parts)


class TikTokUserStats(BaseModel):
    """Statistics for a TikTok user profile."""

    followers: int = Field(default=0, ge=0, description="Number of followers")
    following: int = Field(default=0, ge=0, description="Number of accounts following")
    likes: int = Field(default=0, ge=0, description="Total likes received")
    video_count: int = Field(default=0, ge=0, description="Number of public videos")

    @property
    def follower_ratio(self) -> float:
        """Followers to following ratio."""
        if self.following == 0:
            return float(self.followers)
        return self.followers / self.following

    @property
    def avg_likes_per_video(self) -> float:
        """Average likes per video."""
        if self.video_count == 0:
            return 0.0
        return self.likes / self.video_count


class TikTokUserInfo(BaseModel):
    """Complete information about a TikTok user profile."""

    username: str = Field(description="TikTok username (without @)")
    display_name: str = Field(default="", description="Display name")
    bio: str = Field(default="", description="User bio/description")
    avatar_url: Optional[str] = Field(default=None, description="Profile picture URL")
    profile_url: str = Field(description="Full profile URL")
    is_verified: bool = Field(default=False, description="Whether the user is verified")
    region: Optional[str] = Field(default=None, description="User's region/country")
    stats: TikTokUserStats = Field(
        default_factory=TikTokUserStats, description="User statistics"
    )
    videos: list[TikTokVideoInfo] = Field(
        default_factory=list, description="User's videos (limited)"
    )
    scraped_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the data was scraped"
    )

    @property
    def video_count(self) -> int:
        """Number of scraped videos."""
        return len(self.videos)

    def to_analysis_text(self) -> str:
        """Convert user info to text suitable for LLM analysis."""
        parts = [
            f"=== TikTok User Profile: @{self.username} ===",
            f"Display Name: {self.display_name}",
            f"Bio: {self.bio}" if self.bio else "Bio: (none)",
            f"Verified: {'Yes' if self.is_verified else 'No'}",
            f"Region: {self.region}" if self.region else "",
            f"Followers: {self.stats.followers:,}",
            f"Following: {self.stats.following:,}",
            f"Total Likes: {self.stats.likes:,}",
            f"Videos Posted: {self.stats.video_count}",
            f"Follower Ratio: {self.stats.follower_ratio:.2f}",
            "",
        ]

        for i, video in enumerate(self.videos, 1):
            parts.append(f"--- Video {i} ---")
            parts.append(video.to_analysis_text())
            parts.append("")

        return "\n".join(filter(None, parts))


class ScrapedData(BaseModel):
    """Complete scraped data package for a TikTok user."""

    user: TikTokUserInfo
    video_frames: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapping of video_id to list of extracted frame file paths",
    )
    video_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of video_id to downloaded video file path",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered during scraping",
    )
    scrape_duration_seconds: float = Field(
        default=0.0, description="Total scraping duration"
    )

    @property
    def is_complete(self) -> bool:
        """Check if scraping completed without critical errors."""
        return len(self.user.videos) > 0 and len(self.errors) == 0

    @property
    def frame_count(self) -> int:
        """Total number of extracted frames."""
        return sum(len(frames) for frames in self.video_frames.values())
