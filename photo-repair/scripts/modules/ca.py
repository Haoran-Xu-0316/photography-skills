"""横向色差校正。

横向色差表现为红蓝通道相对绿通道的径向缩放偏差，越靠边角越明显。
估计在降采样图上做，缩放系数与分辨率无关，这样搜索速度快一个量级，
施加时再回到全分辨率。

纵向色差(紫边)成因不同，是离焦造成的，不在这里处理。
"""

import cv2
import numpy as np


def _scale_about_center(ch, s):
    h, w = ch.shape
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    mat = np.array([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]], np.float32)
    return cv2.warpAffine(
        ch, mat, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE
    )


def _search_scale(ch, green, weight, span=0.0018, steps=25):
    scales = np.linspace(1.0 - span, 1.0 + span, steps)
    costs = []
    for s in scales:
        warped = _scale_about_center(ch, float(s))
        costs.append(float(np.sum(weight * (warped - green) ** 2)))
    costs = np.asarray(costs)
    i = int(np.argmin(costs))
    if 0 < i < len(scales) - 1:
        # 抛物线插值取亚步长最优，避免被搜索网格量化
        y0, y1, y2 = costs[i - 1], costs[i], costs[i + 1]
        denom = y0 - 2 * y1 + y2
        if abs(denom) > 1e-12:
            offset = 0.5 * (y0 - y2) / denom
            return float(scales[i] + offset * (scales[1] - scales[0])), float(
                costs.min()
            )
    return float(scales[i]), float(costs.min())


def measure(rgb_linear, est_max_side=900):
    h, w = rgb_linear.shape[:2]
    scale = min(1.0, est_max_side / max(h, w))
    small = (
        cv2.resize(rgb_linear, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else rgb_linear
    )

    g = small[..., 1]
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.hypot(gx, gy)

    hh, ww = g.shape
    ys = (np.arange(hh) - (hh - 1) / 2) / ((hh - 1) / 2)
    xs = (np.arange(ww) - (ww - 1) / 2) / ((ww - 1) / 2)
    r = np.sqrt(ys[:, None] ** 2 + xs[None, :] ** 2)
    # 只在边缘丰富且远离中心的区域估计，中心区域色差本身接近零
    weight = (grad * (r > 0.45)).astype(np.float32)
    if weight.sum() < 1e-3:
        return {
            "red_scale": 1.0,
            "blue_scale": 1.0,
            "max_shift_px": 0.0,
            "reliable": False,
            "note": "边缘信息不足，无法估计色差",
        }

    weight = weight / weight.max()
    rs, _ = _search_scale(small[..., 0], g, weight)
    bs, _ = _search_scale(small[..., 2], g, weight)

    half_diag = np.hypot(h, w) / 2.0
    shift = max(abs(rs - 1.0), abs(bs - 1.0)) * half_diag
    return {
        "red_scale": round(rs, 6),
        "blue_scale": round(bs, 6),
        "max_shift_px": round(float(shift), 2),
        "reliable": True,
        "note": "",
    }


def apply(rgb_linear, model, strength=1.0, min_shift_px=0.4):
    if not model.get("reliable") or model.get("max_shift_px", 0) < min_shift_px:
        return rgb_linear, {"applied": False, "reason": "色差低于可见阈值"}
    out = rgb_linear.copy()
    for idx, key in ((0, "red_scale"), (2, "blue_scale")):
        s = 1.0 + (1.0 / model[key] - 1.0) * float(strength)
        out[..., idx] = _scale_about_center(rgb_linear[..., idx], s)
    return np.clip(out, 0, 1), {
        "applied": True,
        "corrected_shift_px": model["max_shift_px"],
        "strength": float(strength),
    }
