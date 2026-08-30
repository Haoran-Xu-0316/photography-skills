"""Behavioral checks for depth, parallax and relief outputs."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_to_3d import analyze_photo, convert_photo_to_3d, estimate_depth


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixtures(directory: Path) -> tuple[Path, Path]:
    height, width = 180, 260
    yy, xx = np.mgrid[0:height, 0:width]
    background = np.zeros((height, width, 3), dtype=np.float32)
    background[..., 0] = 0.18 + 0.48 * (1.0 - yy / height)
    background[..., 1] = 0.28 + 0.42 * (1.0 - yy / height)
    background[..., 2] = 0.42 + 0.40 * (1.0 - yy / height)
    subject = ((xx - 130) / 48) ** 2 + ((yy - 98) / 62) ** 2 < 1.0
    background[subject] = [0.76, 0.45, 0.28]
    photo_path = directory / "scene.png"
    Image.fromarray(np.round(np.clip(background, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB").save(photo_path)

    radial = np.sqrt(((xx - 130) / 150) ** 2 + ((yy - 98) / 115) ** 2)
    depth = np.clip(1.0 - radial, 0.0, 1.0)
    depth[subject] = np.maximum(depth[subject], 0.78)
    depth_path = directory / "depth.png"
    cv2.imwrite(str(depth_path), np.round(depth * 65535.0).astype(np.uint16))
    return photo_path, depth_path


def test_analyze_and_depth_from_user_map(tmp_path: Path) -> None:
    photo, depth = _fixtures(tmp_path)
    source_hash = _hash(photo)

    analysis = analyze_photo(photo)
    result = estimate_depth(photo, tmp_path / "depth_output", depth_map_path=depth)

    assert analysis["width"] == 260
    assert analysis["height"] == 180
    assert Path(result["depth"]).is_file()
    assert result["quality"]["status"] == "pass"
    assert _hash(photo) == source_hash


def test_bundle_contains_parallax_and_relief(tmp_path: Path) -> None:
    photo, depth = _fixtures(tmp_path)
    source_hash = _hash(photo)

    result = convert_photo_to_3d(
        photo,
        tmp_path / "bundle",
        mode="bundle",
        depth_map_path=depth,
        mesh_resolution=96,
    )

    assert result["status"] == "pass"
    for path in result["outputs"].values():
        assert Path(path).is_file()
    html = Path(result["outputs"]["html"]).read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in html
    assert "data:image/png;base64," in html
    obj = Path(result["outputs"]["obj"]).read_text(encoding="utf-8")
    assert obj.count("\nv ") > 4000
    assert obj.count("\nf ") > 7900
    with Image.open(result["outputs"]["gif"]) as animation:
        assert animation.n_frames == 24
    assert _hash(photo) == source_hash


def test_invert_depth_and_collision_protection(tmp_path: Path) -> None:
    photo, depth = _fixtures(tmp_path)
    normal = estimate_depth(photo, tmp_path / "normal", depth_map_path=depth)
    inverted = estimate_depth(photo, tmp_path / "inverted", depth_map_path=depth, invert_depth=True)
    normal_array = cv2.imread(normal["depth"], cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    inverted_array = cv2.imread(inverted["depth"], cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0

    assert np.mean(np.abs(normal_array + inverted_array - 1.0)) < 0.01

    output_dir = tmp_path / "collision"
    convert_photo_to_3d(photo, output_dir, mode="depth", depth_map_path=depth)
    with pytest.raises(FileExistsError):
        convert_photo_to_3d(photo, output_dir, mode="depth", depth_map_path=depth)


def test_missing_cached_model_fails_honestly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    photo, _ = _fixtures(tmp_path)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    with pytest.raises(RuntimeError, match="本地没有Depth Anything V2 Small缓存"):
        estimate_depth(photo, tmp_path / "model_output", allow_model_download=False)


def test_depth_map_must_preserve_pixel_correspondence(tmp_path: Path) -> None:
    photo, _ = _fixtures(tmp_path)
    mismatched = tmp_path / "square_depth.png"
    square = np.tile(np.arange(100, dtype=np.uint16), (100, 1)) * 600
    assert cv2.imwrite(str(mismatched), square)

    with pytest.raises(ValueError, match="宽高比不一致"):
        estimate_depth(
            photo,
            tmp_path / "mismatched_output",
            depth_map_path=mismatched,
        )


def test_source_photo_cannot_masquerade_as_depth_map(tmp_path: Path) -> None:
    photo, _ = _fixtures(tmp_path)

    with pytest.raises(ValueError, match="不能同时作为深度图"):
        estimate_depth(
            photo,
            tmp_path / "invalid_depth_output",
            depth_map_path=photo,
        )
