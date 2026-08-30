"""Deterministic spatial luminance shaping without generative relighting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

VALID_MODES = {"focus", "depth", "balance"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: str | Path) -> tuple[Path, np.ndarray, bytes | None, bytes | None]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到照片: {source}")
    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image)
        rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
        exif = oriented.getexif().tobytes() if oriented.getexif() else None
        icc = image.info.get("icc_profile")
    return source, rgb, exif, icc


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = [float(value) for value in np.percentile(values, [2, 98])]
    if high - low < 1e-7:
        return np.zeros_like(values, dtype=np.float32)
    return np.clip((values - low) / (high - low), 0.0, 1.0).astype(np.float32)


def _automatic_mask(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    height, width = rgb.shape[:2]
    scale = min(1.0, 900 / max(height, width))
    work = cv2.resize(
        rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA
    )
    gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(work.astype(np.float32) / 255.0, cv2.COLOR_RGB2HSV)
    sigma = max(2.0, max(work.shape[:2]) * 0.035)
    local = _normalize(np.abs(gray - cv2.GaussianBlur(gray, (0, 0), sigma)))
    edge = _normalize(
        cv2.magnitude(
            cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
        )
    )
    yy, xx = np.mgrid[0 : work.shape[0], 0 : work.shape[1]].astype(np.float32)
    center = np.exp(
        -(
            ((xx / work.shape[1] - 0.5) / 0.42) ** 2
            + ((yy / work.shape[0] - 0.5) / 0.42) ** 2
        )
    )
    saliency = _normalize(
        0.36 * local + 0.28 * edge + 0.14 * hsv[..., 1] + 0.22 * center
    )
    binary = (saliency >= np.percentile(saliency, 67)).astype(np.uint8)
    kernel = np.ones((7, 7), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, 8)
    if count <= 1:
        return cv2.resize(saliency, (width, height), interpolation=cv2.INTER_CUBIC), 0.0

    best_label, best_score = 1, -1.0
    for label in range(1, count):
        area = stats[label, cv2.CC_STAT_AREA]
        if area < binary.size * 0.01:
            continue
        cx, cy = centroids[label]
        center_score = 1.0 - min(
            1.0, np.hypot(cx / work.shape[1] - 0.5, cy / work.shape[0] - 0.5)
        )
        score = (
            float(np.mean(saliency[labels == label]))
            * np.sqrt(area / binary.size)
            * (0.7 + 0.3 * center_score)
        )
        if score > best_score:
            best_label, best_score = label, score
    mask = (labels == best_label).astype(np.float32)
    feather = max(2.0, max(work.shape[:2]) * 0.012)
    mask = cv2.GaussianBlur(mask, (0, 0), feather)
    if float(mask.max()) > 0:
        mask /= float(mask.max())
    mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_CUBIC)
    area = float(np.mean(mask > 0.5))
    separation = float(
        np.mean(saliency[labels == best_label])
        - np.mean(saliency[labels != best_label])
    )
    area_score = np.clip(1.0 - abs(area - 0.28) / 0.52, 0.0, 1.0)
    confidence = float(np.clip(0.25 + 1.8 * separation + 0.35 * area_score, 0.0, 1.0))
    if area < 0.02 or area > 0.80:
        confidence *= 0.25
    return np.clip(mask, 0.0, 1.0), confidence


def _load_mask(path: str | Path, shape: tuple[int, int]) -> np.ndarray:
    mask_path = Path(path).expanduser().resolve()
    unchanged = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
    if unchanged is None:
        raise ValueError(f"无法读取蒙版: {mask_path}")
    if unchanged.ndim == 3:
        unchanged = cv2.cvtColor(unchanged[..., :3], cv2.COLOR_BGR2GRAY)
    maximum = (
        float(np.iinfo(unchanged.dtype).max)
        if np.issubdtype(unchanged.dtype, np.integer)
        else 1.0
    )
    mask = unchanged.astype(np.float32) / maximum
    if mask.shape != shape:
        mask = cv2.resize(mask, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    return np.clip(mask, 0.0, 1.0)


def _analysis(rgb: np.ndarray, mask: np.ndarray, confidence: float) -> dict[str, Any]:
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    luma = lab[..., 0] / 100.0
    foreground = mask >= 0.5
    background = mask < 0.2
    return {
        "mask_confidence": round(confidence, 6),
        "subject_area_pct": round(float(np.mean(foreground) * 100), 4),
        "subject_luminance": round(
            float(np.median(luma[foreground])) if np.any(foreground) else 0.0, 6
        ),
        "background_luminance": round(
            float(np.median(luma[background])) if np.any(background) else 0.0, 6
        ),
        "highlight_clip_pct": round(
            float(np.mean(np.max(rgb, axis=2) >= 254) * 100), 6
        ),
        "shadow_clip_pct": round(float(np.mean(np.max(rgb, axis=2) <= 1) * 100), 6),
    }


def analyze_light(
    input_path: str | Path, subject_mask_path: str | Path | None = None
) -> dict[str, Any]:
    source, rgb, _, _ = _load(input_path)
    if subject_mask_path is None:
        mask, confidence = _automatic_mask(rgb)
        mask_source = "automatic-saliency"
    else:
        mask = _load_mask(subject_mask_path, rgb.shape[:2])
        confidence, mask_source = 1.0, "user-mask"
    return {
        "file": str(source),
        "sha256": _hash(source),
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "mask_source": mask_source,
        "analysis": _analysis(rgb, mask, confidence),
    }


def _light_map(
    rgb: np.ndarray, mask: np.ndarray, mode: str, strength: float
) -> np.ndarray:
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    luma = np.clip(lab[..., 0] / 100.0, 0.001, 1.0)
    height, width = luma.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    radial = np.clip(np.hypot(xx / width - 0.5, yy / height - 0.5) / 0.70, 0.0, 1.0)
    if mode == "focus":
        ev = 0.10 * mask - 0.16 * (1.0 - mask) * (0.45 + 0.55 * radial)
    elif mode == "depth":
        sigma = max(3.0, max(height, width) * 0.035)
        base = cv2.GaussianBlur(luma, (0, 0), sigma)
        residual = np.tanh((luma - base) / 0.07)
        ev = 0.10 * residual * mask
    elif mode == "balance":
        sigma = max(5.0, max(height, width) * 0.10)
        base = cv2.GaussianBlur(luma, (0, 0), sigma)
        target = float(np.median(base))
        ev = 0.45 * np.log2(np.clip(target / np.clip(base, 0.03, 1.0), 0.6, 1.7))
        ev *= 0.65 + 0.35 * mask
    else:
        raise ValueError(f"不支持的模式: {mode}")
    return np.clip(ev * strength, -0.60, 0.45).astype(np.float32)


def _apply_ev(rgb: np.ndarray, ev: np.ndarray) -> np.ndarray:
    srgb = rgb.astype(np.float32) / 255.0
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    gain = np.power(2.0, ev)[..., None]
    result = np.clip(linear * gain, 0.0, 1.0)
    srgb_result = np.where(
        result <= 0.0031308, result * 12.92, 1.055 * result ** (1 / 2.4) - 0.055
    )
    return np.round(np.clip(srgb_result, 0.0, 1.0) * 255.0).astype(np.uint8)


def _save_photo(
    path: Path, rgb: np.ndarray, exif: bytes | None, icc: bytes | None
) -> None:
    image = Image.fromarray(rgb, mode="RGB")
    options: dict[str, Any] = {}
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        options.update(quality=96, subsampling=0)
        if exif:
            options["exif"] = exif
    if icc:
        options["icc_profile"] = icc
    image.save(path, **options)


def _contact_sheet(
    rgb: np.ndarray, mask: np.ndarray, ev: np.ndarray, result: np.ndarray, path: Path
) -> None:
    height, width = rgb.shape[:2]
    scale = min(1.0, 420 / max(height, width))
    size = (round(width * scale), round(height * scale))
    mask_rgb = cv2.applyColorMap(
        np.round(mask * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS
    )
    mask_rgb = cv2.cvtColor(mask_rgb, cv2.COLOR_BGR2RGB)
    ev_view = np.clip((ev + 0.60) / 1.05, 0.0, 1.0)
    ev_rgb = cv2.applyColorMap(
        np.round(ev_view * 255).astype(np.uint8), cv2.COLORMAP_TURBO
    )
    ev_rgb = cv2.cvtColor(ev_rgb, cv2.COLOR_BGR2RGB)
    panels = [
        ("ORIGINAL", rgb),
        ("MASK", mask_rgb),
        ("LIGHT MAP", ev_rgb),
        ("RESULT", result),
    ]
    margin, label = 14, 42
    canvas = Image.new(
        "RGB",
        (size[0] * 2 + margin * 3, (size[1] + label) * 2 + margin * 3),
        (238, 237, 233),
    )
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    for index, (name, panel) in enumerate(panels):
        row, column = divmod(index, 2)
        x, y = (
            margin + column * (size[0] + margin),
            margin + row * (size[1] + label + margin),
        )
        thumb = cv2.resize(panel, size, interpolation=cv2.INTER_AREA)
        canvas.paste(Image.fromarray(thumb, mode="RGB"), (x, y))
        draw.text((x + 6, y + size[1] + 12), name, fill=(25, 25, 25), font=font)
    canvas.save(path, quality=94)


def sculpt_photo(
    input_path: str | Path,
    output_dir: str | Path,
    mode: str = "focus",
    strength: float = 1.0,
    subject_mask_path: str | Path | None = None,
) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"不支持的模式: {mode}")
    if not 0.0 < strength <= 1.5:
        raise ValueError("strength必须在0至1.5之间")
    source, rgb, exif, icc = _load(input_path)
    if subject_mask_path is None:
        mask, confidence = _automatic_mask(rgb)
        mask_source = "automatic-saliency"
    else:
        mask, confidence = _load_mask(subject_mask_path, rgb.shape[:2]), 1.0
        mask_source = "user-mask"
    if confidence < 0.35 and mode != "balance":
        raise ValueError(
            f"自动主体蒙版置信度不足: {confidence:.3f}。请提供subject_mask_path。"
        )
    ev = _light_map(rgb, mask, mode, strength)
    result = _apply_ev(rgb, ev)

    directory = Path(output_dir).expanduser().resolve()
    suffix = (
        source.suffix.lower()
        if source.suffix.lower() in {".jpg", ".jpeg", ".png"}
        else ".png"
    )
    base = f"{source.stem}_{mode}"
    paths = {
        "image": directory / f"{base}{suffix}",
        "mask": directory / f"{base}_mask.png",
        "light_map": directory / f"{base}_light16.png",
        "preview": directory / f"{base}_preview.jpg",
        "recipe": directory / f"{base}.recipe.json",
        "validation": directory / f"{base}.validation.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))
    directory.mkdir(parents=True, exist_ok=True)
    original_hash = _hash(source)
    _save_photo(paths["image"], result, exif, icc)
    if not cv2.imwrite(
        str(paths["mask"]), np.round(mask * 65535).astype(np.uint16)
    ):
        raise OSError(f"无法写入主体蒙版: {paths['mask']}")
    if not cv2.imwrite(
        str(paths["light_map"]),
        np.round(np.clip((ev + 0.60) / 1.05, 0, 1) * 65535).astype(np.uint16),
    ):
        raise OSError(f"无法写入EV光照图: {paths['light_map']}")
    _contact_sheet(rgb, mask, ev, result, paths["preview"])

    before = _analysis(rgb, mask, confidence)
    after = _analysis(result, mask, confidence)
    blocking: list[str] = []
    if _hash(source) != original_hash:
        blocking.append("原图哈希发生变化")
    if after["highlight_clip_pct"] - before["highlight_clip_pct"] > 0.03:
        blocking.append("新增高光溢出超过0.03个百分点")
    if after["shadow_clip_pct"] - before["shadow_clip_pct"] > 0.05:
        blocking.append("新增暗部死黑超过0.05个百分点")
    validation = {
        "technical_status": "pass" if not blocking else "blocked",
        "status": "review_required" if not blocking else "blocked",
        "blocking": blocking,
        "review_reasons": ["需要查看主体蒙版、EV光照图和结果对照后完成视觉验收"]
        if not blocking
        else [],
        "before": before,
        "after": after,
    }
    recipe = {
        "input": str(source),
        "input_sha256": original_hash,
        "mode": mode,
        "strength": strength,
        "mask_source": mask_source,
        "mask_confidence": confidence,
        "ev_min": float(ev.min()),
        "ev_max": float(ev.max()),
        "outputs": {
            key: str(value)
            for key, value in paths.items()
            if key not in {"recipe", "validation"}
        },
    }
    paths["recipe"].write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["validation"].write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": validation["status"],
        "outputs": recipe["outputs"],
        "recipe": str(paths["recipe"]),
        "validation": str(paths["validation"]),
        "blocking": blocking,
        "review_reasons": validation["review_reasons"],
    }
