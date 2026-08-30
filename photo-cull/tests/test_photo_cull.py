from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import photo_cull as photo_cull_module  # noqa: E402
from photo_cull import analyze_photos, create_cull_sidecars  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_photo(path: Path, offset: int) -> None:
    rng = np.random.default_rng(100 + offset)
    array = np.full((180, 260, 3), 115 + offset, dtype=np.uint8)
    array = np.clip(array + rng.integers(-8, 9, array.shape), 0, 255).astype(np.uint8)
    image = Image.fromarray(array, mode="RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35 + offset, 35, 145 + offset, 135), outline=(245, 245, 245), width=5)
    draw.line((10, 165, 245, 20 + offset), fill=(20, 20, 20), width=4)
    image.save(path, quality=95)


def test_analysis_is_read_only_and_refuses_report_overwrite(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    first = photos / "first.jpg"
    second = photos / "second.jpg"
    _make_photo(first, 0)
    _make_photo(second, 12)
    before = {path.name: _sha256(path) for path in (first, second)}

    output = tmp_path / "analysis"
    result = analyze_photos(photos, output, jobs=1)

    assert result["summary"]["total"] == 2
    assert Path(result["outputs"]["csv_report"]).is_file()
    assert Path(result["outputs"]["json_report"]).is_file()
    assert not first.with_suffix(".xmp").exists()
    assert before == {path.name: _sha256(path) for path in (first, second)}

    with pytest.raises(FileExistsError):
        analyze_photos(photos, output, jobs=1)


def test_xmp_write_is_explicit_and_preserves_existing_content(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    source = photos / "frame.jpg"
    _make_photo(source, 4)
    source_hash = _sha256(source)
    sidecar = source.with_suffix(".xmp")
    sidecar.write_text(
        '<rdf:Description xmp:Rating="2" xmp:Label="Blue">'
        "<dc:subject>ExistingKeyword</dc:subject>"
        '<dc:description><rdf:li xml:lang="x-default">old</rdf:li></dc:description>'
        "</rdf:Description>",
        encoding="utf-8",
    )

    result = create_cull_sidecars(photos, tmp_path / "confirmed", jobs=1)

    updated = sidecar.read_text(encoding="utf-8")
    assert result["xmp_written"] is True
    assert "ExistingKeyword" in updated
    assert 'xmp:Rating="' in updated
    assert "photo-cull:" in updated
    assert _sha256(source) == source_hash


def test_invalid_preset_is_a_value_error(tmp_path: Path) -> None:
    source = tmp_path / "frame.jpg"
    _make_photo(source, 1)
    with pytest.raises(ValueError, match="预设不存在"):
        analyze_photos(source, tmp_path / "output", preset="unknown")


def test_report_failure_happens_before_any_xmp_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    source = photos / "frame.jpg"
    _make_photo(source, 3)

    def fail_report(*_args, **_kwargs):
        raise OSError("simulated report failure")

    monkeypatch.setattr(photo_cull_module.report, "write_csv", fail_report)
    with pytest.raises(OSError, match="simulated report failure"):
        create_cull_sidecars(photos, tmp_path / "confirmed", jobs=1)

    assert not source.with_suffix(".xmp").exists()


def test_disabled_xmp_output_is_reported_truthfully(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    source = photos / "frame.jpg"
    _make_photo(source, 5)

    result = create_cull_sidecars(
        photos,
        tmp_path / "confirmed",
        jobs=1,
        overrides={"output.write_xmp": False},
    )

    assert result["xmp_written"] is False
    assert result["xmp_paths"] == []
    assert not source.with_suffix(".xmp").exists()
