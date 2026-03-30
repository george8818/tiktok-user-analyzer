"""
Video Analyzer Module.

Uses Claude's multimodal (vision) capabilities to analyze
video frames and generate structured content analysis.
"""

import json
from pathlib import Path
from typing import Optional

import anthropic

from src.logging_config import get_logger
from src.analyzer.models import FrameAnalysis, VideoAnalysisResult
from src.scraper.models import TikTokVideoInfo
from src.scraper.frame_extractor import FrameExtractor

logger = get_logger(__name__)


class VideoAnalysisError(Exception):
    """Raised when video analysis fails."""


class VideoAnalyzer:
    """
    Analyzes TikTok video content using Claude's multimodal capabilities.

    Takes extracted video frames and metadata, sends them to Claude's
    vision API, and returns structured analysis results.

    Usage:
        analyzer = VideoAnalyzer(api_key="sk-ant-...", model="claude-sonnet-4-20250514")
        result = await analyzer.analyze_video(video_info, frame_paths)
    """

    # System prompt for video frame analysis
    FRAME_ANALYSIS_PROMPT = """You are an expert social media content analyst specializing in TikTok.
You analyze video frames to understand content, style, audience, and engagement patterns.

Analyze the provided video frames and metadata carefully. Consider:
1. What is happening in each frame (scene, setting, objects, people, text)
2. The overall content theme and category
3. Production quality and editing style
4. Target audience signals
5. Engagement techniques used
6. Mood, tone, and aesthetic

Be specific and insightful. Focus on actionable observations that would be useful
for understanding this creator and their content strategy."""

    VIDEO_ANALYSIS_PROMPT = """Based on the frame analysis and video metadata provided,
generate a comprehensive video analysis. Respond with a JSON object matching this schema:

{{
    "content_summary": "2-3 sentence summary of the video",
    "content_category": "primary category (e.g., lifestyle, tech, comedy, education)",
    "content_subcategories": ["subcategory1", "subcategory2"],
    "content_themes": ["theme1", "theme2", "theme3"],
    "production_quality": "assessment (professional/semi-pro/casual/low)",
    "editing_style": "description of editing approach",
    "visual_aesthetic": "description of visual style",
    "music_mood": "mood of music if applicable",
    "has_voiceover": true/false,
    "has_dialogue": true/false,
    "target_audience": "description of likely target audience",
    "tone": "overall tone (humorous/educational/inspirational/casual/etc.)",
    "engagement_hooks": ["hook1", "hook2"],
    "call_to_action": "CTA if any, or null"
}}

Video Metadata:
{metadata}

Frame Descriptions:
{frame_descriptions}

Respond ONLY with the JSON object, no markdown formatting."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        vision_model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.vision_model = vision_model or model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def analyze_frames(
        self,
        frame_paths: list[Path],
        video_info: Optional[TikTokVideoInfo] = None,
    ) -> list[FrameAnalysis]:
        """
        Analyze individual video frames using vision model.

        Args:
            frame_paths: Paths to extracted frame images
            video_info: Optional video metadata for context

        Returns:
            List of FrameAnalysis results
        """
        if not frame_paths:
            return []

        logger.info("analyzing_frames", count=len(frame_paths))

        # Build multimodal message with frames
        content: list[dict] = []

        # Add context text
        context = "Analyze the following video frames from a TikTok video."
        if video_info:
            context += f"\n\nVideo description: {video_info.description}"
            if video_info.hashtags:
                context += f"\nHashtags: {video_info.hashtag_string}"

        content.append({"type": "text", "text": context})

        # Add frame images
        for i, path in enumerate(frame_paths):
            base64_data = FrameExtractor.frame_to_base64(path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64_data,
                },
            })
            content.append({
                "type": "text",
                "text": f"Frame {i + 1} of {len(frame_paths)}",
            })

        content.append({
            "type": "text",
            "text": (
                "For each frame, describe:\n"
                "1. Scene description (what's happening)\n"
                "2. Objects visible\n"
                "3. Any text visible\n"
                "4. Mood/tone\n"
                "5. Setting/location\n\n"
                "Respond with a JSON array of objects, one per frame:\n"
                '[{"frame_index": 0, "scene_description": "...", '
                '"objects_detected": [...], "text_detected": "...", '
                '"mood_tone": "...", "setting": "..."}]\n\n'
                "Respond ONLY with the JSON array."
            ),
        })

        try:
            response = self.client.messages.create(
                model=self.vision_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.FRAME_ANALYSIS_PROMPT,
                messages=[{"role": "user", "content": content}],
            )

            response_text = response.content[0].text.strip()
            # Clean JSON response
            response_text = self._clean_json_response(response_text)

            frame_data = json.loads(response_text)

            analyses = []
            for fd in frame_data:
                analyses.append(FrameAnalysis(
                    frame_index=fd.get("frame_index", 0),
                    scene_description=fd.get("scene_description", ""),
                    objects_detected=fd.get("objects_detected", []),
                    text_detected=fd.get("text_detected", ""),
                    mood_tone=fd.get("mood_tone", ""),
                    setting=fd.get("setting", ""),
                ))

            return analyses

        except json.JSONDecodeError as e:
            logger.error("frame_analysis_json_error", error=str(e))
            return []
        except Exception as e:
            logger.error("frame_analysis_error", error=str(e))
            raise VideoAnalysisError(f"Frame analysis failed: {str(e)}") from e

    async def analyze_video(
        self,
        video_info: TikTokVideoInfo,
        frame_paths: list[Path],
    ) -> VideoAnalysisResult:
        """
        Perform comprehensive analysis of a single video.

        Args:
            video_info: Scraped video metadata
            frame_paths: Paths to extracted video frames

        Returns:
            Complete VideoAnalysisResult
        """
        logger.info("analyzing_video", video_id=video_info.video_id)

        # Step 1: Analyze individual frames
        frame_analyses = await self.analyze_frames(frame_paths, video_info)

        # Step 2: Generate comprehensive video analysis
        frame_descriptions = "\n".join(
            f"Frame {fa.frame_index}: {fa.scene_description} "
            f"(Setting: {fa.setting}, Mood: {fa.mood_tone})"
            for fa in frame_analyses
        )

        metadata = video_info.to_analysis_text()

        prompt = self.VIDEO_ANALYSIS_PROMPT.format(
            metadata=metadata,
            frame_descriptions=frame_descriptions,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()
            response_text = self._clean_json_response(response_text)
            analysis_data = json.loads(response_text)

            result = VideoAnalysisResult(
                video_id=video_info.video_id,
                video_url=video_info.url,
                content_summary=analysis_data.get("content_summary", ""),
                content_category=analysis_data.get("content_category", ""),
                content_subcategories=analysis_data.get("content_subcategories", []),
                content_themes=analysis_data.get("content_themes", []),
                frame_analyses=frame_analyses,
                production_quality=analysis_data.get("production_quality", ""),
                editing_style=analysis_data.get("editing_style", ""),
                visual_aesthetic=analysis_data.get("visual_aesthetic", ""),
                music_mood=analysis_data.get("music_mood", ""),
                has_voiceover=analysis_data.get("has_voiceover", False),
                has_dialogue=analysis_data.get("has_dialogue", False),
                target_audience=analysis_data.get("target_audience", ""),
                tone=analysis_data.get("tone", ""),
                engagement_hooks=analysis_data.get("engagement_hooks", []),
                call_to_action=analysis_data.get("call_to_action"),
                description=video_info.description,
                hashtags=video_info.hashtags,
                views=video_info.stats.views,
                likes=video_info.stats.likes,
                comments=video_info.stats.comments,
            )

            logger.info(
                "video_analysis_complete",
                video_id=video_info.video_id,
                category=result.content_category,
            )
            return result

        except json.JSONDecodeError as e:
            logger.error("video_analysis_json_error", error=str(e))
            # Return a minimal result
            return VideoAnalysisResult(
                video_id=video_info.video_id,
                video_url=video_info.url,
                content_summary="Analysis failed to parse",
                content_category="unknown",
                description=video_info.description,
                hashtags=video_info.hashtags,
            )
        except Exception as e:
            raise VideoAnalysisError(
                f"Video analysis failed for {video_info.video_id}: {str(e)}"
            ) from e

    @staticmethod
    def _clean_json_response(text: str) -> str:
        """Clean LLM response to extract valid JSON."""
        # Remove markdown code blocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
