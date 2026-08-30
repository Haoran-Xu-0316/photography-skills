"""客观指标测量。所有函数只读，不修改图像。"""

from itertools import pairwise

import cv2
import numpy as np
from io_utils import linear_to_srgb, luminance


def _highpass(gray):
    """Immerkaer高通核，对图像内容不敏感，只响应像素级随机波动。"""
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    return cv2.filter2D(gray, cv2.CV_32F, kernel) / 6.0


def estimate_noise(rgb_linear, tile=48, flat_percentile=15):
    """在最平坦的一批图块上测量亮度与色度噪声。"""
    encoded = linear_to_srgb(np.clip(rgb_linear, 0, 1)).astype(np.float32)
    lab = cv2.cvtColor(encoded, cv2.COLOR_RGB2Lab)
    luminance_channel = lab[..., 0] / 100.0
    chroma = (np.abs(lab[..., 1]) + np.abs(lab[..., 2])) / 255.0

    highpass_luma = _highpass(luminance_channel)
    highpass_a = _highpass(lab[..., 1] / 255.0)
    highpass_b = _highpass(lab[..., 2] / 255.0)

    height, width = luminance_channel.shape
    row_count = max(1, height // tile)
    column_count = max(1, width // tile)
    luma_sigmas = []
    chroma_sigmas = []
    activities = []
    for row in range(row_count):
        for column in range(column_count):
            y_start = row * tile
            x_start = column * tile
            block = luminance_channel[y_start : y_start + tile, x_start : x_start + tile]
            if block.size < 64:
                continue
            mean = float(block.mean())
            if mean < 0.02 or mean > 0.97:
                continue
            activities.append(float(np.std(cv2.blur(block, (5, 5)))))
            luma_sigmas.append(
                float(np.std(highpass_luma[y_start : y_start + tile, x_start : x_start + tile]))
            )
            sigma_a = np.std(highpass_a[y_start : y_start + tile, x_start : x_start + tile])
            sigma_b = np.std(highpass_b[y_start : y_start + tile, x_start : x_start + tile])
            chroma_sigmas.append(float((sigma_a + sigma_b) / 2))

    if not luma_sigmas:
        return {"luma_sigma": 0.0, "chroma_sigma": 0.0, "samples": 0}

    order = np.argsort(np.asarray(activities))
    keep = max(1, int(len(order) * flat_percentile / 100))
    selected = order[:keep]
    return {
        "luma_sigma": round(float(np.median(np.asarray(luma_sigmas)[selected])), 5),
        "chroma_sigma": round(
            float(np.median(np.asarray(chroma_sigmas)[selected])), 5
        ),
        "samples": len(luma_sigmas),
        "mean_chroma": round(float(chroma.mean()), 4),
    }


def clipping_stats(rgb_linear):
    encoded = linear_to_srgb(np.clip(rgb_linear, 0, 1))
    highlight = float(np.mean(np.max(encoded, axis=2) >= 0.996)) * 100
    shadow = float(np.mean(luminance(rgb_linear) <= 0.0015)) * 100
    luma = luminance(rgb_linear)
    return {
        "highlight_clip_pct": round(highlight, 3),
        "shadow_crush_pct": round(shadow, 3),
        "median_luma": round(float(np.median(luma)), 4),
        "dynamic_range_stops": round(
            float(
                np.log2(
                    max(np.percentile(luma, 99.5), 1e-6)
                    / max(np.percentile(luma, 0.5), 1e-6)
                )
            ),
            2,
        ),
    }


def iso_prior_sigma(iso):
    """按ISO插值预期亮度噪声，只作为实测失败时的先验。"""
    if not iso:
        return None
    table = [
        (100, 0.0025),
        (400, 0.0045),
        (800, 0.0070),
        (1600, 0.0110),
        (3200, 0.0170),
        (6400, 0.0260),
        (12800, 0.0390),
        (25600, 0.0580),
        (51200, 0.0850),
        (102400, 0.1200),
    ]
    if iso <= table[0][0]:
        return table[0][1]
    if iso >= table[-1][0]:
        return table[-1][1]
    for (iso_low, sigma_low), (iso_high, sigma_high) in pairwise(table):
        if iso_low <= iso <= iso_high:
            weight = (np.log2(iso) - np.log2(iso_low)) / (
                np.log2(iso_high) - np.log2(iso_low)
            )
            return float(sigma_low + weight * (sigma_high - sigma_low))
    return table[-1][1]
