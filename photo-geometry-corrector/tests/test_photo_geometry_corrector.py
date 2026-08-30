from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from photo_geometry_corrector import (
    analyze_geometry,
    correct_calibrated_distortion,
    correct_horizon,
    correct_perspective,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grid_photo(path: Path, width: int = 640, height: int = 420) -> Path:
    image = np.full((height, width, 3), 238, dtype=np.uint8)
    for x in range(40, width, 60):
        cv2.line(image, (x, 20), (x, height - 20), (40, 60, 80), 3)
    for y in range(40, height, 60):
        cv2.line(image, (20, y), (width - 20, y), (40, 60, 80), 3)
    Image.fromarray(image, mode="RGB").save(path, quality=98)
    return path


def _tilted_photo(path: Path, angle: float = 7.0) -> Path:
    width, height = 640, 420
    base = np.full((height, width, 3), 232, dtype=np.uint8)
    for y in (90, 170, 250, 330):
        cv2.line(base, (40, y), (600, y), (35, 45, 60), 5)
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -angle, 1.0)
    tilted = cv2.warpAffine(base, matrix, (width, height), borderValue=(245, 245, 245))
    Image.fromarray(tilted, mode="RGB").save(path, quality=98)
    return path


def test_analyze_and_correct_horizon_without_touching_source(tmp_path: Path) -> None:
    source = _tilted_photo(tmp_path / "tilted.jpg")
    source_hash = _hash(source)
    analysis = analyze_geometry(source)

    assert analysis["horizon"]["line_count"] > 0
    assert analysis["horizon"]["confidence"] >= 0.35
    assert analysis["horizon"]["angle_degrees"] == pytest.approx(7.0, abs=1.0)

    result = correct_horizon(source, tmp_path / "out", angle_degrees=7.0)
    assert result["status"] == "pass"
    assert result["crop_reason"] == "remove-transform-invalid-border-only"
    assert result["invalid_pixels_in_output"] == 0
    assert Path(result["output"]).is_file()
    assert Path(result["report"]).is_file()
    assert _hash(source) == source_hash
    with Image.open(result["output"]) as output:
        assert output.width > 0 and output.height > 0
    residual = analyze_geometry(result["output"])["horizon"]
    assert residual["angle_degrees"] == pytest.approx(0.0, abs=0.8)

    with pytest.raises(FileExistsError):
        correct_horizon(source, tmp_path / "out", angle_degrees=7.0)


def test_four_point_perspective_uses_exact_requested_plane(tmp_path: Path) -> None:
    source = _grid_photo(tmp_path / "facade.png", 500, 380)
    source_hash = _hash(source)
    points = [(70, 45), (430, 70), (455, 330), (45, 315)]

    result = correct_perspective(
        source,
        tmp_path / "perspective",
        points,
        output_size=(320, 220),
    )

    assert result["transform"] == "perspective"
    assert result["generated_fill"] is False
    assert result["crop_reason"] == "user-specified-plane-only"
    assert result["output_width"] == 320
    assert result["output_height"] == 220
    assert _hash(source) == source_hash
    with Image.open(result["output"]) as output:
        assert output.size == (320, 220)


def test_calibrated_distortion_crops_only_invalid_mapping(tmp_path: Path) -> None:
    source = _grid_photo(tmp_path / "grid.png")
    source_hash = _hash(source)
    camera_matrix = [[520.0, 0.0, 320.0], [0.0, 520.0, 210.0], [0.0, 0.0, 1.0]]
    distortion = [-0.18, 0.035, 0.0, 0.0, 0.0]

    result = correct_calibrated_distortion(
        source,
        tmp_path / "undistorted",
        camera_matrix,
        distortion,
    )

    assert result["status"] == "pass"
    assert result["transform"] == "calibrated-distortion"
    assert result["invalid_pixels_in_output"] == 0
    assert result["crop_reason"] == "remove-transform-invalid-border-only"
    assert result["output_width"] <= 640
    assert result["output_height"] <= 420
    assert _hash(source) == source_hash


def test_rejects_non_convex_or_out_of_range_geometry(tmp_path: Path) -> None:
    source = _grid_photo(tmp_path / "grid.png", 320, 240)
    with pytest.raises(ValueError):
        correct_perspective(
            source,
            tmp_path / "bad",
            [(0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9)],
            points_normalized=True,
        )
    with pytest.raises(ValueError):
        correct_calibrated_distortion(
            source,
            tmp_path / "bad-calibration",
            [[0, 0, 0], [0, 0, 0], [0, 0, 1]],
            [0, 0, 0],
        )
