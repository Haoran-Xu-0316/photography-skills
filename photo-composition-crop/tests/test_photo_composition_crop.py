from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_composition_crop import analyze_composition, create_crop_set


def _fixture(root: Path) -> Path:
    height, width = 240, 400
    rgb = np.full((height, width, 3), [222, 219, 206], dtype=np.uint8)
    yy, xx = np.mgrid[0:height, 0:width]
    subject = ((xx - 325) / 42) ** 2 + ((yy - 120) / 68) ** 2 < 1
    rgb[subject] = [180, 45, 36]
    path = root / "composition.png"
    Image.fromarray(rgb, mode="RGB").save(path)
    return path


def test_multi_ratio_outputs_and_original_preservation(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    result = create_crop_set(
        source,
        tmp_path / "out",
        aspect_ratios=("1:1", "4:5", "16:9"),
        focus_point=(0.81, 0.5),
    )
    assert result["status"] == "review_required"
    assert len(result["crops"]) == 3
    expected = [(240, 240), (192, 240), (400, 225)]
    for output, size in zip(result["crops"], expected, strict=True):
        with Image.open(output) as image:
            assert image.size == size
    assert Path(result["overlay"]).is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


def test_safe_area_only_and_focus_point(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    analysis = analyze_composition(source, focus_point=(0.82, 0.5))
    result = create_crop_set(
        source,
        tmp_path / "safe",
        aspect_ratios=("1:1",),
        focus_point=(0.82, 0.5),
        safe_area_only=True,
    )
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    left = manifest["plans"][0]["candidates"][0]["coordinates"]["normalized"]["left"]
    assert analysis["focus_source"] == "user"
    assert not result["crops"]
    assert left > 0.25


def test_equivalent_aspect_ratios_are_rejected(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    output = tmp_path / "duplicate"
    with pytest.raises(ValueError, match="重复画幅"):
        create_crop_set(source, output, aspect_ratios=("1:1", "2:2"))
    assert not output.exists()
