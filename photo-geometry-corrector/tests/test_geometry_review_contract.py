from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import photo_geometry_corrector as geometry


def _tilted(path: Path) -> Path:
    image = np.full((260, 420, 3), 235, dtype=np.uint8)
    for y in (70, 130, 190):
        cv2.line(image, (20, y), (400, y), (25, 35, 50), 5)
    matrix = cv2.getRotationMatrix2D((210, 130), -6.0, 1.0)
    tilted = cv2.warpAffine(image, matrix, (420, 260), borderValue=(245, 245, 245))
    Image.fromarray(tilted, mode="RGB").save(path)
    return path


def test_automatic_horizon_requires_explicit_visual_confirmation(
    tmp_path: Path,
) -> None:
    source = _tilted(tmp_path / "tilted.png")
    analysis = geometry.analyze_geometry(source)
    assert analysis["horizon"]["confidence"] >= 0.35

    with pytest.raises(ValueError, match="视觉确认"):
        geometry.correct_horizon(source, tmp_path / "blocked")

    result = geometry.correct_horizon(
        source,
        tmp_path / "confirmed",
        automatic_detection_confirmed=True,
    )
    assert result["angle_source"] == "automatic-confirmed"
    assert result["acceptance_status"] == "visual-review-required"
    assert result["visual_review_required"] is True


def test_camera_matrix_requires_canonical_projective_row(tmp_path: Path) -> None:
    source = _tilted(tmp_path / "photo.png")
    with pytest.raises(ValueError, match="最后一行"):
        geometry.correct_calibrated_distortion(
            source,
            tmp_path / "invalid",
            [[400.0, 0.0, 210.0], [0.0, 400.0, 130.0], [0.1, 0.0, 1.0]],
            [0.0, 0.0, 0.0, 0.0],
        )
