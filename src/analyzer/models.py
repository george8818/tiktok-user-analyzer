"""
Data models for the analyzer module.
Defines structures for video analysis results and user profiles.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FrameAnalysis(BaseModel):
    """Analysis result for a single video frame."""

    frame_index: int = Field(description="Frame index in the video")
    scene_description: str = Field(description="Description of what's happening in the frame")
    objects_detected: list[str] = Field(default_factory=list, description="Objects in the frame")
    text_detected: str = Field(default="", description="Any text visible in the frame")
    mood_tone: str = Field(default="", description="Mood or tone of the frame")
    setting: str = Field(default="", description="Location/setting description")


class VideoAnalysisResult(BaseModel):
    """Complete analysis result for a single video."""

    video_id: str = Field(description="Video identifier")
    video_url: str = Field(default="", description="Video URL")

    # Content analysis
    content_summary: str = Field(description="Summary of video content")
    content_category: str = Field(description="Primary content category")
    content_subcategories: list[str] = Field(
        default_factory=list, description="Content subcategories/tags"
    )
    content_themes: list[str] = Field(
        default_factory=list, description="Key themes identified"
    )

    # Frame-level analysis
    frame_analyses: list[FrameAnalysis] = Field(
        default_factory=list, description="Per-frame analysis results"
    )

    # Production quality
    production_quality: str = Field(
        default="", description="Assessment of production quality"
    )
    editing_style: str = Field(default="", description="Editing style/techniques used")
    visual_aesthetic: str = Field(default="", description="Visual style/aesthetic")

    # Audio/Music
    music_mood: str = Field(default="", description="Mood of background music")
    has_voiceover: bool = Field(default=False, description="Whether video has voiceover")
    has_dialogue: bool = Field(default=False, description="Whether video has dialogue")

    # Audience signals
    target_audience: str = Field(default="", description="Likely target audience")
    tone: str = Field(default="", description="Overall tone (humorous, educational, etc.)")
    language: str = Field(default="en", description="Primary language")

    # Engagement analysis
    engagement_hooks: list[str] = Field(
        default_factory=list, description="Engagement hooks/techniques used"
    )
    call_to_action: Optional[str] = Field(
        default=None, description="Any call to action in the video"
    )

    # Metadata from scraper
    description: str = Field(default="", description="Video caption/description")
    hashtags: list[str] = Field(default_factory=list, description="Hashtags used")
    views: int = Field(default=0, description="View count")
    likes: int = Field(default=0, description="Like count")
    comments: int = Field(default=0, description="Comment count")


class ContentPattern(BaseModel):
    """Pattern identified across a user's content."""

    pattern_type: str = Field(description="Type of pattern (theme, format, timing, etc.)")
    description: str = Field(description="Description of the pattern")
    frequency: str = Field(default="", description="How often this pattern appears")
    examples: list[str] = Field(default_factory=list, description="Examples of the pattern")


class AudienceSegment(BaseModel):
    """A segment of the user's likely audience."""

    segment_name: str = Field(description="Name of the audience segment")
    age_range: str = Field(default="", description="Estimated age range")
    interests: list[str] = Field(default_factory=list, description="Common interests")
    engagement_level: str = Field(default="", description="How engaged this segment is")
    description: str = Field(default="", description="Description of this audience segment")


class BrandPersonality(BaseModel):
    """Brand personality assessment for the user."""

    primary_archetype: str = Field(description="Primary brand archetype")
    secondary_archetype: str = Field(default="", description="Secondary brand archetype")
    tone_of_voice: str = Field(description="Overall tone of voice")
    values: list[str] = Field(default_factory=list, description="Core values projected")
    differentiators: list[str] = Field(
        default_factory=list, description="What makes this creator unique"
    )


class UserProfile(BaseModel):
    """
    Comprehensive user profile generated from video analysis.
    This is the primary output of the analyzer module.
    """

    # Basic info
    username: str = Field(description="TikTok username")
    display_name: str = Field(default="", description="Display name")
    bio: str = Field(default="", description="User bio")

    # Profile summary
    profile_summary: str = Field(description="1-2 paragraph summary of the user")
    creator_type: str = Field(description="Type of creator (e.g., lifestyle, tech, comedy)")
    niche: str = Field(description="Specific content niche")
    estimated_influence_tier: str = Field(
        default="",
        description="Influence tier (nano, micro, mid, macro, mega)",
    )

    # Content analysis
    primary_topics: list[str] = Field(description="Main topics covered")
    content_format: str = Field(description="Typical content format")
    posting_style: str = Field(description="Description of posting style")
    content_patterns: list[ContentPattern] = Field(
        default_factory=list, description="Identified content patterns"
    )

    # Audience
    audience_segments: list[AudienceSegment] = Field(
        default_factory=list, description="Identified audience segments"
    )
    primary_audience_description: str = Field(
        default="", description="Description of primary audience"
    )

    # Brand personality
    brand_personality: Optional[BrandPersonality] = Field(
        default=None, description="Brand personality assessment"
    )

    # Engagement
    engagement_strategy: str = Field(
        default="", description="How the creator drives engagement"
    )
    community_building: str = Field(
        default="", description="Community building tactics"
    )

    # Growth signals
    growth_potential: str = Field(default="", description="Growth potential assessment")
    strengths: list[str] = Field(default_factory=list, description="Key strengths")
    areas_for_improvement: list[str] = Field(
        default_factory=list, description="Areas for improvement"
    )
    collaboration_opportunities: list[str] = Field(
        default_factory=list, description="Potential collaboration types"
    )

    # Technical metadata
    videos_analyzed: int = Field(default=0, description="Number of videos analyzed")
    video_analyses: list[VideoAnalysisResult] = Field(
        default_factory=list, description="Individual video analysis results"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the profile was generated"
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the profile accuracy (0-1)",
    )

    def to_context_string(self) -> str:
        """
        Convert the profile to a context string for the conversational agent.
        This provides all relevant info for answering user questions.
        """
        sections = [
            f"# User Profile: @{self.username}",
            f"**Display Name:** {self.display_name}",
            f"**Bio:** {self.bio}",
            "",
            f"## Profile Summary",
            self.profile_summary,
            "",
            f"## Creator Classification",
            f"- Creator Type: {self.creator_type}",
            f"- Niche: {self.niche}",
            f"- Influence Tier: {self.estimated_influence_tier}",
            f"- Content Format: {self.content_format}",
            f"- Posting Style: {self.posting_style}",
            "",
            f"## Topics & Themes",
            "- " + "\n- ".join(self.primary_topics) if self.primary_topics else "N/A",
            "",
        ]

        if self.content_patterns:
            sections.append("## Content Patterns")
            for pattern in self.content_patterns:
                sections.append(f"- **{pattern.pattern_type}**: {pattern.description}")
            sections.append("")

        if self.audience_segments:
            sections.append("## Audience Segments")
            for segment in self.audience_segments:
                sections.append(f"- **{segment.segment_name}**: {segment.description}")
            sections.append("")

        if self.brand_personality:
            bp = self.brand_personality
            sections.extend([
                "## Brand Personality",
                f"- Primary Archetype: {bp.primary_archetype}",
                f"- Tone: {bp.tone_of_voice}",
                f"- Values: {', '.join(bp.values)}",
                f"- Differentiators: {', '.join(bp.differentiators)}",
                "",
            ])

        sections.extend([
            "## Engagement & Growth",
            f"- Engagement Strategy: {self.engagement_strategy}",
            f"- Community Building: {self.community_building}",
            f"- Growth Potential: {self.growth_potential}",
            "",
            f"## Strengths",
            "- " + "\n- ".join(self.strengths) if self.strengths else "N/A",
            "",
            f"## Areas for Improvement",
            "- " + "\n- ".join(self.areas_for_improvement) if self.areas_for_improvement else "N/A",
            "",
        ])

        # Add video analysis summaries
        sections.append("## Video Analysis Details")
        for va in self.video_analyses:
            sections.extend([
                f"\n### Video: {va.video_id}",
                f"- Category: {va.content_category}",
                f"- Summary: {va.content_summary}",
                f"- Tone: {va.tone}",
                f"- Target Audience: {va.target_audience}",
                f"- Views: {va.views:,}, Likes: {va.likes:,}",
                f"- Hashtags: {', '.join(va.hashtags)}",
            ])

        return "\n".join(sections)
