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

from photo_bracket_fusion import analyze_bracket, fuse_bracket


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_scene(height: int = 180, width: int = 260) -> np.ndarray:
    rng = np.random.default_rng(20260830)
    x = np.linspace(20, 170, width, dtype=np.float32)
    y = np.linspace(0, 45, height, dtype=np.float32)[:, None]
    base = np.clip(x + y, 0, 255)
    scene = np.dstack((base * 0.75, base * 0.9, base)).astype(np.uint8)
    cv2.rectangle(scene, (22, 28), (100, 145), (185, 80, 40), -1)
    cv2.circle(scene, (188, 82), 38, (35, 180, 110), -1)
    cv2.line(scene, (0, 160), (259, 110), (235, 225, 55), 7)
    noise = rng.normal(0, 3, scene.shape).astype(np.int16)
    return np.clip(scene.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def _write_bracket(
    directory: Path,
    *,
    moving_object: bool = False,
) -> list[Path]:
    directory.mkdir(parents=True)
    base = _make_scene()
    paths: list[Path] = []
    for index, scale in enumerate((0.5, 1.0, 1.7)):
        image = np.clip(base.astype(np.float32) * scale, 0, 255).astype(np.uint8)
        transform = np.float32([[1, 0, index - 1], [0, 1, 1 - index]])
        image = cv2.warpAffine(
            image,
            transform,
            (image.shape[1], image.shape[0]),
            borderMode=cv2.BORDER_REFLECT,
        )
        if moving_object and index == 2:
            cv2.rectangle(image, (126, 104), (158, 136), (250, 25, 25), -1)
        path = directory / f"frame_{index}.png"
        assert cv2.imwrite(str(path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        paths.append(path)
    return paths


def test_analyze_valid_bracket_reports_real_exposure_span(tmp_path: Path) -> None:
    paths = _write_bracket(tmp_path / "inputs")

    result = analyze_bracket(paths, exposure_times=[0.25, 0.5, 1.0])

    assert result["blockers"] == []
    assert result["exposure_source"] == "provided"
    assert result["exposure_span_ev"] == pytest.approx(2.0)
    assert len(result["alignment_shifts_xy"]) == 3
    assert min(result["same_view_confidence"]) >= 0.45


def test_duplicate_content_blocks_fusion(tmp_path: Path) -> None:
    scene = _make_scene()
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    assert cv2.imwrite(str(first), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    second.write_bytes(first.read_bytes())

    result = analyze_bracket([first, second], exposure_times=[0.5, 1.0])

    assert result["status"] == "blocked"
    assert "duplicate_content" in result["blockers"]
    with pytest.raises(ValueError, match="blocked fusion"):
        fuse_bracket(
            [first, second],
            tmp_path / "outputs",
            exposure_times=[0.5, 1.0],
        )


def test_fusion_outputs_report_and_preserves_sources(tmp_path: Path) -> None:
    paths = _write_bracket(tmp_path / "inputs", moving_object=True)
    before = {path: _hash(path) for path in paths}
    output_dir = tmp_path / "outputs"

    result = fuse_bracket(
        paths,
        output_dir,
        exposure_times=[0.25, 0.5, 1.0],
    )

    expected = {
        "exposure_fused_16bit.tif",
        "exposure_fused_preview.jpg",
        "ghost_risk_mask.png",
        "alignment_contact_sheet.jpg",
        "bracket_fusion_report.json",
    }
    assert expected == {path.name for path in output_dir.iterdir()}
    assert all(_hash(path) == digest for path, digest in before.items())
    assert result["recipe"]["claim_boundary"] == "not scene-linear HDR or a radiance map"
    assert result["source_hashes_verified_after_processing"] is True
    saved = json.loads((output_dir / "bracket_fusion_report.json").read_text())
    assert saved["recipe"]["fusion"].startswith("OpenCV MergeMertens")
    assert saved["ghost_risk"]["affected_share"] >= 0

    fused = cv2.imread(str(output_dir / "exposure_fused_16bit.tif"), cv2.IMREAD_UNCHANGED)
    assert fused is not None
    assert fused.dtype == np.uint16
    assert fused.shape[:2] == (180, 260)


def test_existing_outputs_are_never_overwritten(tmp_path: Path) -> None:
    paths = _write_bracket(tmp_path / "inputs")
    output_dir = tmp_path / "outputs"
    fuse_bracket(paths, output_dir, exposure_times=[0.25, 0.5, 1.0])

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        fuse_bracket(paths, output_dir, exposure_times=[0.25, 0.5, 1.0])


def test_single_image_is_not_accepted_as_a_bracket(tmp_path: Path) -> None:
    path = tmp_path / "single.png"
    assert cv2.imwrite(str(path), cv2.cvtColor(_make_scene(), cv2.COLOR_RGB2BGR))

    with pytest.raises(ValueError, match="at least two"):
        analyze_bracket([path])


def test_identical_pixels_with_different_encodings_are_not_a_bracket(
    tmp_path: Path,
) -> None:
    scene = _make_scene()
    png_path = tmp_path / "same.png"
    tiff_path = tmp_path / "same.tif"
    assert cv2.imwrite(str(png_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))
    assert cv2.imwrite(str(tiff_path), cv2.cvtColor(scene, cv2.COLOR_RGB2BGR))

    result = analyze_bracket(
        [png_path, tiff_path],
        exposure_times=[0.5, 1.0],
    )

    assert "duplicate_content" in result["blockers"]
