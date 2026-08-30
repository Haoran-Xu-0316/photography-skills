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

from photo_panorama_stitcher import analyze_panorama, stitch_panorama


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wide_scene(height: int = 210, width: int = 720) -> np.ndarray:
    rng = np.random.default_rng(20260830)
    x = np.linspace(25, 185, width, dtype=np.float32)
    y = np.linspace(5, 48, height, dtype=np.float32)[:, None]
    base = np.clip(x + y, 0, 255)
    scene = np.dstack((base * 0.82, base * 0.96, base)).astype(np.uint8)
    for index, center_x in enumerate(range(45, width, 73)):
        color = (
            int(35 + (index * 37) % 190),
            int(55 + (index * 61) % 175),
            int(45 + (index * 83) % 185),
        )
        cv2.circle(scene, (center_x, 50 + (index % 4) * 31), 18, color, -1)
        cv2.rectangle(
            scene,
            (center_x - 23, 140 - (index % 3) * 18),
            (center_x + 29, 185),
            color[::-1],
            3,
        )
        cv2.putText(
            scene,
            f"P{index:02d}",
            (center_x - 25, 32 + (index % 2) * 87),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (245, 245, 245),
            2,
            cv2.LINE_AA,
        )
    noise = rng.normal(0, 4, scene.shape).astype(np.int16)
    return np.clip(scene.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def _write_panorama_inputs(directory: Path) -> list[Path]:
    directory.mkdir(parents=True)
    scene = _wide_scene()
    paths: list[Path] = []
    for index, start in enumerate((0, 200, 400)):
        crop = scene[:, start : start + 320]
        path = directory / f"view_{index}.png"
        assert cv2.imwrite(str(path), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
        paths.append(path)
    return paths


def test_analysis_proves_overlap_and_new_view(tmp_path: Path) -> None:
    paths = _write_panorama_inputs(tmp_path / "inputs")

    result = analyze_panorama(paths)

    assert result["status"] == "ready"
    assert result["blockers"] == []
    assert result["projection"]["model"] == "planar"
    assert len(result["pairs"]) == 2
    for pair in result["pairs"]:
        assert pair["ransac_inlier_count"] >= 8
        assert pair["estimated_overlap_share"] >= 0.08
        assert pair["estimated_view_extension_share"] >= 0.05
    assert result["estimated_canvas_size"][0] > 600


def test_stitch_outputs_reproducible_report_and_preserves_sources(
    tmp_path: Path,
) -> None:
    paths = _write_panorama_inputs(tmp_path / "inputs")
    before = {path: _hash(path) for path in paths}
    output_dir = tmp_path / "outputs"

    result = stitch_panorama(paths, output_dir)

    expected = {
        "panorama_16bit.tif",
        "panorama_preview.jpg",
        "valid_area_mask.png",
        "seam_transition_map.png",
        "stitch_contact_sheet.jpg",
        "panorama_report.json",
    }
    assert expected == {path.name for path in output_dir.iterdir()}
    assert all(_hash(path) == digest for path, digest in before.items())
    assert result["recipe"]["generative_fill"] is False
    assert result["source_hashes_verified_after_processing"] is True
    assert result["final_size"][0] > 600
    saved = json.loads((output_dir / "panorama_report.json").read_text())
    assert saved["claim_boundary"].startswith("uses only pixels recorded")

    panorama = cv2.imread(
        str(output_dir / "panorama_16bit.tif"),
        cv2.IMREAD_UNCHANGED,
    )
    assert panorama is not None
    assert panorama.dtype == np.uint16
    assert panorama.shape[1] == result["final_size"][0]
    assert panorama.shape[0] == result["final_size"][1]
    valid_mask = cv2.imread(
        str(output_dir / "valid_area_mask.png"),
        cv2.IMREAD_UNCHANGED,
    )
    assert valid_mask is not None
    assert valid_mask.shape == panorama.shape[:2]


def test_same_view_duplicate_is_not_a_panorama(tmp_path: Path) -> None:
    scene = _wide_scene()[:, :320]
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    assert cv2.imwrite(str(first), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    second.write_bytes(first.read_bytes())

    result = analyze_panorama([first, second])

    assert result["status"] == "blocked"
    assert "duplicate_source_content" in result["blockers"]
    assert any("insufficient_view_extension" in item for item in result["blockers"])
    with pytest.raises(ValueError, match="Blocked panorama"):
        stitch_panorama([first, second], tmp_path / "outputs")


def test_nonoverlapping_images_are_blocked(tmp_path: Path) -> None:
    rng = np.random.default_rng(9)
    first_array = rng.integers(0, 255, (180, 260, 3), dtype=np.uint8)
    second_array = rng.integers(0, 255, (180, 260, 3), dtype=np.uint8)
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    assert cv2.imwrite(str(first), first_array)
    assert cv2.imwrite(str(second), second_array)

    result = analyze_panorama([first, second])

    assert result["status"] == "blocked"
    assert any(
        token in blocker
        for blocker in result["blockers"]
        for token in ("insufficient_feature_matches", "homography_unavailable")
    )


def test_cylindrical_projection_discloses_estimated_focal_length(
    tmp_path: Path,
) -> None:
    paths = _write_panorama_inputs(tmp_path / "inputs")[:2]

    result = analyze_panorama(paths, projection="cylindrical")

    assert result["projection"]["focal_length_source"] == "estimated"
    assert result["projection"]["focal_length_px"] > 0
    assert "estimated_cylindrical_focal_length" in result["warnings"]


def test_inputs_and_outputs_are_guarded(tmp_path: Path) -> None:
    paths = _write_panorama_inputs(tmp_path / "inputs")
    with pytest.raises(ValueError, match="at least two"):
        analyze_panorama(paths[:1])
    with pytest.raises(ValueError, match="projection"):
        analyze_panorama(paths, projection="spherical")
    with pytest.raises(ValueError, match="only used with cylindrical"):
        analyze_panorama(paths, projection="planar", focal_length_px=500)

    output_dir = tmp_path / "outputs"
    stitch_panorama(paths, output_dir)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        stitch_panorama(paths, output_dir)


def test_identical_pixels_with_different_encodings_are_not_a_panorama(
    tmp_path: Path,
) -> None:
    scene = _wide_scene()[:, :320]
    png_path = tmp_path / "same.png"
    tiff_path = tmp_path / "same.tif"
    assert cv2.imwrite(str(png_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    assert cv2.imwrite(str(tiff_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))

    result = analyze_panorama([png_path, tiff_path])

    assert "duplicate_source_content" in result["blockers"]
