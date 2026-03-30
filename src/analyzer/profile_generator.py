"""
User Profile Generator.

Synthesizes video analysis results and user metadata into a
comprehensive user profile using LLM-based reasoning.
"""

import json
from datetime import datetime
from typing import Optional

import anthropic

from src.logging_config import get_logger
from src.analyzer.models import (
    AudienceSegment,
    BrandPersonality,
    ContentPattern,
    UserProfile,
    VideoAnalysisResult,
)
from src.scraper.models import TikTokUserInfo

logger = get_logger(__name__)


class ProfileGenerationError(Exception):
    """Raised when profile generation fails."""


class ProfileGenerator:
    """
    Generates comprehensive user profiles from video analysis results.

    Takes the output of VideoAnalyzer and combines it with user metadata
    to create detailed user profiles suitable for answering questions.

    Usage:
        generator = ProfileGenerator(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
        profile = await generator.generate_profile(user_info, video_analyses)
    """

    PROFILE_SYSTEM_PROMPT = """You are an expert social media analyst and user profiling specialist.
You create detailed, insightful user profiles based on TikTok video analysis data.

Your profiles should be:
1. Data-driven: Based on the evidence from video analysis
2. Insightful: Go beyond surface observations
3. Actionable: Useful for understanding the creator
4. Balanced: Note both strengths and areas for improvement
5. Professional: Suitable for business/marketing context

Focus on identifying patterns, audience signals, and strategic insights."""

    PROFILE_GENERATION_PROMPT = """Based on the following TikTok user data and video analyses,
generate a comprehensive user profile.

## User Information
{user_info}

## Video Analyses
{video_analyses}

Generate a detailed profile as a JSON object with this structure:
{{
    "profile_summary": "2-3 paragraph comprehensive summary",
    "creator_type": "type of creator (e.g., lifestyle vlogger, tech educator)",
    "niche": "specific content niche",
    "estimated_influence_tier": "nano/micro/mid/macro/mega based on follower count",
    "primary_topics": ["topic1", "topic2", "topic3"],
    "content_format": "typical video format description",
    "posting_style": "description of posting approach",
    "content_patterns": [
        {{
            "pattern_type": "theme/format/timing/engagement",
            "description": "pattern description",
            "frequency": "how often seen",
            "examples": ["example1"]
        }}
    ],
    "audience_segments": [
        {{
            "segment_name": "segment name",
            "age_range": "estimated age range",
            "interests": ["interest1", "interest2"],
            "engagement_level": "high/medium/low",
            "description": "segment description"
        }}
    ],
    "primary_audience_description": "description of main audience",
    "brand_personality": {{
        "primary_archetype": "e.g., The Creator, The Explorer",
        "secondary_archetype": "secondary archetype",
        "tone_of_voice": "description of voice",
        "values": ["value1", "value2"],
        "differentiators": ["what makes them unique"]
    }},
    "engagement_strategy": "how they drive engagement",
    "community_building": "community tactics",
    "growth_potential": "growth assessment",
    "strengths": ["strength1", "strength2"],
    "areas_for_improvement": ["area1", "area2"],
    "collaboration_opportunities": ["type1", "type2"],
    "confidence_score": 0.0-1.0
}}

Respond ONLY with the JSON object, no markdown formatting."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.4,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def generate_profile(
        self,
        user_info: TikTokUserInfo,
        video_analyses: list[VideoAnalysisResult],
    ) -> UserProfile:
        """
        Generate a comprehensive user profile from scraped data and analyses.

        Args:
            user_info: Scraped TikTok user information
            video_analyses: List of video analysis results

        Returns:
            Complete UserProfile

        Raises:
            ProfileGenerationError: If profile generation fails
        """
        logger.info(
            "generating_profile",
            username=user_info.username,
            videos_analyzed=len(video_analyses),
        )

        # Format user info for the prompt
        user_info_text = user_info.to_analysis_text()

        # Format video analyses
        video_analyses_text = "\n\n".join(
            self._format_video_analysis(va) for va in video_analyses
        )

        prompt = self.PROFILE_GENERATION_PROMPT.format(
            user_info=user_info_text,
            video_analyses=video_analyses_text,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.PROFILE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()
            response_text = self._clean_json_response(response_text)
            profile_data = json.loads(response_text)

            # Build the UserProfile
            profile = UserProfile(
                username=user_info.username,
                display_name=user_info.display_name,
                bio=user_info.bio,
                profile_summary=profile_data.get("profile_summary", ""),
                creator_type=profile_data.get("creator_type", ""),
                niche=profile_data.get("niche", ""),
                estimated_influence_tier=profile_data.get("estimated_influence_tier", ""),
                primary_topics=profile_data.get("primary_topics", []),
                content_format=profile_data.get("content_format", ""),
                posting_style=profile_data.get("posting_style", ""),
                content_patterns=self._parse_content_patterns(
                    profile_data.get("content_patterns", [])
                ),
                audience_segments=self._parse_audience_segments(
                    profile_data.get("audience_segments", [])
                ),
                primary_audience_description=profile_data.get(
                    "primary_audience_description", ""
                ),
                brand_personality=self._parse_brand_personality(
                    profile_data.get("brand_personality")
                ),
                engagement_strategy=profile_data.get("engagement_strategy", ""),
                community_building=profile_data.get("community_building", ""),
                growth_potential=profile_data.get("growth_potential", ""),
                strengths=profile_data.get("strengths", []),
                areas_for_improvement=profile_data.get("areas_for_improvement", []),
                collaboration_opportunities=profile_data.get(
                    "collaboration_opportunities", []
                ),
                videos_analyzed=len(video_analyses),
                video_analyses=video_analyses,
                generated_at=datetime.utcnow(),
                confidence_score=profile_data.get("confidence_score", 0.5),
            )

            logger.info(
                "profile_generated",
                username=user_info.username,
                creator_type=profile.creator_type,
                confidence=profile.confidence_score,
            )

            return profile

        except json.JSONDecodeError as e:
            logger.error("profile_json_error", error=str(e))
            raise ProfileGenerationError(f"Failed to parse profile JSON: {str(e)}") from e
        except Exception as e:
            raise ProfileGenerationError(
                f"Profile generation failed for @{user_info.username}: {str(e)}"
            ) from e

    def _format_video_analysis(self, va: VideoAnalysisResult) -> str:
        """Format a video analysis for the prompt."""
        parts = [
            f"### Video: {va.video_id}",
            f"Category: {va.content_category}",
            f"Summary: {va.content_summary}",
            f"Themes: {', '.join(va.content_themes)}",
            f"Tone: {va.tone}",
            f"Target Audience: {va.target_audience}",
            f"Production Quality: {va.production_quality}",
            f"Visual Aesthetic: {va.visual_aesthetic}",
            f"Engagement Hooks: {', '.join(va.engagement_hooks)}",
            f"Description: {va.description}",
            f"Hashtags: {', '.join(va.hashtags)}",
            f"Views: {va.views:,}, Likes: {va.likes:,}, Comments: {va.comments:,}",
        ]
        if va.frame_analyses:
            parts.append("Frame Observations:")
            for fa in va.frame_analyses:
                parts.append(f"  - {fa.scene_description} ({fa.mood_tone})")
        return "\n".join(parts)

    @staticmethod
    def _parse_content_patterns(data: list[dict]) -> list[ContentPattern]:
        """Parse content patterns from JSON data."""
        patterns = []
        for item in data:
            patterns.append(ContentPattern(
                pattern_type=item.get("pattern_type", ""),
                description=item.get("description", ""),
                frequency=item.get("frequency", ""),
                examples=item.get("examples", []),
            ))
        return patterns

    @staticmethod
    def _parse_audience_segments(data: list[dict]) -> list[AudienceSegment]:
        """Parse audience segments from JSON data."""
        segments = []
        for item in data:
            segments.append(AudienceSegment(
                segment_name=item.get("segment_name", ""),
                age_range=item.get("age_range", ""),
                interests=item.get("interests", []),
                engagement_level=item.get("engagement_level", ""),
                description=item.get("description", ""),
            ))
        return segments

    @staticmethod
    def _parse_brand_personality(data: Optional[dict]) -> Optional[BrandPersonality]:
        """Parse brand personality from JSON data."""
        if not data:
            return None
        return BrandPersonality(
            primary_archetype=data.get("primary_archetype", ""),
            secondary_archetype=data.get("secondary_archetype", ""),
            tone_of_voice=data.get("tone_of_voice", ""),
            values=data.get("values", []),
            differentiators=data.get("differentiators", []),
        )

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """Clean LLM response to extract valid JSON."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def estimate_influence_tier(self, followers: int) -> str:
        """
        Estimate the influence tier based on follower count.

        Standard industry tiers:
        - Nano: 1K - 10K
        - Micro: 10K - 100K
        - Mid-tier: 100K - 500K
        - Macro: 500K - 1M
        - Mega: 1M+
        """
        if followers >= 1_000_000:
            return "mega"
        elif followers >= 500_000:
            return "macro"
        elif followers >= 100_000:
            return "mid-tier"
        elif followers >= 10_000:
            return "micro"
        elif followers >= 1_000:
            return "nano"
        else:
            return "aspiring"
