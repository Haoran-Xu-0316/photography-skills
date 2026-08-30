from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from photo_print_layout import analyze_print_layout, create_print_layout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_image(path: Path, size: tuple[int, int], color: str) -> None:
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4),
        fill="white",
    )
    image.save(path, quality=95)


def test_analyze_contain_preserves_full_source(tmp_path: Path) -> None:
    source = tmp_path / "wide.jpg"
    _make_image(source, (1800, 1200), "#155EEF")

    plan = analyze_print_layout(
        [source],
        paper_size_mm=(100, 120),
        grid=(1, 1),
        fit_strategy="contain",
        margins_mm=10,
        crop_marks=False,
    )

    placement = plan["pages"][0]["placements"][0]
    assert placement["source_crop_px"] == [0, 0, 1800, 1200]
    assert placement["destination_mm"][2] == pytest.approx(80, abs=0.01)
    assert placement["destination_mm"][3] < 100


def test_cover_requires_explicit_strategy_and_reports_crop(tmp_path: Path) -> None:
    source = tmp_path / "portrait.jpg"
    _make_image(source, (1200, 1800), "#A20F54")

    with pytest.raises(ValueError, match="fit_strategy"):
        analyze_print_layout(
            [source],
            paper_size_mm=(100, 100),
            grid=(1, 1),
            fit_strategy="cover",
        )

    plan = analyze_print_layout(
        [source],
        paper_size_mm=(100, 100),
        grid=(1, 1),
        fit_strategy="cover-top",
        margins_mm=0,
        bleed_mm=3,
    )
    placement = plan["pages"][0]["placements"][0]
    assert placement["source_crop_px"][1] == 0
    assert placement["source_crop_px"][3] < 1800
    assert placement["destination_mm"][0] < plan["trim_origin_mm"][0]


def test_low_resolution_is_blocked_by_default(tmp_path: Path) -> None:
    source = tmp_path / "small.jpg"
    _make_image(source, (200, 150), "#7A5AF8")

    with pytest.raises(ValueError, match="Low-resolution placement blocked"):
        create_print_layout(
            [source],
            tmp_path / "blocked",
            paper_size_mm=(100, 100),
            grid=(1, 1),
            fit_strategy="contain",
            margins_mm=0,
            minimum_ppi=240,
            crop_marks=False,
        )
    assert not (tmp_path / "blocked").exists()


def test_create_multipicture_layout_and_preserve_sources(tmp_path: Path) -> None:
    sources = []
    for index, color in enumerate(("#004EEB", "#D92D20", "#079455", "#DC6803")):
        source = tmp_path / f"photo_{index}.jpg"
        _make_image(source, (2400, 1600), color)
        sources.append(source)
    hashes_before = {path: _sha256(path) for path in sources}
    output_dir = tmp_path / "layout"

    result = create_print_layout(
        sources,
        output_dir,
        paper_size_mm=(148, 210),
        grid=(2, 2),
        fit_strategy="contain",
        margins_mm=(12, 10, 16, 18),
        gap_mm=5,
        bleed_mm=3,
        binding_edge="left",
        binding_safe_mm=7,
        dpi=150,
        minimum_ppi=200,
        output_basename="a5_contact",
    )

    assert result["page_count"] == 1
    assert Path(result["outputs"]["pdf"]).read_bytes().startswith(b"%PDF")
    print_page = Image.open(result["outputs"]["print_pages"][0])
    expected_width = round(result["media_size_mm"][0] * 150 / 25.4)
    assert print_page.width == expected_width
    assert Path(result["outputs"]["previews"][0]).is_file()
    manifest = json.loads(Path(result["outputs"]["manifest_json"]).read_text())
    assert len(manifest["pages"][0]["placements"]) == 4
    assert all(_sha256(path) == hashes_before[path] for path in sources)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        create_print_layout(
            sources,
            output_dir,
            paper_size_mm=(148, 210),
            grid=(2, 2),
            fit_strategy="contain",
            margins_mm=(12, 10, 16, 18),
            gap_mm=5,
            bleed_mm=3,
            binding_edge="left",
            binding_safe_mm=7,
            dpi=150,
            minimum_ppi=200,
            output_basename="a5_contact",
        )


def test_binding_safe_area_prevents_false_edge_bleed(tmp_path: Path) -> None:
    source = tmp_path / "bound.jpg"
    _make_image(source, (1800, 1200), "#175CD3")

    plan = analyze_print_layout(
        [source],
        paper_size_mm=(100, 100),
        grid=(1, 1),
        fit_strategy="cover-center",
        margins_mm=0,
        bleed_mm=3,
        binding_edge="left",
        binding_safe_mm=10,
    )

    placement = plan["pages"][0]["placements"][0]
    expected_x = plan["trim_origin_mm"][0] + 10
    assert placement["destination_mm"][0] == pytest.approx(expected_x, abs=0.01)


def test_output_basename_cannot_escape_output_directory(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    _make_image(source, (1200, 1200), "#039855")

    with pytest.raises(ValueError, match="output_basename"):
        create_print_layout(
            [source],
            tmp_path / "layout",
            paper_size_mm=(50, 50),
            grid=(1, 1),
            fit_strategy="contain",
            margins_mm=5,
            dpi=72,
            minimum_ppi=72,
            crop_marks=False,
            output_basename="../escaped",
        )

    assert not (tmp_path / "escaped.pdf").exists()
