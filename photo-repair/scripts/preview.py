"""调参用的对比预览。

全图跑一遍降噪再看效果，一轮几十秒，调五次参数就是几分钟。
这里只在中心、边缘、边角三处各裁一块做100%对比，一轮一两秒，
参数定下来再对全图跑。

裁切位置的选择有讲究: 边角看暗角和色差，中心看降噪对细节的影响，
边缘看两者叠加后的表现。
"""

import os

import cv2
import io_utils
import numpy as np
from pipeline import run_pipeline

LABELS = ("corner", "edge", "center")


def _crop_boxes(h, w, size):
    size = int(min(size, h // 2, w // 2))
    margin = int(size * 0.15)
    return [
        ("corner", margin, margin),
        ("edge", h // 2 - size // 2, margin),
        ("center", h // 2 - size // 2, w // 2 - size // 2),
    ], size


def _annotate(tile, text):
    out = tile.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1] - 1, 22), (0, 0, 0), -1)
    cv2.putText(
        out,
        text,
        (6, 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return out


def build(path, cfg, out_path, size=420):
    """几何类修复作用于全图，耗时的降噪锐化只作用于裁切块。"""
    from pipeline import auto_params, diagnose

    if os.path.realpath(path) == os.path.realpath(out_path):
        raise ValueError("修复预览路径不得与源图相同")
    if os.path.exists(out_path):
        raise FileExistsError(f"拒绝覆盖既有修复预览: {out_path}")

    rgb, meta = io_utils.load(path, cfg.get("raw"))
    report = diagnose(rgb, meta, cfg)
    used = auto_params(report, cfg) if cfg.get("_auto_preview", True) else cfg

    geom, geom_log = run_pipeline(
        rgb, meta, used, report=report, stages=("hotpixel", "ca", "vignette")
    )

    boxes, size = _crop_boxes(*rgb.shape[:2], size)
    rows = []
    for name, y, x in boxes:
        before = rgb[y : y + size, x : x + size]
        stage_in = geom[y : y + size, x : x + size]
        after, _ = run_pipeline(
            stage_in, meta, used, report=report, stages=("denoise", "sharpen")
        )
        left = _annotate(io_utils.to_encoded_u8(before), f"{name}  before")
        right = _annotate(io_utils.to_encoded_u8(after), f"{name}  after")
        sep = np.full((size, 4, 3), 40, np.uint8)
        rows.append(np.hstack([left, sep, right]))

    gap = np.full((4, rows[0].shape[1], 3), 40, np.uint8)
    grid = rows[0]
    for row in rows[1:]:
        grid = np.vstack([grid, gap, row])

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    if not cv2.imwrite(out_path, cv2.cvtColor(grid, cv2.COLOR_RGB2BGR)):
        raise OSError(f"写入修复预览失败: {out_path}")
    return out_path, report, used, geom_log
