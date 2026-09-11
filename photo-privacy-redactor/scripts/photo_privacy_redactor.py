"""Deterministic visual-content redaction for photographs.

Automatic face detection produces review candidates only. Only user rectangles,
user masks, and explicitly confirmed candidate IDs enter the opaque output mask.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

Decision = Literal["redact", "reject"]
VALID_DECISIONS = {"redact", "reject"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_photo(
    input_path: str | Path,
) -> tuple[Path, Image.Image, bytes | None, bytes | None, str]:
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到照片: {source}")
    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image)
        has_alpha = "A" in oriented.getbands()
        if has_alpha:
            rgba = oriented.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            rgb = background.convert("RGB")
            alpha_action = "flattened-on-opaque-white"
        else:
            rgb = oriented.convert("RGB")
            alpha_action = "not-present"
        exif_data = image.getexif()
        if exif_data:
            exif_data[274] = 1
            exif = exif_data.tobytes()
        else:
            exif = None
        icc = image.info.get("icc_profile")
    return source, rgb, exif, icc, alpha_action


def _candidate_records(
    boxes: list[tuple[int, int, int, int]], image_width: int, image_height: int
) -> list[dict[str, Any]]:
    candidates = []
    for index, box in enumerate(boxes, start=1):
        left, top, right, bottom = box
        width, height = right - left, bottom - top
        expanded = (
            max(0, round(left - 0.18 * width)),
            max(0, round(top - 0.28 * height)),
            min(image_width, round(right + 0.18 * width)),
            min(image_height, round(bottom + 0.22 * height)),
        )
        candidates.append(
            {
                "id": f"face-{index:03d}",
                "candidate_box": list(box),
                "suggested_redaction_box": list(expanded),
                "status": "pending",
            }
        )
    return candidates


def _detect_candidates(
    rgb: np.ndarray,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cascade_root = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if not hasattr(cv2, "CascadeClassifier") or not cascade_root:
        return [], {
            "available": False,
            "name": "opencv-haarcascade-frontalface-default",
            "opencv_version": getattr(cv2, "__version__", "unknown"),
            "reason": "当前OpenCV构建缺少级联接口或数据。请检查requirements.txt中的4.x依赖；未经允许不要改动共享环境。检测恢复前使用用户矩形、蒙版和人工全图复核。",
        }
    cascade_path = Path(cascade_root) / "haarcascade_frontalface_default.xml"
    if not cascade_path.is_file():
        return [], {
            "available": False,
            "name": "opencv-haarcascade-frontalface-default",
            "reason": f"找不到正面人脸候选检测器: {cascade_path}",
        }
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        return [], {
            "available": False,
            "name": "opencv-haarcascade-frontalface-default",
            "reason": f"无法加载正面人脸候选检测器: {cascade_path}",
        }
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.equalizeHist(gray)
    minimum = max(24, round(min(rgb.shape[:2]) * 0.035))
    detected = detector.detectMultiScale(
        gray,
        scaleFactor=1.08,
        minNeighbors=5,
        minSize=(minimum, minimum),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )
    boxes = sorted(
        (
            (int(x), int(y), int(x + width), int(y + height))
            for x, y, width, height in detected
        ),
        key=lambda box: (box[1], box[0], box[3] - box[1], box[2] - box[0]),
    )
    image_height, image_width = rgb.shape[:2]
    candidates = _candidate_records(boxes, image_width, image_height)
    for candidate in candidates:
        candidate["detector"] = "opencv-haarcascade-frontalface-default"
    return candidates, {
        "available": True,
        "name": "opencv-haarcascade-frontalface-default",
        "opencv_version": getattr(cv2, "__version__", "unknown"),
        "reason": None,
    }


def detect_face_candidates(input_path: str | Path) -> dict[str, Any]:
    """Return frontal-face review candidates without modifying any image."""
    source, image, _, _, alpha_action = _load_photo(input_path)
    candidates, detector = _detect_candidates(np.asarray(image, dtype=np.uint8))
    return {
        "input": str(source),
        "input_sha256": _sha256(source),
        "width": image.width,
        "height": image.height,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "face_detector": detector,
        "alpha_action": alpha_action,
        "candidate_only": True,
        "limitations": [
            "只提示正面人脸候选，可能误报或漏报。",
            "不检测车牌、屏幕、票据、证件、二维码或敏感文字。",
            "不检查GPS、EXIF或其他元数据隐私。",
        ],
    }


def _rectangle_box(
    rectangle: dict[str, Any], width: int, height: int
) -> tuple[int, int, int, int]:
    missing = {"left", "top", "right", "bottom"} - rectangle.keys()
    if missing:
        raise ValueError("矩形缺少字段: " + ", ".join(sorted(missing)))
    unit = rectangle.get("unit", "pixel")
    values = [float(rectangle[key]) for key in ("left", "top", "right", "bottom")]
    if unit == "normalized":
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("normalized矩形坐标必须在0至1之间")
        left, top, right, bottom = (
            round(values[0] * width),
            round(values[1] * height),
            round(values[2] * width),
            round(values[3] * height),
        )
    elif unit == "pixel":
        left, top, right, bottom = [round(value) for value in values]
    else:
        raise ValueError(f"不支持的矩形坐标单位: {unit}")
    left, right = max(0, left), min(width, right)
    top, bottom = max(0, top), min(height, bottom)
    if right <= left or bottom <= top:
        raise ValueError("矩形必须具有正面积并与照片相交")
    return left, top, right, bottom


def _load_user_mask(
    mask_path: str | Path, size: tuple[int, int]
) -> tuple[Path, np.ndarray]:
    path = Path(mask_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"找不到蒙版: {path}")
    with Image.open(path) as image:
        mask = ImageOps.exif_transpose(image).convert("L")
        if mask.size != size:
            mask = mask.resize(size, Image.Resampling.NEAREST)
    return path, np.asarray(mask, dtype=np.uint8) >= 128


def _draw_preview(
    image: Image.Image,
    mask: np.ndarray,
    candidates: list[dict[str, Any]],
    path: Path,
) -> None:
    maximum = 1800
    scale = min(1.0, maximum / max(image.size))
    preview_size = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    preview = image.resize(preview_size, Image.Resampling.LANCZOS)
    mask_image = Image.fromarray((mask.astype(np.uint8) * 115), mode="L").resize(
        preview_size, Image.Resampling.NEAREST
    )
    overlay = Image.new("RGBA", preview_size, (0, 0, 0, 0))
    overlay.putalpha(mask_image)
    preview = Image.alpha_composite(preview.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default()
    colors = {"pending": "#E34A33", "redact": "#1B9E77", "reject": "#777777"}
    line_width = max(2, round(4 * scale))
    for candidate in candidates:
        left, top, right, bottom = candidate["candidate_box"]
        box = tuple(round(value * scale) for value in (left, top, right, bottom))
        color = colors[candidate["status"]]
        draw.rectangle(box, outline=color, width=line_width)
        draw.text(
            (box[0] + 4, box[1] + 4),
            f"{candidate['id']} {candidate['status']}",
            fill=color,
            font=font,
        )
    preview.save(path, quality=94)


def _save_redacted(
    path: Path,
    image: Image.Image,
    mask: np.ndarray,
    fill_rgb: tuple[int, int, int],
    exif: bytes | None,
    icc: bytes | None,
) -> None:
    pixels = np.asarray(image, dtype=np.uint8).copy()
    pixels[mask] = np.asarray(fill_rgb, dtype=np.uint8)
    output = Image.fromarray(pixels, mode="RGB")
    options: dict[str, Any] = {}
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        options.update(quality=95, subsampling=0)
    if exif:
        options["exif"] = exif
    if icc:
        options["icc_profile"] = icc
    output.save(path, **options)


def redact_photo(
    input_path: str | Path,
    output_dir: str | Path,
    rectangles: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    mask_paths: list[str | Path] | tuple[str | Path, ...] = (),
    candidate_decisions: dict[str, Decision] | None = None,
    manual_review_confirmed: bool = False,
    fill_rgb: tuple[int, int, int] = (0, 0, 0),
) -> dict[str, Any]:
    """Create an opaque flattened copy and a review package.

    Automatic candidates are redacted only when their decision is explicitly
    ``redact``. A ``reject`` decision records a reviewed false positive.
    """
    source, image, exif, icc, alpha_action = _load_photo(input_path)
    original_hash = _sha256(source)
    width, height = image.size
    decisions = dict(candidate_decisions or {})
    invalid = {
        key: value for key, value in decisions.items() if value not in VALID_DECISIONS
    }
    if invalid:
        raise ValueError(f"候选决定只接受redact或reject: {invalid}")
    if len(fill_rgb) != 3 or any(not 0 <= int(value) <= 255 for value in fill_rgb):
        raise ValueError("fill_rgb必须包含三个0至255整数")

    candidates, detector = _detect_candidates(np.asarray(image, dtype=np.uint8))
    candidate_ids = {candidate["id"] for candidate in candidates}
    unknown_ids = sorted(set(decisions) - candidate_ids)
    if unknown_ids:
        raise ValueError("candidate_decisions包含未知候选: " + ", ".join(unknown_ids))

    mask = np.zeros((height, width), dtype=bool)
    rectangle_records = []
    for index, rectangle in enumerate(rectangles, start=1):
        box = _rectangle_box(rectangle, width, height)
        left, top, right, bottom = box
        mask[top:bottom, left:right] = True
        rectangle_records.append(
            {
                "id": f"user-rectangle-{index:03d}",
                "box": list(box),
                "label": rectangle.get("label"),
            }
        )

    mask_records = []
    for index, mask_path in enumerate(mask_paths, start=1):
        resolved, user_mask = _load_user_mask(mask_path, image.size)
        mask |= user_mask
        mask_records.append(
            {
                "id": f"user-mask-{index:03d}",
                "path": str(resolved),
                "sha256": _sha256(resolved),
                "covered_pixels": int(user_mask.sum()),
            }
        )

    for candidate in candidates:
        decision = decisions.get(candidate["id"])
        candidate["status"] = decision or "pending"
        if decision == "redact":
            left, top, right, bottom = candidate["suggested_redaction_box"]
            mask[top:bottom, left:right] = True

    pending = [
        candidate["id"] for candidate in candidates if candidate["status"] == "pending"
    ]
    if pending:
        status = "needs-candidate-review"
    elif not manual_review_confirmed:
        status = "needs-manual-review"
    else:
        status = "content-redaction-reviewed"

    directory = Path(output_dir).expanduser().resolve()
    paths = {
        "redacted": directory / f"{source.stem}_redacted.png",
        "mask": directory / f"{source.stem}_redaction_mask.png",
        "preview": directory / f"{source.stem}_redaction_preview.jpg",
        "review": directory / f"{source.stem}_privacy_review.json",
    }
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))
    directory.mkdir(parents=True, exist_ok=True)

    _save_redacted(
        paths["redacted"],
        image,
        mask,
        tuple(int(value) for value in fill_rgb),
        exif,
        icc,
    )
    Image.fromarray(mask.astype(np.uint8) * 255, mode="L").save(paths["mask"])
    _draw_preview(image, mask, candidates, paths["preview"])

    review = {
        "status": status,
        "input": str(source),
        "input_sha256": original_hash,
        "original_preserved": _sha256(source) == original_hash,
        "redacted_output": str(paths["redacted"]),
        "mask_output": str(paths["mask"]),
        "preview_output": str(paths["preview"]),
        "fill_rgb": list(fill_rgb),
        "output_encoding": "lossless-png",
        "alpha_action": alpha_action,
        "covered_pixels": int(mask.sum()),
        "covered_fraction": round(float(mask.mean()), 8),
        "user_rectangles": rectangle_records,
        "user_masks": mask_records,
        "face_candidates": candidates,
        "face_detector": detector,
        "pending_candidate_ids": pending,
        "manual_review_confirmed": bool(manual_review_confirmed),
        "manual_missed_review_required": not manual_review_confirmed,
        "review_checklist": [
            "在原始分辨率下检查侧脸、小脸、遮挡脸、背光脸和画面边缘。",
            "用用户矩形或蒙版补充车牌、屏幕、票据、证件、二维码和敏感文字。",
            "确认实心遮挡完整覆盖目标边缘，没有残留可辨识特征。",
            "另行使用交付质检检查GPS、EXIF和其他元数据隐私。",
        ],
        "limitations": [
            "自动检测只提示正面人脸候选，可能误报或漏报。",
            "不自动检测车牌、屏幕、票据、证件、二维码或文字。",
            "不检查或删除GPS、EXIF及其他元数据。",
            "任何状态都不代表不存在全部隐私风险。",
        ],
        "metadata_action": "preserved-with-orientation-normalized-not-reviewed",
    }
    paths["review"].write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**review, "review_output": str(paths["review"])}
