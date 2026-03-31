"""Unit tests for the video frame extractor."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scraper.frame_extractor import FrameExtractor, FrameExtractionError


class TestFrameExtractor:
    """Tests for FrameExtractor."""

    def test_init_creates_output_dir(self, tmp_path):
        """Test that initialization creates the output directory."""
        output_dir = tmp_path / "frames"
        extractor = FrameExtractor(output_dir=output_dir)
        assert output_dir.exists()

    def test_uniform_indices(self):
        """Test uniform frame index selection."""
        extractor = FrameExtractor()
        indices = extractor._uniform_indices(total_frames=100, num_frames=5)

        assert len(indices) == 5
        # Should be roughly evenly spaced
        assert indices[0] >= 0
        assert indices[-1] <= 100
        # Check ordering
        assert indices == sorted(indices)

    def test_uniform_indices_few_frames(self):
        """Test uniform selection when requesting more than available."""
        extractor = FrameExtractor()
        indices = extractor._uniform_indices(total_frames=3, num_frames=10)
        assert len(indices) == 3

    def test_uniform_indices_single(self):
        """Test uniform selection for single frame."""
        extractor = FrameExtractor()
        indices = extractor._uniform_indices(total_frames=100, num_frames=1)
        assert len(indices) == 1

    def test_resize_frame_downscale(self):
        """Test that large frames are downscaled."""
        extractor = FrameExtractor(target_size=(640, 360))
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        resized = extractor._resize_frame(frame)

        assert resized.shape[1] <= 640
        assert resized.shape[0] <= 360

    def test_resize_frame_no_upscale(self):
        """Test that small frames are not upscaled."""
        extractor = FrameExtractor(target_size=(1280, 720))
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        resized = extractor._resize_frame(frame)

        # Should not upscale
        assert resized.shape[0] == 360
        assert resized.shape[1] == 640

    def test_frame_to_base64(self, tmp_path):
        """Test converting a frame image to base64."""
        # Create a small test image
        import cv2
        test_image = np.zeros((10, 10, 3), dtype=np.uint8)
        test_path = tmp_path / "test.jpg"
        cv2.imwrite(str(test_path), test_image)

        base64_str = FrameExtractor.frame_to_base64(test_path)
        assert isinstance(base64_str, str)
        assert len(base64_str) > 0

    def test_frames_to_base64(self, tmp_path):
        """Test batch frame to base64 conversion."""
        import cv2
        paths = []
        for i in range(3):
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            path = tmp_path / f"test_{i}.jpg"
            cv2.imwrite(str(path), img)
            paths.append(path)

        results = FrameExtractor.frames_to_base64(paths)
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)

    @pytest.mark.asyncio
    async def test_extract_frames_missing_file(self, tmp_path):
        """Test extraction with missing video file."""
        extractor = FrameExtractor(output_dir=tmp_path / "frames")
        with pytest.raises(FrameExtractionError, match="not found"):
            await extractor.extract_frames(tmp_path / "nonexistent.mp4")

    def test_get_video_info_missing_file(self, tmp_path):
        """Test getting info for missing video."""
        extractor = FrameExtractor()
        info = extractor.get_video_info(tmp_path / "nonexistent.mp4")
        assert "error" in info
