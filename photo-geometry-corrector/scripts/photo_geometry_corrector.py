"""Deterministic photo geometry correction without aesthetic reframing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_photo(
    input_path: str | Path,
) -> tuple[Path, np.ndarray, bytes | None, bytes | None]:
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到照片: {source}")
    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image)
        rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
        exif = oriented.getexif().tobytes() if oriented.getexif() else None
        icc = image.info.get("icc_profile")
    return source, rgb, exif, icc


def _save_photo(
    output_path: Path,
    rgb: np.ndarray,
    exif: bytes | None,
    icc: bytes | None,
) -> None:
    image = Image.fromarray(rgb, mode="RGB")
    options: dict[str, Any] = {}
    suffix = output_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        options.update(quality=96, subsampling=0)
    elif suffix in {".tif", ".tiff"}:
        options["compression"] = "tiff_lzw"
    if exif:
        options["exif"] = exif
    if icc:
        options["icc_profile"] = icc
    image.save(output_path, **options)


def _output_paths(
    source: Path, output_dir: str | Path, label: str
) -> tuple[Path, Path]:
    directory = Path(output_dir).expanduser().resolve()
    suffix = (
        source.suffix.lower() if source.suffix.lower() in SUPPORTED_SUFFIXES else ".png"
    )
    image_path = directory / f"{source.stem}_{label}{suffix}"
    report_path = directory / f"{source.stem}_{label}.geometry.json"
    if image_path == source or report_path == source:
        raise ValueError("输出路径不得与输入路径相同")
    existing = [str(path) for path in (image_path, report_path) if path.exists()]
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))
    directory.mkdir(parents=True, exist_ok=True)
    return image_path, report_path


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order])
    cutoff = float(weights.sum()) / 2.0
    return float(sorted_values[np.searchsorted(cumulative, cutoff, side="left")])


def _detect_horizon(rgb: np.ndarray) -> dict[str, Any]:
    height, width = rgb.shape[:2]
    scale = min(1.0, 1600.0 / max(height, width))
    work = cv2.resize(
        rgb,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0.9)
    edges = cv2.Canny(gray, 50, 150)
    minimum_length = max(24, round(work.shape[1] * 0.12))
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 720,
        threshold=max(28, round(minimum_length * 0.35)),
        minLineLength=minimum_length,
        maxLineGap=max(8, round(minimum_length * 0.08)),
    )
    candidates: list[tuple[float, float]] = []
    if lines is not None:
        for raw in np.asarray(lines).reshape(-1, 4):
            x1, y1, x2, y2 = [float(value) for value in raw]
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle > 90:
                angle -= 180
            elif angle < -90:
                angle += 180
            length = float(np.hypot(x2 - x1, y2 - y1))
            if abs(angle) <= 20.0:
                candidates.append((angle, length))
    if not candidates:
        return {
            "angle_degrees": None,
            "confidence": 0.0,
            "line_count": 0,
            "angle_mad_degrees": None,
        }
    angles = np.asarray([item[0] for item in candidates], dtype=np.float64)
    weights = np.asarray([item[1] for item in candidates], dtype=np.float64)
    angle = _weighted_median(angles, weights)
    deviation = _weighted_median(np.abs(angles - angle), weights)
    coverage = min(1.0, float(weights.sum()) / (work.shape[1] * 2.5))
    agreement = float(np.exp(-((deviation / 3.0) ** 2)))
    confidence = float(np.clip(coverage * agreement, 0.0, 1.0))
    return {
        "angle_degrees": round(angle, 6),
        "confidence": round(confidence, 6),
        "line_count": len(candidates),
        "angle_mad_degrees": round(deviation, 6),
    }


def analyze_geometry(input_path: str | Path) -> dict[str, Any]:
    source, rgb, _, _ = _load_photo(input_path)
    return {
        "file": str(source),
        "sha256": _sha256(source),
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "horizon": _detect_horizon(rgb),
    }


def _largest_rectangle(binary: np.ndarray) -> tuple[int, int, int, int]:
    height, width = binary.shape
    heights = np.zeros(width, dtype=np.int32)
    best_area = 0
    best = (0, 0, 0, 0)
    for row in range(height):
        heights = np.where(binary[row] > 0, heights + 1, 0)
        stack: list[tuple[int, int]] = []
        for column in range(width + 1):
            current = int(heights[column]) if column < width else 0
            start = column
            while stack and stack[-1][1] > current:
                index, bar_height = stack.pop()
                area = bar_height * (column - index)
                if area > best_area:
                    best_area = area
                    best = (index, row - bar_height + 1, column, row + 1)
                start = index
            if not stack or stack[-1][1] < current:
                stack.append((start, current))
    if best_area <= 0:
        raise ValueError("几何变换后没有可用的完整矩形区域")
    return best


def _valid_crop(
    mask: np.ndarray, sample_long_side: int = 1600
) -> tuple[int, int, int, int]:
    height, width = mask.shape
    scale = min(1.0, sample_long_side / max(height, width))
    if scale < 1.0:
        sampled = cv2.resize(
            mask,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        sampled = (sampled >= 255).astype(np.uint8)
    else:
        sampled = (mask > 0).astype(np.uint8)
    left, top, right, bottom = _largest_rectangle(sampled)
    scale_x = width / sampled.shape[1]
    scale_y = height / sampled.shape[0]
    left = min(width - 1, max(0, int(np.ceil(left * scale_x)) + 1))
    top = min(height - 1, max(0, int(np.ceil(top * scale_y)) + 1))
    right = max(left + 1, min(width, int(np.floor(right * scale_x)) - 1))
    bottom = max(top + 1, min(height, int(np.floor(bottom * scale_y)) - 1))

    invalid = (mask == 0).astype(np.uint8)
    integral = cv2.integral(invalid)

    def invalid_count(box: tuple[int, int, int, int]) -> int:
        x1, y1, x2, y2 = box
        return int(
            integral[y2, x2] - integral[y1, x2] - integral[y2, x1] + integral[y1, x1]
        )

    box = (left, top, right, bottom)
    while invalid_count(box) and right - left > 2 and bottom - top > 2:
        edge_counts = [
            invalid_count((left, top, left + 1, bottom)),
            invalid_count((right - 1, top, right, bottom)),
            invalid_count((left, top, right, top + 1)),
            invalid_count((left, bottom - 1, right, bottom)),
        ]
        edge = int(np.argmax(edge_counts))
        if edge == 0:
            left += 1
        elif edge == 1:
            right -= 1
        elif edge == 2:
            top += 1
        else:
            bottom -= 1
        box = (left, top, right, bottom)
    if invalid_count(box):
        raise ValueError("无法在变换结果中找到没有无效像素的裁切区域")
    return box


def _crop(rgb: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = box
    return rgb[top:bottom, left:right].copy()


def _base_report(
    source: Path,
    source_hash: str,
    transform: str,
    output_path: Path,
    output_rgb: np.ndarray,
) -> dict[str, Any]:
    return {
        "status": "pass" if _sha256(source) == source_hash else "blocked",
        "acceptance_status": "visual-review-required",
        "visual_review_required": True,
        "transform": transform,
        "input": str(source),
        "input_sha256": source_hash,
        "original_preserved": _sha256(source) == source_hash,
        "output": str(output_path),
        "output_width": output_rgb.shape[1],
        "output_height": output_rgb.shape[0],
    }


def correct_horizon(
    input_path: str | Path,
    output_dir: str | Path,
    angle_degrees: float | None = None,
    automatic_detection_confirmed: bool = False,
) -> dict[str, Any]:
    source, rgb, exif, icc = _load_photo(input_path)
    source_hash = _sha256(source)
    detection = _detect_horizon(rgb)
    if angle_degrees is None:
        if detection["angle_degrees"] is None or detection["confidence"] < 0.35:
            raise ValueError("自动水平线置信度不足，请显式提供angle_degrees")
        if not automatic_detection_confirmed:
            raise ValueError(
                "自动水平线只提供建议；请先视觉确认，再显式提供angle_degrees或设置automatic_detection_confirmed=True"
            )
        angle = float(detection["angle_degrees"])
        angle_source = "automatic-confirmed"
    else:
        angle = float(angle_degrees)
        angle_source = "user"
    if not np.isfinite(angle) or abs(angle) > 45.0:
        raise ValueError("angle_degrees必须是负45至正45之间的有限值")

    height, width = rgb.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    canvas_width = max(1, int(np.ceil(height * sine + width * cosine)))
    canvas_height = max(1, int(np.ceil(height * cosine + width * sine)))
    matrix[0, 2] += canvas_width / 2.0 - center[0]
    matrix[1, 2] += canvas_height / 2.0 - center[1]
    transformed = cv2.warpAffine(
        rgb,
        matrix,
        (canvas_width, canvas_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    valid_mask = cv2.warpAffine(
        np.full((height, width), 255, dtype=np.uint8),
        matrix,
        (canvas_width, canvas_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    crop_box = _valid_crop(valid_mask)
    result = _crop(transformed, crop_box)
    image_path, report_path = _output_paths(source, output_dir, "horizon")
    _save_photo(image_path, result, exif, icc)
    report = {
        **_base_report(source, source_hash, "horizon", image_path, result),
        "angle_degrees": angle,
        "angle_source": angle_source,
        "automatic_detection": detection,
        "affine_matrix": matrix.tolist(),
        "transformed_canvas": {"width": canvas_width, "height": canvas_height},
        "valid_crop_box": {
            "left": crop_box[0],
            "top": crop_box[1],
            "right": crop_box[2],
            "bottom": crop_box[3],
        },
        "crop_reason": "remove-transform-invalid-border-only",
        "invalid_pixels_in_output": int(np.sum(_crop(valid_mask, crop_box) == 0)),
    }
    _write_report(report_path, report)
    return {**report, "report": str(report_path)}


def _points_array(
    source_points: Sequence[Sequence[float]],
    width: int,
    height: int,
    points_normalized: bool,
) -> np.ndarray:
    points = np.asarray(source_points, dtype=np.float32)
    if points.shape != (4, 2) or not np.all(np.isfinite(points)):
        raise ValueError("source_points必须是4×2有限坐标，顺序为左上、右上、右下、左下")
    if points_normalized:
        if np.any(points < 0.0) or np.any(points > 1.0):
            raise ValueError("归一化source_points必须在0至1之间")
        points = points * np.array([width - 1, height - 1], dtype=np.float32)
    elif (
        np.any(points[:, 0] < 0)
        or np.any(points[:, 0] >= width)
        or np.any(points[:, 1] < 0)
        or np.any(points[:, 1] >= height)
    ):
        raise ValueError("像素source_points必须位于照片范围内")
    contour = points.reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 4.0:
        raise ValueError("source_points必须构成非退化凸四边形且不能自交")
    return points


def correct_perspective(
    input_path: str | Path,
    output_dir: str | Path,
    source_points: Sequence[Sequence[float]],
    output_size: tuple[int, int] | None = None,
    points_normalized: bool = False,
) -> dict[str, Any]:
    source, rgb, exif, icc = _load_photo(input_path)
    source_hash = _sha256(source)
    height, width = rgb.shape[:2]
    points = _points_array(source_points, width, height, points_normalized)
    if output_size is None:
        top = float(np.linalg.norm(points[1] - points[0]))
        bottom = float(np.linalg.norm(points[2] - points[3]))
        left = float(np.linalg.norm(points[3] - points[0]))
        right = float(np.linalg.norm(points[2] - points[1]))
        output_width = max(1, round(max(top, bottom)))
        output_height = max(1, round(max(left, right)))
    else:
        output_width, output_height = [int(value) for value in output_size]
        if output_width <= 0 or output_height <= 0:
            raise ValueError("output_size的宽高必须为正整数")
    destination = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(points, destination)
    result = cv2.warpPerspective(
        rgb,
        matrix,
        (output_width, output_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    image_path, report_path = _output_paths(source, output_dir, "perspective")
    _save_photo(image_path, result, exif, icc)
    report = {
        **_base_report(source, source_hash, "perspective", image_path, result),
        "source_points_pixels": points.tolist(),
        "points_normalized": points_normalized,
        "destination_points": destination.tolist(),
        "homography": matrix.tolist(),
        "crop_reason": "user-specified-plane-only",
        "generated_fill": False,
    }
    _write_report(report_path, report)
    return {**report, "report": str(report_path)}


def _camera_parameters(
    camera_matrix: Sequence[Sequence[float]],
    distortion_coefficients: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(camera_matrix, dtype=np.float64)
    coefficients = np.asarray(distortion_coefficients, dtype=np.float64).reshape(-1)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("camera_matrix必须是3×3有限矩阵")
    if len(coefficients) not in {4, 5, 8, 12, 14} or not np.all(
        np.isfinite(coefficients)
    ):
        raise ValueError("distortion_coefficients必须包含4、5、8、12或14个有限系数")
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0:
        raise ValueError("camera_matrix焦距必须为正数")
    if not np.allclose(matrix[2], [0.0, 0.0, 1.0], rtol=0.0, atol=1e-9):
        raise ValueError("camera_matrix最后一行必须为[0, 0, 1]")
    return matrix, coefficients


def correct_calibrated_distortion(
    input_path: str | Path,
    output_dir: str | Path,
    camera_matrix: Sequence[Sequence[float]],
    distortion_coefficients: Sequence[float],
) -> dict[str, Any]:
    source, rgb, exif, icc = _load_photo(input_path)
    source_hash = _sha256(source)
    matrix, coefficients = _camera_parameters(camera_matrix, distortion_coefficients)
    height, width = rgb.shape[:2]
    map_x, map_y = cv2.initUndistortRectifyMap(
        matrix,
        coefficients,
        None,
        matrix,
        (width, height),
        cv2.CV_32FC1,
    )
    transformed = cv2.remap(
        rgb,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    valid_mask = (
        (map_x >= 0.0)
        & (map_x <= width - 1.0)
        & (map_y >= 0.0)
        & (map_y <= height - 1.0)
    ).astype(np.uint8) * 255
    crop_box = _valid_crop(valid_mask)
    result = _crop(transformed, crop_box)
    image_path, report_path = _output_paths(source, output_dir, "undistorted")
    _save_photo(image_path, result, exif, icc)
    report = {
        **_base_report(
            source, source_hash, "calibrated-distortion", image_path, result
        ),
        "camera_matrix": matrix.tolist(),
        "distortion_coefficients": coefficients.tolist(),
        "valid_crop_box": {
            "left": crop_box[0],
            "top": crop_box[1],
            "right": crop_box[2],
            "bottom": crop_box[3],
        },
        "crop_reason": "remove-transform-invalid-border-only",
        "invalid_pixels_in_output": int(np.sum(_crop(valid_mask, crop_box) == 0)),
    }
    _write_report(report_path, report)
    return {**report, "report": str(report_path)}
