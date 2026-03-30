"""
Video frame extraction module.

Extracts keyframes from downloaded TikTok videos for multimodal
LLM analysis. Uses OpenCV for efficient frame extraction with
intelligent keyframe selection.
"""

import asyncio
import base64
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from src.logging_config import get_logger

logger = get_logger(__name__)


class FrameExtractionError(Exception):
    """Raised when frame extraction fails."""


class FrameExtractor:
    """
    Extracts keyframes from video files for LLM vision analysis.

    Implements multiple frame selection strategies:
    - Uniform: Evenly spaced frames across the video
    - Scene change: Frames at significant visual transitions
    - Hybrid: Combination of uniform + scene change detection

    Usage:
        extractor = FrameExtractor(output_dir="./data/frames")
        frames = await extractor.extract_frames("video.mp4", num_frames=5)
    """

    # Minimum frame difference threshold for scene change detection
    SCENE_CHANGE_THRESHOLD = 30.0
    # Target output resolution for frames
    TARGET_WIDTH = 1280
    TARGET_HEIGHT = 720
    # JPEG quality for saved frames
    JPEG_QUALITY = 85

    def __init__(
        self,
        output_dir: str | Path = "./data/frames",
        target_size: tuple[int, int] = (1280, 720),
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_size = target_size

    async def extract_frames(
        self,
        video_path: str | Path,
        num_frames: int = 5,
        strategy: str = "hybrid",
        video_id: Optional[str] = None,
    ) -> list[Path]:
        """
        Extract frames from a video file.

        Args:
            video_path: Path to the video file
            num_frames: Number of frames to extract
            strategy: Extraction strategy ('uniform', 'scene_change', 'hybrid')
            video_id: Optional ID for naming output files

        Returns:
            List of paths to extracted frame images

        Raises:
            FrameExtractionError: If frame extraction fails
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FrameExtractionError(f"Video file not found: {video_path}")

        if not video_id:
            video_id = video_path.stem

        logger.info(
            "extracting_frames",
            video_path=str(video_path),
            num_frames=num_frames,
            strategy=strategy,
        )

        # Run extraction in a thread pool
        frames = await asyncio.get_event_loop().run_in_executor(
            None,
            self._extract_frames_sync,
            video_path,
            num_frames,
            strategy,
            video_id,
        )

        logger.info("frames_extracted", count=len(frames), video_id=video_id)
        return frames

    def _extract_frames_sync(
        self,
        video_path: Path,
        num_frames: int,
        strategy: str,
        video_id: str,
    ) -> list[Path]:
        """Synchronous frame extraction."""
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise FrameExtractionError(f"Cannot open video: {video_path}")

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            if total_frames <= 0:
                raise FrameExtractionError(f"Video has no frames: {video_path}")

            # Select frame indices based on strategy
            if strategy == "uniform":
                frame_indices = self._uniform_indices(total_frames, num_frames)
            elif strategy == "scene_change":
                frame_indices = self._scene_change_indices(cap, total_frames, num_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset position
            else:  # hybrid
                frame_indices = self._hybrid_indices(cap, total_frames, num_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            # Extract and save frames
            frame_dir = self.output_dir / video_id
            frame_dir.mkdir(parents=True, exist_ok=True)

            saved_paths: list[Path] = []
            for idx, frame_num in enumerate(sorted(frame_indices)):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()
                if not ret:
                    continue

                # Resize frame
                frame = self._resize_frame(frame)

                # Save frame
                output_path = frame_dir / f"frame_{idx:03d}.jpg"
                cv2.imwrite(
                    str(output_path),
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY],
                )
                saved_paths.append(output_path)

            return saved_paths

        finally:
            cap.release()

    def _uniform_indices(self, total_frames: int, num_frames: int) -> list[int]:
        """Select uniformly spaced frame indices."""
        if num_frames >= total_frames:
            return list(range(total_frames))

        # Avoid first and last frames (often black/transition)
        start = int(total_frames * 0.05)
        end = int(total_frames * 0.95)
        step = (end - start) / (num_frames - 1) if num_frames > 1 else 1

        return [int(start + i * step) for i in range(num_frames)]

    def _scene_change_indices(
        self,
        cap: cv2.VideoCapture,
        total_frames: int,
        num_frames: int,
    ) -> list[int]:
        """Detect scene changes and select frames at transitions."""
        differences: list[tuple[int, float]] = []
        prev_frame = None
        sample_step = max(1, total_frames // 500)  # Sample up to 500 frames

        for frame_idx in range(0, total_frames, sample_step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # Convert to grayscale and resize for faster comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))

            if prev_frame is not None:
                diff = np.mean(np.abs(gray.astype(float) - prev_frame.astype(float)))
                differences.append((frame_idx, diff))

            prev_frame = gray

        if not differences:
            return self._uniform_indices(total_frames, num_frames)

        # Sort by difference score and take top N
        differences.sort(key=lambda x: x[1], reverse=True)
        scene_frames = [idx for idx, _ in differences[:num_frames]]

        # If not enough scene changes, supplement with uniform frames
        if len(scene_frames) < num_frames:
            uniform = self._uniform_indices(total_frames, num_frames - len(scene_frames))
            scene_frames.extend(uniform)

        return scene_frames[:num_frames]

    def _hybrid_indices(
        self,
        cap: cv2.VideoCapture,
        total_frames: int,
        num_frames: int,
    ) -> list[int]:
        """Combine uniform and scene change selection."""
        # Use half uniform, half scene change
        n_uniform = max(1, num_frames // 2)
        n_scene = num_frames - n_uniform

        uniform = set(self._uniform_indices(total_frames, n_uniform))
        scene = set(self._scene_change_indices(cap, total_frames, n_scene))

        combined = list(uniform | scene)
        combined.sort()

        # Trim to exact num_frames
        return combined[:num_frames]

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize frame to target dimensions maintaining aspect ratio."""
        h, w = frame.shape[:2]
        target_w, target_h = self.target_size

        # Calculate scale factor
        scale = min(target_w / w, target_h / h)
        if scale >= 1.0:
            return frame  # Don't upscale

        new_w = int(w * scale)
        new_h = int(h * scale)

        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def frame_to_base64(frame_path: str | Path) -> str:
        """
        Convert a frame image to base64 string for LLM API.

        Args:
            frame_path: Path to the frame image

        Returns:
            Base64-encoded string of the image
        """
        frame_path = Path(frame_path)
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def frames_to_base64(frame_paths: list[Path]) -> list[str]:
        """
        Convert multiple frames to base64 strings.

        Args:
            frame_paths: List of paths to frame images

        Returns:
            List of base64-encoded strings
        """
        return [FrameExtractor.frame_to_base64(p) for p in frame_paths]

    def get_video_info(self, video_path: str | Path) -> dict:
        """
        Get basic video information.

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary with video metadata (fps, frame_count, duration, resolution)
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))

        try:
            if not cap.isOpened():
                return {"error": f"Cannot open video: {video_path}"}

            return {
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "duration_seconds": (
                    cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                    if cap.get(cv2.CAP_PROP_FPS) > 0
                    else 0
                ),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }
        finally:
            cap.release()
