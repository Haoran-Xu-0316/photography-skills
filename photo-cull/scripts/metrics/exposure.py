"""曝光评估。

只报告不可逆的问题。高光溢出的像素信息已经丢失，暗部死黑同理，这两项
是删片依据。整体偏亮偏暗则不是，RAW有充足的后期空间，报告出来供参考
但不参与判废。
"""

import cv2
import numpy as np


def measure(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    arr = bgr.astype(np.float32) / 255.0

    # 通道级判断。单通道溢出在高饱和色彩上很常见，比如红花，
    # 用灰度判断会漏掉，那部分色彩细节实际已经丢失
    clip_hi = float(np.mean(np.max(arr, axis=2) >= 0.996)) * 100
    clip_lo = float(np.mean(gray <= 0.008)) * 100

    hist = cv2.calcHist(
        [(gray * 255).astype(np.uint8)], [0], None, [64], [0, 256]
    ).ravel()
    hist = hist / max(hist.sum(), 1)

    median = float(np.median(gray))
    p01, p99 = float(np.percentile(gray, 1)), float(np.percentile(gray, 99))

    return {
        "highlight_clip_pct": round(clip_hi, 3),
        "shadow_crush_pct": round(clip_lo, 3),
        "median_luma": round(median, 4),
        "contrast_range": round(p99 - p01, 4),
        "exposure_bias_stops": round(float(np.log2(max(median, 1e-4) / 0.18)), 2),
        # 相对反差。绝对反差会把欠曝误判成误拍，欠曝的片子只是整体偏暗，
        # 反差按自身亮度衡量并不低，RAW里完全可以提亮回来；镜头盖和严重
        # 雾霾则是无论怎么归一化都平
        "relative_contrast": round(float((p99 - p01) / (median + 0.05)), 3),
        "histogram": [round(float(v), 5) for v in hist],
    }
