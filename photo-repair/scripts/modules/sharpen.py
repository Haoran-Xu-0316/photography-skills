"""锐化。必须放在流水线末端，且只作用于亮度通道。

用边缘掩膜限制作用范围，平坦区域不锐化，否则会把降噪后残留的
低频噪声重新放大成色斑。阈值参数控制多弱的边缘才参与锐化。
"""

import cv2
import numpy as np
from io_utils import linear_to_srgb, srgb_to_linear


def apply(rgb_linear, cfg):
    amount = float(cfg.get("amount", 0.0))
    if amount <= 1e-3:
        return rgb_linear, {"applied": False}

    radius = float(cfg.get("radius", 1.0))
    threshold = float(cfg.get("threshold", 0.008))

    enc = linear_to_srgb(np.clip(rgb_linear, 0, 1)).astype(np.float32)
    lab = cv2.cvtColor(enc, cv2.COLOR_RGB2Lab)
    L = lab[..., 0] / 100.0

    blur = cv2.GaussianBlur(L, (0, 0), radius)
    detail = L - blur
    mask = np.clip((np.abs(detail) - threshold) / max(threshold, 1e-6), 0, 1)
    sharp = np.clip(L + amount * detail * mask, 0, 1)

    lab[..., 0] = sharp * 100.0
    out = np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1)
    return srgb_to_linear(out).astype(np.float32), {
        "applied": True,
        "amount": amount,
        "radius": radius,
        "threshold": threshold,
    }
