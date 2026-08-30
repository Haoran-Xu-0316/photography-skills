"""Behavioral checks for the photo-color-grade programmatic API."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from color_engine import load_image
from photo_color_grade import (
    analyze_photo,
    build_preview,
    grade_photo,
    grade_series,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_photo(path: Path, cast: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> Path:
    height, width = 180, 260
    x = np.linspace(0.08, 0.76, width, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 0.15, height, dtype=np.float32)[:, None]
    base = np.clip(x + y, 0.0, 0.88)
    rgb = np.stack(
        [
            np.clip(base * cast[0], 0.0, 0.94),
            np.clip((base * 0.96 + 0.02) * cast[1], 0.0, 0.94),
            np.clip((base * 0.90 + 0.035) * cast[2], 0.0, 0.94),
        ],
        axis=2,
    )
    Image.fromarray(np.round(rgb * 255.0).astype(np.uint8), mode="RGB").save(path)
    return path


def test_analyze_and_preview_are_traceable(tmp_path: Path) -> None:
    source = _make_photo(tmp_path / "source.png", cast=(1.05, 1.0, 0.92))
    source_hash = _hash(source)

    analysis = analyze_photo(source)
    preview = build_preview(
        source, tmp_path / "preview", mode="look", look="warm-documentary"
    )

    assert analysis["width"] == 260
    assert analysis["height"] == 180
    assert "white_balance" in analysis["analysis"]
    assert Path(preview["preview"]).is_file()
    assert Path(preview["report"]).is_file()
    assert _hash(source) == source_hash


def test_grade_preserves_source_and_dimensions(tmp_path: Path) -> None:
    source = _make_photo(tmp_path / "source.png")
    source_hash = _hash(source)

    result = grade_photo(source, tmp_path / "output", mode="correct")

    output = Path(result["output"])
    assert result["status"] == "review_required"
    assert result["technical_status"] == "pass"
    assert output.is_file()
    assert Path(result["recipe"]).is_file()
    assert Path(result["validation"]).is_file()
    assert load_image(source).rgb.shape == load_image(output).rgb.shape
    assert _hash(source) == source_hash

    with pytest.raises(FileExistsError):
        grade_photo(source, tmp_path / "output", mode="correct")


def test_reference_match_and_series_create_independent_outputs(tmp_path: Path) -> None:
    anchor = _make_photo(tmp_path / "anchor.png", cast=(1.07, 1.0, 0.92))
    second = _make_photo(tmp_path / "second.png", cast=(0.92, 1.0, 1.08))

    matched = grade_photo(
        second,
        tmp_path / "matched",
        mode="match",
        reference_path=anchor,
        strength=0.7,
    )
    series = grade_series(
        [anchor, second],
        tmp_path / "series",
        anchor,
        look="natural-clean",
        match_strength=0.25,
    )

    assert Path(matched["output"]).is_file()
    assert len(series["results"]) == 2
    assert all(item["status"] != "error" for item in series["results"])
    assert all(Path(item["output"]).is_file() for item in series["results"])


def test_sixteen_bit_tiff_stays_sixteen_bit(tmp_path: Path) -> None:
    values = np.linspace(2000, 54000, 160 * 220, dtype=np.uint16).reshape(160, 220)
    rgb = np.stack([values, np.minimum(values + 1500, 65535), values], axis=2)
    source = tmp_path / "source16.tif"
    tifffile.imwrite(source, rgb, photometric="rgb", metadata=None)

    result = grade_photo(
        source, tmp_path / "output16", mode="look", look="soft-film", strength=0.7
    )
    rendered = load_image(result["output"])

    assert rendered.bit_depth == 16
    assert rendered.rgb.shape == rgb.shape


def test_preview_preflights_report_before_writing_image(tmp_path: Path) -> None:
    source = _make_photo(tmp_path / "source.png")
    output = tmp_path / "preview"
    output.mkdir()
    report = output / "source_look_preview.json"
    report.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_preview(source, output, mode="look", look="natural-clean")

    assert not (output / "source_look_preview.jpg").exists()
    assert report.read_text(encoding="utf-8") == "existing"


def test_series_rejects_duplicate_output_names_before_writing(tmp_path: Path) -> None:
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _make_photo(first_dir / "same.png")
    second = _make_photo(second_dir / "same.png", cast=(0.92, 1.0, 1.06))
    output = tmp_path / "series"

    with pytest.raises(ValueError, match="同名输出"):
        grade_series([first, second], output, first)

    assert not output.exists()
