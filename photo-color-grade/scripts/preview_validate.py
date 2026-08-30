"""Preview composition and measurable output validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from .color_engine import analyze_rgb
except ImportError:
    from color_engine import analyze_rgb


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _thumbnail(rgb: np.ndarray, cell_width: int, image_height: int) -> Image.Image:
    array = np.round(np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)
    image = Image.fromarray(array, mode="RGB")
    image.thumbnail((cell_width, image_height), Image.Resampling.LANCZOS)
    return image


def make_contact_sheet(
    variants: Mapping[str, np.ndarray],
    output_path: str | Path,
    columns: int = 3,
    cell_width: int = 460,
    image_height: int = 430,
) -> Path:
    destination = Path(output_path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"预览已存在，默认不覆盖: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    labels = list(variants.keys())
    rows = (len(labels) + columns - 1) // columns
    label_height = 52
    margin = 18
    cell_height = image_height + label_height
    canvas = Image.new(
        "RGB",
        (
            columns * cell_width + (columns + 1) * margin,
            rows * cell_height + (rows + 1) * margin,
        ),
        (238, 237, 233),
    )
    draw = ImageDraw.Draw(canvas)
    font = _font(22)

    for index, label in enumerate(labels):
        row, column = divmod(index, columns)
        x = margin + column * (cell_width + margin)
        y = margin + row * (cell_height + margin)
        thumb = _thumbnail(variants[label], cell_width, image_height)
        image_x = x + (cell_width - thumb.width) // 2
        image_y = y + (image_height - thumb.height) // 2
        canvas.paste(thumb, (image_x, image_y))
        text_box = draw.textbbox((0, 0), label, font=font)
        text_width = text_box[2] - text_box[0]
        draw.text(
            (x + (cell_width - text_width) // 2, y + image_height + 14),
            label,
            fill=(30, 30, 30),
            font=font,
        )

    canvas.save(destination, quality=94, subsampling=0)
    return destination


def _mean_skin_delta(source: np.ndarray, result: np.ndarray) -> float | None:
    source_u8 = np.round(np.clip(source, 0.0, 1.0) * 255.0).astype(np.uint8)
    ycrcb = cv2.cvtColor(source_u8, cv2.COLOR_RGB2YCrCb)
    y, cr, cb = cv2.split(ycrcb)
    mask = (y > 38) & (cr >= 130) & (cr <= 180) & (cb >= 75) & (cb <= 138)
    if np.count_nonzero(mask) < 64:
        return None
    source_lab = cv2.cvtColor(source.astype(np.float32), cv2.COLOR_RGB2LAB)
    result_lab = cv2.cvtColor(result.astype(np.float32), cv2.COLOR_RGB2LAB)
    delta = np.linalg.norm(result_lab[mask] - source_lab[mask], axis=1)
    return float(np.mean(delta))


def validate_arrays(source: np.ndarray, result: np.ndarray) -> dict[str, Any]:
    source_analysis = analyze_rgb(source)
    result_analysis = analyze_rgb(result)
    blocking: list[str] = []
    warnings: list[str] = []

    if source.shape != result.shape:
        blocking.append(f"尺寸发生变化: {source.shape} -> {result.shape}")
    if not np.all(np.isfinite(result)):
        blocking.append("输出包含NaN或无穷值")
    if float(np.min(result)) < 0.0 or float(np.max(result)) > 1.0:
        blocking.append("输出存在色域范围外数值")

    source_clip = source_analysis["clipping"]
    result_clip = result_analysis["clipping"]
    highlight_increase = result_clip["highlight_pct"] - source_clip["highlight_pct"]
    shadow_increase = result_clip["shadow_pct"] - source_clip["shadow_pct"]
    if highlight_increase > 0.05:
        blocking.append(f"新增高光溢出{highlight_increase:.4f}个百分点")
    if shadow_increase > 0.10:
        blocking.append(f"新增暗部死黑{shadow_increase:.4f}个百分点")

    saturation_change = (
        result_analysis["saturation"]["median"]
        - source_analysis["saturation"]["median"]
    )
    luma_change = (
        result_analysis["luminance"]["p50"] - source_analysis["luminance"]["p50"]
    )
    if abs(saturation_change) > 0.22:
        warnings.append(f"中位饱和度变化较大: {saturation_change:+.4f}")
    if abs(luma_change) > 0.28:
        warnings.append(f"中位亮度变化较大: {luma_change:+.4f}")

    skin_delta = _mean_skin_delta(source, result)
    if skin_delta is not None and skin_delta > 18.0:
        warnings.append(f"潜在肤色区域平均Lab变化较大: {skin_delta:.2f}")

    return {
        "status": "pass" if not blocking else "blocked",
        "blocking": blocking,
        "warnings": warnings,
        "metrics": {
            "highlight_clip_increase_pct_points": round(highlight_increase, 6),
            "shadow_clip_increase_pct_points": round(shadow_increase, 6),
            "median_saturation_change": round(saturation_change, 6),
            "median_luminance_change": round(luma_change, 6),
            "skin_candidate_mean_lab_delta": None
            if skin_delta is None
            else round(skin_delta, 4),
        },
        "source": source_analysis,
        "result": result_analysis,
    }
