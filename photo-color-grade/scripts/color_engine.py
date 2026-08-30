"""Deterministic image analysis and color operations.

The module deliberately exposes no command-line entrypoint. It operates on copies
of image data and never overwrites a source file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import tifffile
from PIL import Image, ImageOps

LDR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".erf",
    ".kdc",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".srw",
}


@dataclass(frozen=True)
class ImageData:
    path: Path
    rgb: np.ndarray
    source_dtype: str
    bit_depth: int
    source_format: str
    exif: bytes | None
    icc_profile: bytes | None
    orientation_normalized: bool


def _metadata_from_pillow(path: Path) -> tuple[bytes | None, bytes | None, bool]:
    try:
        with Image.open(path) as source:
            original_orientation = source.getexif().get(274, 1)
            normalized = ImageOps.exif_transpose(source)
            exif = normalized.getexif().tobytes() if normalized.getexif() else None
            icc = source.info.get("icc_profile")
            return exif, icc, original_orientation not in (None, 1)
    except (OSError, SyntaxError, ValueError):
        return None, None, False


def _normalize_numeric_image(array: np.ndarray) -> tuple[np.ndarray, int]:
    if array.ndim == 2:
        array = np.repeat(array[..., None], 3, axis=2)
    if array.ndim != 3:
        raise ValueError(f"不支持的图像维度: {array.shape}")
    if array.shape[2] > 3:
        array = array[..., :3]

    if np.issubdtype(array.dtype, np.integer):
        max_value = float(np.iinfo(array.dtype).max)
        bit_depth = int(np.iinfo(array.dtype).bits)
        rgb = array.astype(np.float32) / max_value
    else:
        rgb = array.astype(np.float32)
        bit_depth = 32
        finite = rgb[np.isfinite(rgb)]
        if finite.size and float(np.nanmax(finite)) > 1.5:
            rgb /= float(np.nanmax(finite))
    return np.clip(rgb, 0.0, 1.0), bit_depth


def load_image(path: str | Path) -> ImageData:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"找不到图像: {source_path}")

    suffix = source_path.suffix.lower()
    exif, icc, orientation_normalized = _metadata_from_pillow(source_path)

    if suffix in RAW_EXTENSIONS:
        try:
            import rawpy  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "RAW处理需要rawpy。当前环境未安装，不能使用内嵌JPEG代替RAW调色。"
            ) from exc
        with rawpy.imread(str(source_path)) as raw:
            array = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=True,
                output_bps=16,
                gamma=(2.222, 4.5),
            )
        rgb, bit_depth = _normalize_numeric_image(array)
        return ImageData(
            path=source_path,
            rgb=rgb,
            source_dtype=str(array.dtype),
            bit_depth=bit_depth,
            source_format="RAW",
            exif=None,
            icc_profile=None,
            orientation_normalized=False,
        )

    if suffix not in LDR_EXTENSIONS:
        raise ValueError(f"不支持的图像格式: {suffix or '无扩展名'}")

    if suffix in {".tif", ".tiff"}:
        array = tifffile.imread(source_path)
        if array.ndim == 4:
            array = array[0]
        rgb, bit_depth = _normalize_numeric_image(array)
    else:
        unchanged = cv2.imread(str(source_path), cv2.IMREAD_UNCHANGED)
        if unchanged is not None and unchanged.dtype == np.uint16:
            if unchanged.ndim == 2:
                array = np.repeat(unchanged[..., None], 3, axis=2)
            else:
                array = cv2.cvtColor(unchanged[..., :3], cv2.COLOR_BGR2RGB)
            rgb, bit_depth = _normalize_numeric_image(array)
        else:
            with Image.open(source_path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                array = np.asarray(oriented)
            rgb, bit_depth = _normalize_numeric_image(array)

    return ImageData(
        path=source_path,
        rgb=rgb,
        source_dtype=str(array.dtype),
        bit_depth=bit_depth,
        source_format=suffix.lstrip(".").upper(),
        exif=exif,
        icc_profile=icc,
        orientation_normalized=orientation_normalized,
    )


def _quantize(rgb: np.ndarray, bit_depth: int) -> np.ndarray:
    clipped = np.clip(rgb, 0.0, 1.0)
    if bit_depth > 8:
        return np.round(clipped * 65535.0).astype(np.uint16)
    return np.round(clipped * 255.0).astype(np.uint8)


def save_image(image: ImageData, rgb: np.ndarray, output_path: str | Path) -> Path:
    destination = Path(output_path).expanduser().resolve()
    if destination == image.path:
        raise ValueError("输出路径不能与原图相同")
    if destination.exists():
        raise FileExistsError(f"输出已存在，默认不覆盖: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    suffix = destination.suffix.lower()
    output_depth = 16 if image.bit_depth > 8 or image.source_format == "RAW" else 8
    array = _quantize(rgb, output_depth)

    if suffix in {".jpg", ".jpeg"}:
        pil_image = Image.fromarray(_quantize(rgb, 8), mode="RGB")
        options: dict[str, Any] = {"quality": 96, "subsampling": 0, "optimize": True}
        if image.exif:
            options["exif"] = image.exif
        if image.icc_profile:
            options["icc_profile"] = image.icc_profile
        pil_image.save(destination, **options)
    elif suffix == ".png":
        if output_depth == 16:
            bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            if not cv2.imwrite(str(destination), bgr):
                raise OSError(f"无法写入图像: {destination}")
        else:
            options = {}
            if image.icc_profile:
                options["icc_profile"] = image.icc_profile
            Image.fromarray(array, mode="RGB").save(destination, **options)
    elif suffix in {".tif", ".tiff"}:
        extra_tags = None
        if image.icc_profile:
            extra_tags = [
                (34675, "B", len(image.icc_profile), image.icc_profile, False)
            ]
        tifffile.imwrite(
            destination,
            array,
            photometric="rgb",
            metadata=None,
            extratags=extra_tags,
        )
    else:
        raise ValueError(f"不支持的输出格式: {suffix}")
    return destination


def _sample(rgb: np.ndarray, longest_side: int = 1200) -> np.ndarray:
    height, width = rgb.shape[:2]
    scale = min(1.0, longest_side / max(height, width))
    if scale == 1.0:
        return rgb
    return cv2.resize(
        rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA
    )


def perceptual_luminance(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2LAB)
    return np.clip(lab[..., 0] / 100.0, 0.0, 1.0)


def _skin_candidate_mask(rgb: np.ndarray) -> np.ndarray:
    u8 = _quantize(rgb, 8)
    ycrcb = cv2.cvtColor(u8, cv2.COLOR_RGB2YCrCb)
    hsv = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2HSV)
    y, cr, cb = cv2.split(ycrcb)
    saturation = hsv[..., 1]
    return (
        (y > 38)
        & (cr >= 130)
        & (cr <= 180)
        & (cb >= 75)
        & (cb <= 138)
        & (saturation >= 0.08)
        & (saturation <= 0.78)
    )


def analyze_rgb(rgb: np.ndarray) -> dict[str, Any]:
    sampled = _sample(rgb)
    luminance = perceptual_luminance(sampled)
    hsv = cv2.cvtColor(sampled.astype(np.float32), cv2.COLOR_RGB2HSV)
    saturation = np.clip(hsv[..., 1], 0.0, 1.0)

    percentiles = np.percentile(luminance, [1, 5, 50, 95, 99])
    p01, p05, p50, p95, p99 = [float(value) for value in percentiles]
    highlight_clip = float(np.mean(np.max(sampled, axis=2) >= 0.998) * 100.0)
    shadow_clip = float(np.mean(np.max(sampled, axis=2) <= 0.002) * 100.0)

    mid = (luminance >= 0.16) & (luminance <= 0.84)
    if np.any(mid):
        threshold = min(0.18, float(np.percentile(saturation[mid], 18)) + 0.015)
        neutral_mask = mid & (saturation <= threshold)
    else:
        neutral_mask = np.zeros_like(luminance, dtype=bool)

    neutral_coverage = float(np.mean(neutral_mask))
    if np.count_nonzero(neutral_mask) >= 64:
        neutral_rgb = np.median(sampled[neutral_mask], axis=0)
        red, green, blue = [max(float(value), 1e-5) for value in neutral_rgb]
        raw_gains = np.array([green / red, 1.0, green / blue], dtype=np.float32)
        gains = np.clip(raw_gains, 0.92, 1.08)
        neutral_sat = float(np.median(saturation[neutral_mask]))
        coverage_score = min(1.0, neutral_coverage / 0.08)
        purity_score = np.clip((0.18 - neutral_sat) / 0.15, 0.0, 1.0)
        wb_confidence = float(coverage_score * purity_score)
    else:
        neutral_rgb = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        raw_gains = np.ones(3, dtype=np.float32)
        gains = raw_gains.copy()
        neutral_sat = 1.0
        wb_confidence = 0.0

    skin_mask = _skin_candidate_mask(sampled)
    skin_coverage = float(np.mean(skin_mask) * 100.0)
    dynamic_range = float(np.log2(max(p99, 1e-4) / max(p01, 1e-4)))
    scene_key = "low" if p50 < 0.28 else "high" if p50 > 0.62 else "normal"

    return {
        "luminance": {
            "p01": round(p01, 6),
            "p05": round(p05, 6),
            "p50": round(p50, 6),
            "p95": round(p95, 6),
            "p99": round(p99, 6),
            "dynamic_range_stops": round(dynamic_range, 3),
            "scene_key": scene_key,
        },
        "clipping": {
            "highlight_pct": round(highlight_clip, 6),
            "shadow_pct": round(shadow_clip, 6),
        },
        "saturation": {
            "median": round(float(np.median(saturation)), 6),
            "p90": round(float(np.percentile(saturation, 90)), 6),
        },
        "white_balance": {
            "candidate_coverage_pct": round(neutral_coverage * 100.0, 4),
            "candidate_median_saturation": round(neutral_sat, 6),
            "candidate_rgb": [round(float(value), 6) for value in neutral_rgb],
            "raw_gains": [round(float(value), 6) for value in raw_gains],
            "bounded_gains": [round(float(value), 6) for value in gains],
            "confidence": round(wb_confidence, 6),
            "recommended": wb_confidence >= 0.45
            and float(np.max(np.abs(gains - 1.0))) >= 0.008,
        },
        "skin_candidate_pct": round(skin_coverage, 4),
    }


def build_technical_plan(
    analysis: dict[str, Any], strength: float = 1.0
) -> dict[str, Any]:
    strength = float(np.clip(strength, 0.0, 1.5))
    luma = analysis["luminance"]
    clipping = analysis["clipping"]
    p50, p95, p99 = luma["p50"], luma["p95"], luma["p99"]

    exposure_stops = 0.0
    if p99 < 0.72 and p50 < 0.42:
        exposure_stops = min(0.55, np.log2(0.78 / max(p99, 0.08)) * 0.55)
    elif p50 < 0.16 and p95 < 0.58:
        exposure_stops = min(0.45, np.log2(0.34 / max(p50, 0.04)) * 0.35)
    elif clipping["highlight_pct"] > 0.5 or p50 > 0.72:
        exposure_stops = -0.18

    wb = analysis["white_balance"]
    apply_wb = bool(wb["recommended"])
    wb_gains = np.array(wb["bounded_gains"] if apply_wb else [1.0, 1.0, 1.0])
    wb_gains = 1.0 + (wb_gains - 1.0) * strength

    shadow_lift = 0.0
    if luma["p05"] < 0.025 and clipping["shadow_pct"] < 8.0:
        shadow_lift = 0.012
    highlight_rolloff = 0.0
    if p95 > 0.88 or clipping["highlight_pct"] > 0.05:
        highlight_rolloff = min(0.035, 0.012 + clipping["highlight_pct"] / 200.0)

    return {
        "exposure_stops": round(
            float(np.clip(exposure_stops * strength, -0.75, 0.75)), 6
        ),
        "white_balance_applied": apply_wb,
        "white_balance_confidence": wb["confidence"],
        "white_balance_gains": [round(float(value), 6) for value in wb_gains],
        "shadow_lift": round(float(shadow_lift * strength), 6),
        "highlight_rolloff": round(float(highlight_rolloff * strength), 6),
        "contrast": 0.0,
        "strength": strength,
    }


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    return np.where(
        rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(rgb, 1 / 2.4) - 0.055
    )


def _adjust_luminance(
    rgb: np.ndarray,
    contrast: float = 0.0,
    shadow_lift: float = 0.0,
    highlight_rolloff: float = 0.0,
    black_lift: float = 0.0,
) -> np.ndarray:
    lab = cv2.cvtColor(np.clip(rgb, 0.0, 1.0).astype(np.float32), cv2.COLOR_RGB2LAB)
    luminance = np.clip(lab[..., 0] / 100.0, 0.0, 1.0)
    shaped = luminance + contrast * (luminance - 0.5) * 4.0 * luminance * (
        1.0 - luminance
    )
    shaped += shadow_lift * (1.0 - luminance) ** 2
    shaped -= highlight_rolloff * luminance**4
    shaped = black_lift + (1.0 - black_lift) * shaped
    lab[..., 0] = np.clip(shaped, 0.0, 1.0) * 100.0
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)


def apply_technical(rgb: np.ndarray, plan: dict[str, Any]) -> np.ndarray:
    linear = _srgb_to_linear(np.clip(rgb, 0.0, 1.0))
    gains = np.asarray(plan["white_balance_gains"], dtype=np.float32)
    linear = linear * gains.reshape(1, 1, 3)
    linear *= 2.0 ** float(plan["exposure_stops"])
    corrected = _linear_to_srgb(np.clip(linear, 0.0, 1.0))
    return _adjust_luminance(
        corrected,
        contrast=float(plan.get("contrast", 0.0)),
        shadow_lift=float(plan.get("shadow_lift", 0.0)),
        highlight_rolloff=float(plan.get("highlight_rolloff", 0.0)),
    )


def _targeted_saturation(
    rgb: np.ndarray, green_scale: float, blue_scale: float
) -> np.ndarray:
    hsv = cv2.cvtColor(np.clip(rgb, 0.0, 1.0).astype(np.float32), cv2.COLOR_RGB2HSV)
    hue = hsv[..., 0]
    green_mask = np.clip(1.0 - np.abs(hue - 120.0) / 55.0, 0.0, 1.0)
    blue_mask = np.clip(1.0 - np.abs(hue - 220.0) / 70.0, 0.0, 1.0)
    scale = 1.0 + green_mask * (green_scale - 1.0) + blue_mask * (blue_scale - 1.0)
    hsv[..., 1] = np.clip(hsv[..., 1] * scale, 0.0, 1.0)
    return np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0.0, 1.0)


def apply_creative_look(
    rgb: np.ndarray,
    look: dict[str, Any],
    strength: float = 1.0,
    protect_skin: bool = True,
) -> np.ndarray:
    strength = float(np.clip(strength, 0.0, 1.5))
    base = np.clip(rgb, 0.0, 1.0).astype(np.float32)

    temperature = float(look.get("temperature", 0.0)) * strength
    tint = float(look.get("tint", 0.0)) * strength
    linear = _srgb_to_linear(base)
    color_gains = np.array(
        [
            1.0 + 0.06 * temperature + 0.025 * tint,
            1.0 - 0.035 * tint,
            1.0 - 0.06 * temperature + 0.025 * tint,
        ],
        dtype=np.float32,
    )
    linear *= color_gains.reshape(1, 1, 3)
    graded = _linear_to_srgb(np.clip(linear, 0.0, 1.0))

    graded = _adjust_luminance(
        graded,
        contrast=float(look.get("contrast", 0.0)) * strength,
        black_lift=float(look.get("black_lift", 0.0)) * strength,
        highlight_rolloff=max(0.0, -float(look.get("contrast", 0.0))) * 0.08 * strength,
    )

    lab = cv2.cvtColor(graded.astype(np.float32), cv2.COLOR_RGB2LAB)
    saturation = 1.0 + (float(look.get("saturation", 1.0)) - 1.0) * strength
    lab[..., 1:] *= saturation
    graded = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)

    graded = _targeted_saturation(
        graded,
        1.0 + (float(look.get("green_saturation", 1.0)) - 1.0) * strength,
        1.0 + (float(look.get("blue_saturation", 1.0)) - 1.0) * strength,
    )

    luminance = perceptual_luminance(graded)
    shadow_weight = np.clip((0.48 - luminance) / 0.48, 0.0, 1.0) ** 1.5
    highlight_weight = np.clip((luminance - 0.52) / 0.48, 0.0, 1.0) ** 1.5
    shadow_color = np.asarray(
        look.get("shadow_color", [0.0, 0.0, 0.0]), dtype=np.float32
    )
    highlight_color = np.asarray(
        look.get("highlight_color", [0.0, 0.0, 0.0]), dtype=np.float32
    )
    graded += strength * (
        shadow_weight[..., None] * shadow_color.reshape(1, 1, 3)
        + highlight_weight[..., None] * highlight_color.reshape(1, 1, 3)
    )
    graded = np.clip(graded, 0.0, 1.0)

    if protect_skin:
        skin = _skin_candidate_mask(base)
        if np.any(skin):
            base_lab = cv2.cvtColor(base, cv2.COLOR_RGB2LAB)
            graded_lab = cv2.cvtColor(graded.astype(np.float32), cv2.COLOR_RGB2LAB)
            graded_lab[skin, 1:] = (
                0.65 * graded_lab[skin, 1:] + 0.35 * base_lab[skin, 1:]
            )
            graded = np.clip(cv2.cvtColor(graded_lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)
    return graded


def reference_statistics(rgb: np.ndarray) -> dict[str, Any]:
    sampled = _sample(rgb)
    luminance = perceptual_luminance(sampled)
    lab = cv2.cvtColor(sampled.astype(np.float32), cv2.COLOR_RGB2LAB)
    valid = (luminance > 0.03) & (luminance < 0.97)
    if np.count_nonzero(valid) < 64:
        valid = np.ones_like(luminance, dtype=bool)
    ab = lab[valid, 1:]
    return {
        "luminance_percentiles": [
            float(value) for value in np.percentile(luminance, [5, 50, 95])
        ],
        "ab_mean": [float(value) for value in np.mean(ab, axis=0)],
        "ab_std": [float(value) for value in np.std(ab, axis=0)],
    }


def apply_reference_match(
    rgb: np.ndarray,
    reference_rgb: np.ndarray,
    strength: float = 1.0,
    protect_skin: bool = True,
) -> np.ndarray:
    strength = float(np.clip(strength, 0.0, 1.0))
    source_stats = reference_statistics(rgb)
    target_stats = reference_statistics(reference_rgb)

    lab = cv2.cvtColor(np.clip(rgb, 0.0, 1.0).astype(np.float32), cv2.COLOR_RGB2LAB)
    luminance = np.clip(lab[..., 0] / 100.0, 0.0, 1.0)
    source_points = np.array(
        [0.0, *source_stats["luminance_percentiles"], 1.0], dtype=np.float32
    )
    target_middle = np.array(
        source_stats["luminance_percentiles"], dtype=np.float32
    ) * (1.0 - 0.65 * strength) + np.array(
        target_stats["luminance_percentiles"], dtype=np.float32
    ) * (0.65 * strength)
    target_points = np.array([0.0, *target_middle, 1.0], dtype=np.float32)
    target_points = np.maximum.accumulate(target_points)
    target_points[1:-1] = np.clip(target_points[1:-1], 0.01, 0.99)
    mapped_luminance = np.interp(luminance, source_points, target_points)
    lab[..., 0] = np.clip(mapped_luminance, 0.0, 1.0) * 100.0

    source_mean = np.asarray(source_stats["ab_mean"], dtype=np.float32)
    source_std = np.maximum(np.asarray(source_stats["ab_std"], dtype=np.float32), 2.0)
    target_mean = np.asarray(target_stats["ab_mean"], dtype=np.float32)
    target_std = np.maximum(np.asarray(target_stats["ab_std"], dtype=np.float32), 2.0)
    scale = np.clip(target_std / source_std, 0.72, 1.35)
    transferred = (lab[..., 1:] - source_mean) * scale + target_mean
    delta = np.clip(transferred - lab[..., 1:], -18.0, 18.0)
    lab[..., 1:] += delta * (0.45 * strength)

    if protect_skin:
        skin = _skin_candidate_mask(rgb)
        if np.any(skin):
            original_lab = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2LAB)
            lab[skin, 1:] = 0.70 * lab[skin, 1:] + 0.30 * original_lab[skin, 1:]
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)
