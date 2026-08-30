from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_output_preflight import inspect_delivery, prepare_web_copies


def _fixture(root: Path, size: tuple[int, int] = (1800, 1200)) -> Path:
    width, height = size
    xx = np.linspace(0, 255, width, dtype=np.uint8)
    rgb = np.empty((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = xx
    rgb[..., 1] = 110
    rgb[..., 2] = xx[::-1]
    path = root / "delivery.png"
    Image.fromarray(rgb, mode="RGB").save(path)
    return path


def test_web_inspection_and_safe_resize(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    inspection = inspect_delivery([source], tmp_path / "inspection", target="web")
    exports = prepare_web_copies([source], tmp_path / "exports", long_edge=900)
    assert inspection["status"] == "warning"
    assert exports["status"] == "pass"
    assert max(exports["exports"][0]["width"], exports["exports"][0]["height"]) == 900
    assert exports["exports"][0]["color_action"] == "missing-source-profile"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


def test_print_effective_ppi_blocks_low_resolution(tmp_path: Path) -> None:
    source = _fixture(tmp_path, size=(900, 600))
    result = inspect_delivery(
        [source],
        tmp_path / "print",
        target="print",
        print_width_cm=30,
        print_height_cm=20,
    )
    assert result["status"] == "blocked"
    assert result["files"][0]["effective_ppi"] < 240
    assert any(
        issue["code"] == "print-ppi-low" for issue in result["files"][0]["issues"]
    )


def test_embedded_profile_is_converted_and_retained(tmp_path: Path) -> None:
    source = tmp_path / "profiled.jpg"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (1200, 800), (80, 120, 160)).save(source, icc_profile=profile)
    result = prepare_web_copies([source], tmp_path / "profiled-export", long_edge=1000)
    output = Path(result["exports"][0]["output"])
    with Image.open(output) as image:
        exported_profile = image.info.get("icc_profile")
    assert result["exports"][0]["color_action"] == "converted-to-srgb"
    assert exported_profile


def test_web_export_rejects_destination_name_collision(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "same.png"
    second = second_dir / "same.jpg"
    Image.new("RGB", (800, 600), (30, 60, 90)).save(first)
    Image.new("RGB", (800, 600), (90, 60, 30)).save(second)
    with pytest.raises(ValueError, match="同名网页副本"):
        prepare_web_copies([first, second], tmp_path / "collision", long_edge=600)
