from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from photo_focus_stacker import _blend_sources, analyze_focus_stack, stack_focus


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_textured_scene(height: int = 180, width: int = 270) -> np.ndarray:
    rng = np.random.default_rng(20260830)
    scene = np.zeros((height, width, 3), np.uint8)
    scene[:] = (198, 207, 216)
    for _ in range(180):
        x = int(rng.integers(0, width))
        y = int(rng.integers(0, height))
        radius = int(rng.integers(1, 5))
        color = tuple(int(item) for item in rng.integers(20, 235, 3))
        cv2.circle(scene, (x, y), radius, color, -1)
    cv2.putText(scene, "NEAR", (10, 88), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (15, 45, 185), 3)
    cv2.putText(scene, "FAR", (176, 115), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (185, 45, 15), 3)
    return scene


def _write_focus_sequence(directory: Path, moving_object: bool = False) -> list[Path]:
    directory.mkdir(parents=True)
    base = _make_textured_scene()
    blurred = cv2.GaussianBlur(base, (0, 0), 4.0)
    _, xx = np.mgrid[: base.shape[0], : base.shape[1]]
    centers = (40, 135, 230)
    paths: list[Path] = []
    for index, center in enumerate(centers):
        focus = np.exp(-0.5 * ((xx - center) / 42.0) ** 2).astype(np.float32)
        focus = cv2.GaussianBlur(focus, (0, 0), 5.0)[..., None]
        image = np.round(base * focus + blurred * (1.0 - focus)).astype(np.uint8)
        transform = np.float32([[1, 0, index - 1], [0, 1, 1 - index]])
        image = cv2.warpAffine(
            image,
            transform,
            (image.shape[1], image.shape[0]),
            borderMode=cv2.BORDER_REFLECT,
        )
        if moving_object and index == 2:
            cv2.rectangle(image, (118, 135), (150, 165), (245, 20, 20), -1)
        path = directory / f"focus_{index}.png"
        assert cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        paths.append(path)
    return paths


def test_analysis_detects_multiple_focus_sources(tmp_path: Path) -> None:
    paths = _write_focus_sequence(tmp_path / "inputs")

    result = analyze_focus_stack(paths)

    assert result["blockers"] == []
    assert len(result["focus_plane"]["tile_winner_source_indices"]) >= 2
    assert result["alignment"]["model"] == "rigid rotation and translation only"
    assert result["focus_breathing"]["applied_as_alignment_scale"] is False
    assert result["motion_or_breathing_risk"]["level"] == "low"


def test_stack_outputs_maps_report_and_preserves_sources(tmp_path: Path) -> None:
    paths = _write_focus_sequence(tmp_path / "inputs", moving_object=True)
    before = {path: _hash(path) for path in paths}
    output_dir = tmp_path / "outputs"

    result = stack_focus(paths, output_dir, blend_radius=5)

    expected = {
        "focus_stacked_16bit.tif",
        "focus_stacked_preview.jpg",
        "focus_source_map.png",
        "focus_confidence.png",
        "motion_or_breathing_risk_mask.png",
        "alignment_contact_sheet.jpg",
        "focus_stack_report.json",
    }
    assert expected == {path.name for path in output_dir.iterdir()}
    assert all(_hash(path) == digest for path, digest in before.items())
    assert result["recipe"]["claim_boundary"] == "no detail synthesized beyond recorded input frames"
    assert result["motion_or_breathing_risk"]["level"] == "high"

    saved = json.loads((output_dir / "focus_stack_report.json").read_text())
    assert saved["recipe"]["selection"].startswith("per-pixel")
    stacked = cv2.imread(str(output_dir / "focus_stacked_16bit.tif"), cv2.IMREAD_UNCHANGED)
    source_map = cv2.imread(str(output_dir / "focus_source_map.png"), cv2.IMREAD_UNCHANGED)
    assert stacked is not None and stacked.dtype == np.uint16
    assert source_map is not None and source_map.dtype == np.uint16
    assert stacked.shape[:2] == source_map.shape == (180, 270)


def test_duplicate_content_blocks_stack(tmp_path: Path) -> None:
    scene = _make_textured_scene()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    assert cv2.imwrite(str(first), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    second.write_bytes(first.read_bytes())

    analysis = analyze_focus_stack([first, second])

    assert "duplicate_content" in analysis["blockers"]
    with pytest.raises(ValueError, match="failed focus stacking checks"):
        stack_focus([first, second], tmp_path / "outputs")


def test_dimension_mismatch_is_blocked(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    scene = _make_textured_scene()
    assert cv2.imwrite(str(first), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    assert cv2.imwrite(str(second), cv2.cvtColor(scene[:, :-10], cv2.COLOR_RGB2BGR))

    result = analyze_focus_stack([first, second])

    assert result["status"] == "blocked"
    assert "dimension_mismatch" in result["blockers"]


def test_existing_outputs_are_never_overwritten(tmp_path: Path) -> None:
    paths = _write_focus_sequence(tmp_path / "inputs")
    output_dir = tmp_path / "outputs"
    stack_focus(paths, output_dir)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        stack_focus(paths, output_dir)


def test_single_image_is_not_a_focus_sequence(tmp_path: Path) -> None:
    path = tmp_path / "single.png"
    scene = _make_textured_scene()
    assert cv2.imwrite(str(path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))

    with pytest.raises(ValueError, match="at least two"):
        analyze_focus_stack([path])


def test_blending_never_uses_invalid_alignment_borders() -> None:
    first = np.full((12, 16, 3), 80, dtype=np.uint8)
    second = np.full((12, 16, 3), 220, dtype=np.uint8)
    first_valid = np.ones((12, 16), dtype=bool)
    second_valid = np.ones((12, 16), dtype=bool)
    second_valid[:, :5] = False
    source_map = np.zeros((12, 16), dtype=np.uint16)
    source_map[:, 5:] = 1

    blended = _blend_sources(
        [first, second],
        [first_valid, second_valid],
        source_map,
        blend_radius=6,
    )

    assert np.allclose(blended[:, :5], 80 / 255.0)


def test_identical_pixels_with_different_file_encodings_are_blocked(
    tmp_path: Path,
) -> None:
    scene = _make_textured_scene()
    png_path = tmp_path / "same.png"
    tiff_path = tmp_path / "same.tif"
    assert cv2.imwrite(str(png_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    assert cv2.imwrite(str(tiff_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))

    result = analyze_focus_stack([png_path, tiff_path])

    assert "duplicate_content" in result["blockers"]
