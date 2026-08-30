"""Deterministic, non-generative crop planning for photographs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


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


def _saliency(rgb: np.ndarray) -> np.ndarray:
    height, width = rgb.shape[:2]
    scale = min(1.0, 900 / max(height, width))
    work = cv2.resize(
        rgb,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    hsv = cv2.cvtColor(work.astype(np.float32) / 255.0, cv2.COLOR_RGB2HSV)
    sigma = max(2.0, max(work.shape[:2]) * 0.035)
    local = _normalize(np.abs(gray - cv2.GaussianBlur(gray, (0, 0), sigma)))
    gradient = _normalize(
        cv2.magnitude(
            cv2.Sobel(gray, cv2.CV_32F, 1, 0),
            cv2.Sobel(gray, cv2.CV_32F, 0, 1),
        )
    )
    yy, xx = np.mgrid[0 : work.shape[0], 0 : work.shape[1]].astype(np.float32)
    center = np.exp(
        -(
            ((xx / work.shape[1] - 0.5) / 0.48) ** 2
            + ((yy / work.shape[0] - 0.5) / 0.48) ** 2
        )
    )
    result = _normalize(
        0.37 * local + 0.31 * gradient + 0.12 * hsv[..., 1] + 0.20 * center
    )
    return cv2.resize(result, (width, height), interpolation=cv2.INTER_CUBIC)


def _validate_focus(
    focus_point: tuple[float, float] | None,
) -> tuple[float, float] | None:
    if focus_point is None:
        return None
    x, y = [float(value) for value in focus_point]
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError("focus_point必须使用0至1归一化坐标")
    return x, y


def _visual_center(saliency: np.ndarray) -> tuple[float, float, float]:
    mass = np.clip(saliency - np.percentile(saliency, 55), 0.0, None)
    total = float(mass.sum())
    if total < 1e-8:
        return 0.5, 0.5, 0.0
    yy, xx = np.mgrid[0 : saliency.shape[0], 0 : saliency.shape[1]]
    x = float((xx * mass).sum() / total / saliency.shape[1])
    y = float((yy * mass).sum() / total / saliency.shape[0])
    concentration = float(np.mean(saliency >= np.percentile(saliency, 85)))
    confidence = float(np.clip(1.0 - abs(concentration - 0.15) / 0.25, 0.0, 1.0))
    return x, y, confidence


def analyze_composition(
    input_path: str | Path,
    focus_point: tuple[float, float] | None = None,
) -> dict[str, Any]:
    source, rgb, _, _ = _load(input_path)
    saliency = _saliency(rgb)
    automatic_x, automatic_y, confidence = _visual_center(saliency)
    user_focus = _validate_focus(focus_point)
    focus = user_focus or (automatic_x, automatic_y)
    return {
        "file": str(source),
        "sha256": _hash(source),
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "focus_source": "user" if user_focus else "automatic-saliency",
        "focus_point": {"x": round(focus[0], 6), "y": round(focus[1], 6)},
        "automatic_confidence": round(confidence, 6),
    }


def _parse_ratio(value: str) -> tuple[float, str]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"画幅比例格式错误: {value}")
    try:
        left, right = float(parts[0]), float(parts[1])
    except ValueError as error:
        raise ValueError(f"画幅比例格式错误: {value}") from error
    if left <= 0 or right <= 0:
        raise ValueError(f"画幅比例必须为正数: {value}")
    label = f"{parts[0].strip()}x{parts[1].strip()}".replace(".", "p")
    return left / right, label


def _crop_size(width: int, height: int, ratio: float) -> tuple[int, int]:
    if width / height >= ratio:
        crop_height = height
        crop_width = round(height * ratio)
    else:
        crop_width = width
        crop_height = round(width / ratio)
    return min(width, crop_width), min(height, crop_height)


def _positions(maximum: int) -> list[int]:
    if maximum <= 0:
        return [0]
    return sorted({round(maximum * index / 24) for index in range(25)})


def _thirds_score(
    focus_x: float,
    focus_y: float,
    left: int,
    top: int,
    crop_width: int,
    crop_height: int,
) -> float:
    local_x = (focus_x - left) / crop_width
    local_y = (focus_y - top) / crop_height
    if not (0.0 <= local_x <= 1.0 and 0.0 <= local_y <= 1.0):
        return 0.0
    distance = min(
        np.hypot(local_x - third_x, local_y - third_y)
        for third_x in (1 / 3, 2 / 3)
        for third_y in (1 / 3, 2 / 3)
    )
    return float(np.clip(1.0 - distance / 0.48, 0.0, 1.0))


def _score_box(
    saliency: np.ndarray,
    focus: tuple[float, float],
    box: tuple[int, int, int, int],
) -> dict[str, float]:
    left, top, right, bottom = box
    crop = saliency[top:bottom, left:right]
    total = float(saliency.sum()) + 1e-8
    retained = float(crop.sum() / total)
    focus_pixels = (focus[0] * saliency.shape[1], focus[1] * saliency.shape[0])
    thirds = _thirds_score(
        focus_pixels[0],
        focus_pixels[1],
        left,
        top,
        right - left,
        bottom - top,
    )
    band = max(2, round(min(crop.shape) * 0.035))
    boundary = np.concatenate(
        [
            crop[:band].ravel(),
            crop[-band:].ravel(),
            crop[:, :band].ravel(),
            crop[:, -band:].ravel(),
        ]
    )
    boundary_safety = 1.0 - float(np.mean(boundary))
    vertical = float(
        abs(
            np.mean(crop[:, : crop.shape[1] // 2])
            - np.mean(crop[:, crop.shape[1] // 2 :])
        )
    )
    horizontal = float(
        abs(np.mean(crop[: crop.shape[0] // 2]) - np.mean(crop[crop.shape[0] // 2 :]))
    )
    balance = float(np.clip(1.0 - (vertical + horizontal), 0.0, 1.0))
    score = 0.45 * retained + 0.25 * thirds + 0.20 * boundary_safety + 0.10 * balance
    return {
        "score": round(float(score), 8),
        "saliency_retained": round(retained, 8),
        "thirds_relationship": round(thirds, 8),
        "boundary_safety": round(boundary_safety, 8),
        "edge_balance": round(balance, 8),
    }


def _candidate_boxes(
    saliency: np.ndarray,
    ratio: float,
    focus: tuple[float, float],
) -> list[dict[str, Any]]:
    height, width = saliency.shape
    crop_width, crop_height = _crop_size(width, height, ratio)
    candidates: list[dict[str, Any]] = []
    for left in _positions(width - crop_width):
        for top in _positions(height - crop_height):
            box = (left, top, left + crop_width, top + crop_height)
            candidates.append({"box": box, **_score_box(saliency, focus, box)})
    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        left, top, _, _ = candidate["box"]
        if all(
            abs(left - item["box"][0]) + abs(top - item["box"][1])
            >= 0.08 * (crop_width + crop_height)
            for item in selected
        ):
            selected.append(candidate)
        if len(selected) == 3:
            break
    return selected or candidates[:1]


def _coordinates(
    box: tuple[int, int, int, int], width: int, height: int
) -> dict[str, Any]:
    left, top, right, bottom = box
    return {
        "pixels": {"left": left, "top": top, "right": right, "bottom": bottom},
        "normalized": {
            "left": round(left / width, 8),
            "top": round(top / height, 8),
            "right": round(right / width, 8),
            "bottom": round(bottom / height, 8),
        },
    }


def _save_crop(
    path: Path,
    rgb: np.ndarray,
    box: tuple[int, int, int, int],
    exif: bytes | None,
    icc: bytes | None,
) -> None:
    left, top, right, bottom = box
    image = Image.fromarray(rgb[top:bottom, left:right], mode="RGB")
    options: dict[str, Any] = {}
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        options.update(quality=96, subsampling=0)
        if exif:
            options["exif"] = exif
    if icc:
        options["icc_profile"] = icc
    image.save(path, **options)


def _overlay(
    rgb: np.ndarray,
    plans: list[dict[str, Any]],
    focus: tuple[float, float],
    path: Path,
) -> None:
    height, width = rgb.shape[:2]
    scale = min(1.0, 1400 / max(height, width))
    preview = Image.fromarray(rgb, mode="RGB").resize(
        (round(width * scale), round(height * scale)),
        Image.Resampling.LANCZOS,
    )
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default()
    colors = ["#F25F5C", "#247BA0", "#70C1B3", "#FFE066", "#B388EB"]
    for index, plan in enumerate(plans):
        box = plan["candidates"][0]["box"]
        scaled = tuple(round(value * scale) for value in box)
        color = colors[index % len(colors)]
        draw.rectangle(scaled, outline=color, width=max(2, round(4 * scale)))
        draw.text((scaled[0] + 8, scaled[1] + 8), plan["ratio"], fill=color, font=font)
    focus_xy = (round(focus[0] * width * scale), round(focus[1] * height * scale))
    radius = max(4, round(8 * scale))
    draw.ellipse(
        (
            focus_xy[0] - radius,
            focus_xy[1] - radius,
            focus_xy[0] + radius,
            focus_xy[1] + radius,
        ),
        outline="white",
        width=max(2, round(3 * scale)),
    )
    preview.save(path, quality=94)


def create_crop_set(
    input_path: str | Path,
    output_dir: str | Path,
    aspect_ratios: tuple[str, ...] = ("1:1", "4:5", "3:4", "16:9"),
    focus_point: tuple[float, float] | None = None,
    safe_area_only: bool = False,
) -> dict[str, Any]:
    if not aspect_ratios:
        raise ValueError("aspect_ratios不能为空")
    source, rgb, exif, icc = _load(input_path)
    original_hash = _hash(source)
    saliency = _saliency(rgb)
    auto_x, auto_y, confidence = _visual_center(saliency)
    user_focus = _validate_focus(focus_point)
    focus = user_focus or (auto_x, auto_y)
    directory = Path(output_dir).expanduser().resolve()
    overlay_path = directory / f"{source.stem}_crop_overlay.jpg"
    manifest_path = directory / f"{source.stem}_crop_plan.json"
    requested_outputs = [overlay_path, manifest_path]
    plans: list[dict[str, Any]] = []
    crop_paths: list[Path] = []
    seen_ratios: list[float] = []
    suffix = (
        source.suffix.lower()
        if source.suffix.lower() in {".jpg", ".jpeg", ".png"}
        else ".png"
    )
    for ratio_text in aspect_ratios:
        ratio, label = _parse_ratio(ratio_text)
        if any(abs(ratio - existing_ratio) < 1e-9 for existing_ratio in seen_ratios):
            raise ValueError(f"aspect_ratios包含重复画幅: {ratio_text}")
        seen_ratios.append(ratio)
        candidates = _candidate_boxes(saliency, ratio, focus)
        candidate_records = []
        for candidate in candidates:
            box = candidate["box"]
            candidate_records.append(
                {
                    **{key: value for key, value in candidate.items() if key != "box"},
                    "box": list(box),
                    "coordinates": _coordinates(box, rgb.shape[1], rgb.shape[0]),
                }
            )
        plan = {"ratio": ratio_text, "candidates": candidate_records}
        if not safe_area_only:
            crop_path = directory / f"{source.stem}_crop_{label}{suffix}"
            requested_outputs.append(crop_path)
            crop_paths.append(crop_path)
            plan["output"] = str(crop_path)
        plans.append(plan)
    existing = [str(path) for path in requested_outputs if path.exists()]
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))
    directory.mkdir(parents=True, exist_ok=True)
    for plan, crop_path in zip(plans, crop_paths, strict=False):
        _save_crop(crop_path, rgb, tuple(plan["candidates"][0]["box"]), exif, icc)
    _overlay(rgb, plans, focus, overlay_path)
    manifest = {
        "input": str(source),
        "input_sha256": original_hash,
        "focus_source": "user" if user_focus else "automatic-saliency",
        "focus_point": {"x": focus[0], "y": focus[1]},
        "automatic_confidence": confidence,
        "safe_area_only": safe_area_only,
        "plans": plans,
        "original_preserved": _hash(source) == original_hash,
        "review_required": True,
        "review_reasons": [
            "需要查看构图叠加图和实际裁切结果",
            *(
                [f"自动视觉中心置信度较低: {confidence:.3f}"]
                if not user_focus and confidence < 0.40
                else []
            ),
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "status": "review_required"
        if manifest["original_preserved"]
        else "blocked",
        "technical_status": "pass" if manifest["original_preserved"] else "blocked",
        "overlay": str(overlay_path),
        "manifest": str(manifest_path),
        "crops": [str(path) for path in crop_paths],
        "plans": plans,
        "review_reasons": manifest["review_reasons"],
    }
