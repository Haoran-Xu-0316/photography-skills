from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import photo_privacy_redactor as redactor


def _no_candidates(
    _rgb: np.ndarray,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    return [], {"available": True, "name": "test-detector", "reason": None}


def test_redacted_copy_is_lossless_png_for_jpeg_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (100, 80), (120, 150, 180)).save(source, quality=90)
    monkeypatch.setattr(redactor, "_detect_candidates", _no_candidates)

    result = redactor.redact_photo(
        source,
        tmp_path / "out",
        rectangles=[{"left": 10, "top": 10, "right": 40, "bottom": 40}],
    )
    output = Path(result["redacted_output"])
    assert output.suffix == ".png"
    with Image.open(output) as image:
        assert image.format == "PNG"
    assert result["output_encoding"] == "lossless-png"


def test_transparent_pixels_are_flattened_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "transparent.png"
    rgba = np.zeros((40, 50, 4), dtype=np.uint8)
    rgba[..., :3] = (255, 0, 0)
    rgba[..., 3] = 0
    Image.fromarray(rgba, mode="RGBA").save(source)
    monkeypatch.setattr(redactor, "_detect_candidates", _no_candidates)

    result = redactor.redact_photo(source, tmp_path / "flat")
    with Image.open(result["redacted_output"]) as image:
        pixels = np.asarray(image.convert("RGB"))
    assert np.all(pixels == 255)
    assert result["alpha_action"] == "flattened-on-opaque-white"
