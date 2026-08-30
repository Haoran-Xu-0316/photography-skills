"""Photo loading, relative depth estimation and depth quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class PhotoData:
    path: Path
    rgb: np.ndarray
    exif: bytes | None
    icc_profile: bytes | None


def load_photo(path: str | Path) -> PhotoData:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到照片: {source}")
    if source.suffix.lower() not in SUPPORTED_IMAGES:
        raise ValueError(f"不支持的照片格式: {source.suffix or '无扩展名'}")

    with Image.open(source) as image:
        oriented = ImageOps.exif_transpose(image)
        rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
        exif = oriented.getexif().tobytes() if oriented.getexif() else None
        icc = image.info.get("icc_profile")
    return PhotoData(path=source, rgb=rgb, exif=exif, icc_profile=icc)


def robust_normalize(depth: np.ndarray) -> np.ndarray:
    values = np.asarray(depth, dtype=np.float32)
    finite = np.isfinite(values)
    if not np.any(finite):
        raise ValueError("深度图没有有限值")
    replacement = float(np.median(values[finite]))
    values = np.where(finite, values, replacement)
    low, high = [float(value) for value in np.percentile(values, [2.0, 98.0])]
    if high - low <= 1e-8:
        raise ValueError("深度图动态范围塌缩")
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    normalized = cv2.bilateralFilter(normalized.astype(np.float32), 7, 0.06, 5.0)
    return np.clip(normalized, 0.0, 1.0)


def load_depth_map(
    path: str | Path,
    target_size: tuple[int, int],
    invert: bool = False,
) -> np.ndarray:
    depth_path = Path(path).expanduser().resolve()
    if not depth_path.is_file():
        raise FileNotFoundError(f"找不到深度图: {depth_path}")
    unchanged = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
    if unchanged is None:
        raise ValueError(f"无法读取深度图: {depth_path}")
    if unchanged.ndim == 3:
        if unchanged.shape[2] == 4:
            unchanged = unchanged[..., :3]
        unchanged = cv2.cvtColor(unchanged, cv2.COLOR_BGR2GRAY)
    source_height, source_width = unchanged.shape[:2]
    width, height = target_size
    source_ratio = source_width / source_height
    target_ratio = width / height
    if abs(source_ratio / target_ratio - 1.0) > 0.01:
        raise ValueError(
            "深度图与照片宽高比不一致，禁止通过非等比缩放伪造像素对应关系"
        )
    if np.issubdtype(unchanged.dtype, np.integer):
        depth = unchanged.astype(np.float32) / float(np.iinfo(unchanged.dtype).max)
    else:
        depth = unchanged.astype(np.float32)
    if depth.shape != (height, width):
        depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_CUBIC)
    depth = robust_normalize(depth)
    return 1.0 - depth if invert else depth


def estimate_depth_with_model(
    photo: PhotoData,
    allow_download: bool = False,
    device: str = "cpu",
) -> np.ndarray:
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    except ImportError as exc:
        raise RuntimeError("模型推理需要torch和transformers") from exc

    try:
        processor = AutoImageProcessor.from_pretrained(
            MODEL_ID,
            local_files_only=not allow_download,
        )
        model = AutoModelForDepthEstimation.from_pretrained(
            MODEL_ID,
            local_files_only=not allow_download,
        ).to(device)
    except (OSError, RuntimeError) as exc:
        if not allow_download:
            raise RuntimeError(
                "本地没有Depth Anything V2 Small缓存。请提供深度图，或在用户明确允许后设置allow_model_download=True。"
            ) from exc
        raise RuntimeError(f"深度模型加载失败: {exc}") from exc

    image = Image.fromarray(photo.rgb, mode="RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    model.eval()
    with torch.inference_mode():
        outputs = model(**inputs)
        predicted = outputs.predicted_depth.unsqueeze(1)
        resized = torch.nn.functional.interpolate(
            predicted,
            size=(photo.rgb.shape[0], photo.rgb.shape[1]),
            mode="bicubic",
            align_corners=False,
        ).squeeze()
    depth = resized.detach().cpu().numpy().astype(np.float32)
    return robust_normalize(depth)


def assess_depth(photo_rgb: np.ndarray, depth: np.ndarray) -> dict[str, Any]:
    if depth.shape != photo_rgb.shape[:2]:
        return {
            "status": "blocked",
            "blocking": [f"深度尺寸{depth.shape}与照片尺寸{photo_rgb.shape[:2]}不一致"],
            "warnings": [],
        }

    blocking: list[str] = []
    warnings: list[str] = []
    if not np.all(np.isfinite(depth)):
        blocking.append("深度图包含非有限值")
    minimum, maximum = float(np.min(depth)), float(np.max(depth))
    useful_range = float(np.percentile(depth, 95) - np.percentile(depth, 5))
    if useful_range < 0.08:
        blocking.append(f"深度有效范围过低: {useful_range:.4f}")

    gray = cv2.cvtColor(photo_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    photo_edges = cv2.magnitude(
        cv2.Sobel(gray, cv2.CV_32F, 1, 0),
        cv2.Sobel(gray, cv2.CV_32F, 0, 1),
    )
    depth_edges = cv2.magnitude(
        cv2.Sobel(depth, cv2.CV_32F, 1, 0),
        cv2.Sobel(depth, cv2.CV_32F, 0, 1),
    )
    if np.std(photo_edges) > 1e-6 and np.std(depth_edges) > 1e-6:
        edge_correlation = float(np.corrcoef(photo_edges.ravel(), depth_edges.ravel())[0, 1])
    else:
        edge_correlation = 0.0
    if edge_correlation < 0.03:
        warnings.append("深度边缘与照片结构相关性较低，需要人工检查")

    return {
        "status": "pass" if not blocking else "blocked",
        "blocking": blocking,
        "warnings": warnings,
        "metrics": {
            "minimum": round(minimum, 6),
            "maximum": round(maximum, 6),
            "p05_p95_range": round(useful_range, 6),
            "edge_correlation": round(edge_correlation, 6),
            "near_is_white": True,
        },
    }


def save_depth16(depth: np.ndarray, output_path: str | Path) -> Path:
    destination = Path(output_path).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"深度输出已存在，默认不覆盖: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    array = np.round(np.clip(depth, 0.0, 1.0) * 65535.0).astype(np.uint16)
    if not cv2.imwrite(str(destination), array):
        raise OSError(f"无法写入深度图: {destination}")
    return destination
