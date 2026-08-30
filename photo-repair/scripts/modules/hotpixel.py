"""坏点与热噪点修复。

判据是孤立性而非绝对亮度: 真实细节在邻域内有支撑，热噪点没有。
设了修复比例上限，防止把星点、雨滴、高光碎斑当成坏点抹掉。
"""

import cv2
import numpy as np


def detect_and_fix(rgb_linear, sigma_hint=0.004, k=8.0, max_fix_ratio=0.0008):
    """判据是孤立性，不是绝对亮度。

    只用固定阈值会把细密纹理当成坏点。像素级的真实结构，比如羽毛、
    织物、远处树枝，经过中值滤波后残差同样很大。区别在于真实结构的
    邻域本身也在起伏，而热噪点周围是平的。因此阈值必须随邻域起伏
    自适应抬高，纹理区自动变严，平坦区保持灵敏。
    """
    out = rgb_linear.copy()
    total = 0
    h, w = rgb_linear.shape[:2]
    cap = int(h * w * max_fix_ratio)

    for c in range(3):
        ch = rgb_linear[..., c]
        med = cv2.medianBlur(ch, 3)
        diff = ch - med
        adiff = np.abs(diff)

        # 全局尺度，用MAD估计，抗异常值
        mad = float(np.median(np.abs(diff - np.median(diff)))) + 1e-7
        global_scale = max(mad * 1.4826, sigma_hint * 0.3)

        # 邻域起伏尺度。用中值图算局部标准差，中值图已剔除孤立点本身的影响，
        # 因此反映的是周围真实结构的活跃程度
        mean = cv2.boxFilter(med, -1, (5, 5))
        sq = cv2.boxFilter(med * med, -1, (5, 5))
        local_std = np.sqrt(np.maximum(sq - mean * mean, 0.0))

        thr = k * np.maximum(global_scale, local_std * 0.9)
        mask = adiff > thr

        if mask.sum() > cap:
            need = 100.0 * (1.0 - cap / mask.size)
            floor = float(np.percentile(adiff, min(need, 99.999)))
            mask &= adiff > floor

        # 孤立性: 邻域内同时超阈的像素过多，说明是成片的结构而非孤立点
        neighbors = cv2.boxFilter(mask.astype(np.float32), -1, (5, 5), normalize=False)
        mask &= neighbors <= 3

        out[..., c][mask] = med[mask]
        total += int(mask.sum())

    return out, {
        "pixels_fixed": total,
        "ratio_pct": round(100.0 * total / (h * w * 3), 5),
    }
