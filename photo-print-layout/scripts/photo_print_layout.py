"""Deterministic physical-page imposition for finalized photographs.

The public API is intentionally programmatic. It never modifies source images and
requires an explicit fit strategy so cropping cannot happen by accident.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MM_PER_INCH = 25.4
POINTS_PER_MM = 72.0 / MM_PER_INCH
SUPPORTED_FIT_STRATEGIES = {
    "contain",
    "cover-center",
    "cover-top",
    "cover-bottom",
}
SUPPORTED_BINDING_EDGES = {"none", "left", "right", "top", "bottom"}


@dataclass(frozen=True)
class SourceInfo:
    path: Path
    width_px: int
    height_px: int
    sha256: str
    has_icc_profile: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mm_to_px(value_mm: float, dpi: int) -> int:
    return round(value_mm * dpi / MM_PER_INCH)


def _as_positive_pair(value: Sequence[float], name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{name} must contain exactly two numbers")
    pair = (float(value[0]), float(value[1]))
    if pair[0] <= 0 or pair[1] <= 0:
        raise ValueError(f"{name} values must be positive")
    return pair


def _normalize_margins(
    margins_mm: float | Sequence[float],
) -> tuple[float, float, float, float]:
    if isinstance(margins_mm, (int, float)):
        values = (float(margins_mm),) * 4
    else:
        raw = tuple(float(value) for value in margins_mm)
        if len(raw) == 2:
            values = (raw[0], raw[1], raw[0], raw[1])
        elif len(raw) == 4:
            values = raw
        else:
            raise ValueError("margins_mm must be one, two, or four numbers")
    if any(value < 0 for value in values):
        raise ValueError("margins_mm values cannot be negative")
    return values


def _load_source_info(path: str | Path) -> SourceInfo:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source image not found: {source}")
    with Image.open(source) as opened:
        oriented = ImageOps.exif_transpose(opened)
        width_px, height_px = oriented.size
        has_icc_profile = bool(opened.info.get("icc_profile"))
    return SourceInfo(
        path=source,
        width_px=width_px,
        height_px=height_px,
        sha256=_sha256(source),
        has_icc_profile=has_icc_profile,
    )


def _source_crop_for_cover(
    source_width: int,
    source_height: int,
    target_width: float,
    target_height: float,
    fit_strategy: str,
) -> tuple[int, int, int, int]:
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_width = max(1, round(source_height * target_ratio))
        left = (source_width - crop_width) // 2
        return (left, 0, left + crop_width, source_height)

    crop_height = max(1, round(source_width / target_ratio))
    if fit_strategy == "cover-top":
        top = 0
    elif fit_strategy == "cover-bottom":
        top = source_height - crop_height
    else:
        top = (source_height - crop_height) // 2
    return (0, top, source_width, top + crop_height)


def _placement_for_slot(
    source: SourceInfo,
    slot_mm: tuple[float, float, float, float],
    paint_mm: tuple[float, float, float, float],
    fit_strategy: str,
) -> dict[str, Any]:
    slot_x, slot_y, slot_width, slot_height = slot_mm
    if fit_strategy == "contain":
        scale_mm_per_px = min(
            slot_width / source.width_px,
            slot_height / source.height_px,
        )
        placed_width = source.width_px * scale_mm_per_px
        placed_height = source.height_px * scale_mm_per_px
        destination = (
            slot_x + (slot_width - placed_width) / 2,
            slot_y + (slot_height - placed_height) / 2,
            placed_width,
            placed_height,
        )
        source_crop = (0, 0, source.width_px, source.height_px)
    else:
        destination = paint_mm
        source_crop = _source_crop_for_cover(
            source.width_px,
            source.height_px,
            paint_mm[2],
            paint_mm[3],
            fit_strategy,
        )

    crop_width = source_crop[2] - source_crop[0]
    crop_height = source_crop[3] - source_crop[1]
    effective_ppi = min(
        crop_width / (destination[2] / MM_PER_INCH),
        crop_height / (destination[3] / MM_PER_INCH),
    )
    return {
        "destination_mm": [round(value, 4) for value in destination],
        "source_crop_px": list(source_crop),
        "effective_ppi": round(effective_ppi, 2),
    }


def _extend_edge_slot_for_bleed(
    slot_mm: tuple[float, float, float, float],
    *,
    paper_width_mm: float,
    paper_height_mm: float,
    trim_origin_mm: float,
    bleed_mm: float,
    margins_mm: tuple[float, float, float, float],
    row: int,
    column: int,
    rows: int,
    columns: int,
) -> tuple[float, float, float, float]:
    x, y, width, height = slot_mm
    top, right, bottom, left = margins_mm
    if column == 0 and left == 0:
        x -= bleed_mm
        width += bleed_mm
    if column == columns - 1 and right == 0:
        width += bleed_mm
    if row == 0 and top == 0:
        y -= bleed_mm
        height += bleed_mm
    if row == rows - 1 and bottom == 0:
        height += bleed_mm
    return (x + trim_origin_mm, y + trim_origin_mm, width, height)


def _validate_output_basename(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("output_basename must be a non-empty filename stem")
    if len(value) > 128:
        raise ValueError("output_basename cannot exceed 128 characters")
    forbidden = set('/\\<>:"|?*')
    if (
        value in {".", ".."}
        or value.endswith((" ", "."))
        or any(character in forbidden or ord(character) < 32 for character in value)
    ):
        raise ValueError(
            "output_basename must be a filename stem without path separators "
            "or platform-reserved characters"
        )
    return value


def _validate_inputs(
    input_paths: Iterable[str | Path],
    *,
    paper_size_mm: Sequence[float],
    grid: Sequence[int],
    fit_strategy: str,
    margins_mm: float | Sequence[float],
    gap_mm: float,
    bleed_mm: float,
    binding_edge: str,
    binding_safe_mm: float,
    dpi: int,
    minimum_ppi: float,
    crop_mark_length_mm: float,
    crop_mark_gap_mm: float,
) -> tuple[
    list[SourceInfo],
    tuple[float, float],
    tuple[int, int],
    tuple[float, float, float, float],
]:
    paths = list(input_paths)
    if not paths:
        raise ValueError("At least one source image is required")
    resolved = [Path(path).expanduser().resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Duplicate source paths are not allowed")
    paper = _as_positive_pair(paper_size_mm, "paper_size_mm")
    if len(grid) != 2:
        raise ValueError("grid must contain rows and columns")
    rows, columns = int(grid[0]), int(grid[1])
    if rows <= 0 or columns <= 0:
        raise ValueError("grid rows and columns must be positive")
    if fit_strategy not in SUPPORTED_FIT_STRATEGIES:
        allowed = ", ".join(sorted(SUPPORTED_FIT_STRATEGIES))
        raise ValueError(f"fit_strategy must be explicit and one of: {allowed}")
    margins = _normalize_margins(margins_mm)
    if gap_mm < 0 or bleed_mm < 0 or binding_safe_mm < 0:
        raise ValueError("gap, bleed, and binding safe values cannot be negative")
    if binding_edge not in SUPPORTED_BINDING_EDGES:
        raise ValueError(f"Unsupported binding_edge: {binding_edge}")
    if binding_edge == "none" and binding_safe_mm:
        raise ValueError("binding_safe_mm requires a binding_edge")
    if dpi <= 0 or minimum_ppi <= 0:
        raise ValueError("dpi and minimum_ppi must be positive")
    if crop_mark_length_mm < 0 or crop_mark_gap_mm < 0:
        raise ValueError("Crop mark dimensions cannot be negative")

    top, right, bottom, left = margins
    if binding_edge == "left":
        left += binding_safe_mm
    elif binding_edge == "right":
        right += binding_safe_mm
    elif binding_edge == "top":
        top += binding_safe_mm
    elif binding_edge == "bottom":
        bottom += binding_safe_mm
    usable_width = paper[0] - left - right - gap_mm * (columns - 1)
    usable_height = paper[1] - top - bottom - gap_mm * (rows - 1)
    if usable_width <= 0 or usable_height <= 0:
        raise ValueError("Margins, binding safe area, and gaps leave no printable grid")

    sources = [_load_source_info(path) for path in resolved]
    return sources, paper, (rows, columns), margins


def analyze_print_layout(
    input_paths: Iterable[str | Path],
    *,
    paper_size_mm: Sequence[float],
    grid: Sequence[int],
    fit_strategy: str,
    margins_mm: float | Sequence[float] = 10,
    gap_mm: float = 5,
    bleed_mm: float = 0,
    binding_edge: str = "none",
    binding_safe_mm: float = 0,
    dpi: int = 300,
    minimum_ppi: float = 240,
    crop_marks: bool = True,
    crop_mark_length_mm: float = 4,
    crop_mark_gap_mm: float = 1,
) -> dict[str, Any]:
    """Build a serializable layout plan without writing output files."""

    sources, paper, normalized_grid, base_margins = _validate_inputs(
        input_paths,
        paper_size_mm=paper_size_mm,
        grid=grid,
        fit_strategy=fit_strategy,
        margins_mm=margins_mm,
        gap_mm=gap_mm,
        bleed_mm=bleed_mm,
        binding_edge=binding_edge,
        binding_safe_mm=binding_safe_mm,
        dpi=dpi,
        minimum_ppi=minimum_ppi,
        crop_mark_length_mm=crop_mark_length_mm,
        crop_mark_gap_mm=crop_mark_gap_mm,
    )
    paper_width, paper_height = paper
    rows, columns = normalized_grid
    top, right, bottom, left = base_margins
    effective_margins = [top, right, bottom, left]
    edge_index = {"top": 0, "right": 1, "bottom": 2, "left": 3}
    if binding_edge != "none":
        effective_margins[edge_index[binding_edge]] += binding_safe_mm

    slot_width = (
        paper_width
        - effective_margins[1]
        - effective_margins[3]
        - gap_mm * (columns - 1)
    ) / columns
    slot_height = (
        paper_height
        - effective_margins[0]
        - effective_margins[2]
        - gap_mm * (rows - 1)
    ) / rows
    mark_clearance = crop_mark_length_mm + crop_mark_gap_mm if crop_marks else 0
    trim_origin = bleed_mm + mark_clearance
    media_width = paper_width + 2 * trim_origin
    media_height = paper_height + 2 * trim_origin
    page_capacity = rows * columns
    page_count = math.ceil(len(sources) / page_capacity)
    pages: list[dict[str, Any]] = []
    all_warnings: list[str] = []

    for page_index in range(page_count):
        placements: list[dict[str, Any]] = []
        page_sources = sources[
            page_index * page_capacity : (page_index + 1) * page_capacity
        ]
        for local_index, source in enumerate(page_sources):
            row, column = divmod(local_index, columns)
            slot_trim = (
                effective_margins[3] + column * (slot_width + gap_mm),
                effective_margins[0] + row * (slot_height + gap_mm),
                slot_width,
                slot_height,
            )
            slot_media = (
                slot_trim[0] + trim_origin,
                slot_trim[1] + trim_origin,
                slot_trim[2],
                slot_trim[3],
            )
            if fit_strategy == "contain":
                paint_media = slot_media
            else:
                paint_media = _extend_edge_slot_for_bleed(
                    slot_trim,
                    paper_width_mm=paper_width,
                    paper_height_mm=paper_height,
                    trim_origin_mm=trim_origin,
                    bleed_mm=bleed_mm,
                    margins_mm=tuple(effective_margins),
                    row=row,
                    column=column,
                    rows=rows,
                    columns=columns,
                )
            placement = _placement_for_slot(
                source,
                slot_media,
                paint_media,
                fit_strategy,
            )
            warnings: list[str] = []
            if placement["effective_ppi"] < minimum_ppi:
                warnings.append(
                    f"effective PPI {placement['effective_ppi']:.2f} is below "
                    f"minimum {minimum_ppi:.2f}"
                )
            elif placement["effective_ppi"] < dpi:
                warnings.append(
                    f"output sampling at {dpi} DPI does not add detail beyond "
                    f"effective PPI {placement['effective_ppi']:.2f}"
                )
            if not source.has_icc_profile:
                warnings.append("source has no embedded ICC profile")
            all_warnings.extend(
                f"{source.path.name}: {warning}" for warning in warnings
            )
            placements.append(
                {
                    "source_path": str(source.path),
                    "source_sha256": source.sha256,
                    "source_size_px": [source.width_px, source.height_px],
                    "has_icc_profile": source.has_icc_profile,
                    "page": page_index + 1,
                    "slot": local_index + 1,
                    "row": row + 1,
                    "column": column + 1,
                    "slot_mm": [round(value, 4) for value in slot_media],
                    **placement,
                    "warnings": warnings,
                }
            )
        pages.append({"page": page_index + 1, "placements": placements})

    return {
        "paper_size_mm": [paper_width, paper_height],
        "media_size_mm": [round(media_width, 4), round(media_height, 4)],
        "trim_origin_mm": [round(trim_origin, 4), round(trim_origin, 4)],
        "grid": [rows, columns],
        "fit_strategy": fit_strategy,
        "margins_mm": list(base_margins),
        "effective_margins_mm": [round(value, 4) for value in effective_margins],
        "gap_mm": float(gap_mm),
        "bleed_mm": float(bleed_mm),
        "binding_edge": binding_edge,
        "binding_safe_mm": float(binding_safe_mm),
        "dpi": int(dpi),
        "minimum_ppi": float(minimum_ppi),
        "crop_marks": bool(crop_marks),
        "crop_mark_length_mm": float(crop_mark_length_mm),
        "crop_mark_gap_mm": float(crop_mark_gap_mm),
        "page_count": page_count,
        "pages": pages,
        "warnings": all_warnings,
        "output_icc_profile": None,
        "color_note": (
            "The composite is untagged RGB; no printer ICC or CMYK conversion is "
            "performed."
        ),
    }


def _draw_crop_marks(
    image: Image.Image,
    plan: dict[str, Any],
    dpi: int,
) -> None:
    if not plan["crop_marks"]:
        return
    draw = ImageDraw.Draw(image)
    trim_x = _mm_to_px(plan["trim_origin_mm"][0], dpi)
    trim_y = _mm_to_px(plan["trim_origin_mm"][1], dpi)
    trim_width = max(1, _mm_to_px(plan["paper_size_mm"][0], dpi))
    trim_height = max(1, _mm_to_px(plan["paper_size_mm"][1], dpi))
    bleed = _mm_to_px(plan["bleed_mm"], dpi) if plan["bleed_mm"] else 0
    gap = _mm_to_px(plan["crop_mark_gap_mm"], dpi)
    length = _mm_to_px(plan["crop_mark_length_mm"], dpi)
    line_width = max(1, round(dpi / 300))
    x_left_end = trim_x - bleed - gap
    x_right_start = trim_x + trim_width + bleed + gap
    y_top_end = trim_y - bleed - gap
    y_bottom_start = trim_y + trim_height + bleed + gap

    for y in (trim_y, trim_y + trim_height):
        draw.line(
            (x_left_end - length, y, x_left_end, y),
            fill="black",
            width=line_width,
        )
        draw.line(
            (x_right_start, y, x_right_start + length, y),
            fill="black",
            width=line_width,
        )
    for x in (trim_x, trim_x + trim_width):
        draw.line(
            (x, y_top_end - length, x, y_top_end),
            fill="black",
            width=line_width,
        )
        draw.line(
            (x, y_bottom_start, x, y_bottom_start + length),
            fill="black",
            width=line_width,
        )


def _paste_placement(
    page: Image.Image,
    placement: dict[str, Any],
    dpi: int,
) -> None:
    source_path = Path(placement["source_path"])
    with Image.open(source_path) as opened:
        oriented = ImageOps.exif_transpose(opened)
        if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
            rgba = oriented.convert("RGBA")
            base = Image.new("RGBA", rgba.size, "white")
            base.alpha_composite(rgba)
            image = base.convert("RGB")
        else:
            image = oriented.convert("RGB")
        crop_box = tuple(int(value) for value in placement["source_crop_px"])
        if crop_box != (0, 0, image.width, image.height):
            image = image.crop(crop_box)
        destination = placement["destination_mm"]
        destination_px = (
            _mm_to_px(destination[0], dpi),
            _mm_to_px(destination[1], dpi),
            max(1, _mm_to_px(destination[2], dpi)),
            max(1, _mm_to_px(destination[3], dpi)),
        )
        resized = image.resize(
            (destination_px[2], destination_px[3]),
            Image.Resampling.LANCZOS,
        )
        page.paste(resized, (destination_px[0], destination_px[1]))


def _draw_preview_guides(
    print_page: Image.Image,
    page_plan: dict[str, Any],
    plan: dict[str, Any],
    dpi: int,
) -> Image.Image:
    preview = print_page.copy()
    draw = ImageDraw.Draw(preview, "RGBA")
    trim_x = _mm_to_px(plan["trim_origin_mm"][0], dpi)
    trim_y = _mm_to_px(plan["trim_origin_mm"][1], dpi)
    trim_width = max(1, _mm_to_px(plan["paper_size_mm"][0], dpi))
    trim_height = max(1, _mm_to_px(plan["paper_size_mm"][1], dpi))
    guide_width = max(3, round(dpi / 100))
    draw.rectangle(
        (trim_x, trim_y, trim_x + trim_width, trim_y + trim_height),
        outline=(220, 0, 85, 255),
        width=guide_width,
    )

    for placement in page_plan["placements"]:
        x, y, width, height = (
            _mm_to_px(value, dpi) for value in placement["slot_mm"]
        )
        draw.rectangle(
            (x, y, x + width, y + height),
            outline=(0, 120, 255, 255),
            width=guide_width,
        )
        label = f"{placement['slot']}: {Path(placement['source_path']).name}"
        label_y = max(0, y + 4)
        draw.rectangle(
            (x + 4, label_y, x + min(width - 4, 520), label_y + 28),
            fill=(255, 255, 255, 210),
        )
        draw.text((x + 8, label_y + 5), label, fill=(0, 70, 150, 255))

    edge = plan["binding_edge"]
    safe_mm = plan["binding_safe_mm"]
    if edge != "none" and safe_mm:
        safe_px = _mm_to_px(safe_mm, dpi)
        paper_box = (trim_x, trim_y, trim_x + trim_width, trim_y + trim_height)
        if edge == "left":
            safe_box = (paper_box[0], paper_box[1], paper_box[0] + safe_px, paper_box[3])
        elif edge == "right":
            safe_box = (paper_box[2] - safe_px, paper_box[1], paper_box[2], paper_box[3])
        elif edge == "top":
            safe_box = (paper_box[0], paper_box[1], paper_box[2], paper_box[1] + safe_px)
        else:
            safe_box = (paper_box[0], paper_box[3] - safe_px, paper_box[2], paper_box[3])
        draw.rectangle(safe_box, fill=(255, 145, 0, 60), outline=(255, 110, 0, 255))

    if max(preview.size) > 1600:
        scale = 1600 / max(preview.size)
        preview = preview.resize(
            (round(preview.width * scale), round(preview.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return preview


def _write_manifest_csv(path: Path, plan: dict[str, Any]) -> None:
    fields = [
        "page",
        "slot",
        "row",
        "column",
        "source_path",
        "source_sha256",
        "source_width_px",
        "source_height_px",
        "slot_mm",
        "destination_mm",
        "source_crop_px",
        "effective_ppi",
        "has_icc_profile",
        "warnings",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for page in plan["pages"]:
            for placement in page["placements"]:
                writer.writerow(
                    {
                        "page": placement["page"],
                        "slot": placement["slot"],
                        "row": placement["row"],
                        "column": placement["column"],
                        "source_path": placement["source_path"],
                        "source_sha256": placement["source_sha256"],
                        "source_width_px": placement["source_size_px"][0],
                        "source_height_px": placement["source_size_px"][1],
                        "slot_mm": json.dumps(placement["slot_mm"]),
                        "destination_mm": json.dumps(placement["destination_mm"]),
                        "source_crop_px": json.dumps(placement["source_crop_px"]),
                        "effective_ppi": placement["effective_ppi"],
                        "has_icc_profile": placement["has_icc_profile"],
                        "warnings": " | ".join(placement["warnings"]),
                    }
                )


def _write_pdf(pdf_path: Path, page_paths: list[Path], media_size_mm: Sequence[float]) -> None:
    width_points = media_size_mm[0] * POINTS_PER_MM
    height_points = media_size_mm[1] * POINTS_PER_MM
    pdf = canvas.Canvas(
        str(pdf_path),
        pagesize=(width_points, height_points),
        pageCompression=1,
    )
    for page_path in page_paths:
        pdf.drawImage(
            ImageReader(str(page_path)),
            0,
            0,
            width=width_points,
            height=height_points,
            preserveAspectRatio=False,
            mask="auto",
        )
        pdf.showPage()
    pdf.save()


def create_print_layout(
    input_paths: Iterable[str | Path],
    output_dir: str | Path,
    *,
    paper_size_mm: Sequence[float],
    grid: Sequence[int],
    fit_strategy: str,
    margins_mm: float | Sequence[float] = 10,
    gap_mm: float = 5,
    bleed_mm: float = 0,
    binding_edge: str = "none",
    binding_safe_mm: float = 0,
    dpi: int = 300,
    minimum_ppi: float = 240,
    allow_low_ppi: bool = False,
    crop_marks: bool = True,
    crop_mark_length_mm: float = 4,
    crop_mark_gap_mm: float = 1,
    background: str = "white",
    output_basename: str = "photo_print_layout",
) -> dict[str, Any]:
    """Render print pages, a PDF, previews, and machine-readable manifests."""

    paths = list(input_paths)
    output_basename = _validate_output_basename(output_basename)
    plan = analyze_print_layout(
        paths,
        paper_size_mm=paper_size_mm,
        grid=grid,
        fit_strategy=fit_strategy,
        margins_mm=margins_mm,
        gap_mm=gap_mm,
        bleed_mm=bleed_mm,
        binding_edge=binding_edge,
        binding_safe_mm=binding_safe_mm,
        dpi=dpi,
        minimum_ppi=minimum_ppi,
        crop_marks=crop_marks,
        crop_mark_length_mm=crop_mark_length_mm,
        crop_mark_gap_mm=crop_mark_gap_mm,
    )
    low_ppi = [
        placement
        for page in plan["pages"]
        for placement in page["placements"]
        if placement["effective_ppi"] < minimum_ppi
    ]
    if low_ppi and not allow_low_ppi:
        details = "; ".join(
            f"{Path(item['source_path']).name}={item['effective_ppi']:.2f} PPI"
            for item in low_ppi
        )
        raise ValueError(
            f"Low-resolution placement blocked: {details}. "
            "Set allow_low_ppi=True only after explicit acceptance."
        )

    output = Path(output_dir).expanduser().resolve()
    if output.exists() and not output.is_dir():
        raise NotADirectoryError(f"Output path is not a directory: {output}")
    background_rgb = ImageColor.getrgb(background)
    page_paths = [
        output / f"{output_basename}_page_{page['page']:03d}.png"
        for page in plan["pages"]
    ]
    preview_paths = [
        output / f"{output_basename}_preview_{page['page']:03d}.png"
        for page in plan["pages"]
    ]
    pdf_path = output / f"{output_basename}.pdf"
    json_path = output / f"{output_basename}_manifest.json"
    csv_path = output / f"{output_basename}_manifest.csv"
    expected_outputs = [*page_paths, *preview_paths, pdf_path, json_path, csv_path]
    collisions = [path for path in expected_outputs if path.exists()]
    if collisions:
        names = ", ".join(path.name for path in collisions)
        raise FileExistsError(f"Refusing to overwrite existing outputs: {names}")

    media_pixels = (
        max(1, _mm_to_px(plan["media_size_mm"][0], dpi)),
        max(1, _mm_to_px(plan["media_size_mm"][1], dpi)),
    )
    if media_pixels[0] * media_pixels[1] > 150_000_000:
        raise ValueError(
            "Rendered page exceeds 150 million pixels; reduce page size or DPI"
        )
    output.mkdir(parents=True, exist_ok=True)
    for page_plan, page_path, preview_path in zip(
        plan["pages"], page_paths, preview_paths, strict=True
    ):
        print_page = Image.new("RGB", media_pixels, background_rgb)
        for placement in page_plan["placements"]:
            _paste_placement(print_page, placement, dpi)
        _draw_crop_marks(print_page, plan, dpi)
        print_page.save(page_path, format="PNG", dpi=(dpi, dpi), optimize=True)
        preview = _draw_preview_guides(print_page, page_plan, plan, dpi)
        preview.save(preview_path, format="PNG", optimize=True)

    _write_pdf(pdf_path, page_paths, plan["media_size_mm"])
    plan["allow_low_ppi"] = bool(allow_low_ppi)
    plan["outputs"] = {
        "print_pages": [str(path) for path in page_paths],
        "previews": [str(path) for path in preview_paths],
        "pdf": str(pdf_path),
        "manifest_json": str(json_path),
        "manifest_csv": str(csv_path),
    }
    json_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_manifest_csv(csv_path, plan)

    changed_sources = []
    for path in paths:
        source = Path(path).expanduser().resolve()
        original_hash = next(
            item["source_sha256"]
            for page in plan["pages"]
            for item in page["placements"]
            if item["source_path"] == str(source)
        )
        if _sha256(source) != original_hash:
            changed_sources.append(str(source))
    if changed_sources:
        raise RuntimeError(f"Source files changed during rendering: {changed_sources}")
    return plan
