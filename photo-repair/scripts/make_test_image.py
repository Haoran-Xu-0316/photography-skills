"""生成带已知缺陷的合成测试图。

缺陷参数写死在GROUND_TRUTH里，用于反过来检验诊断模块的测量精度。
真实照片没有真值可比，只能靠合成图验证算法本身是否成立。
"""

import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from io_utils import linear_to_srgb

GROUND_TRUTH = {
    "corner_ratio": 0.45,  # 边角亮度为中心的45%，约1.15档暗角
    "luma_sigma": 0.020,  # gamma空间亮度噪声标准差
    "chroma_sigma": 0.016,
    "hot_pixels": 240,
    "ca_red_scale": 1.0013,  # 红通道相对绿通道放大
    "ca_blue_scale": 0.9990,
}

H, W = 1600, 2400


def _texture(rng):
    """多尺度噪声叠加硬边结构，模拟真实画面的频率分布。"""
    base = np.zeros((H, W), np.float32)
    for scale, weight in ((160, 0.45), (60, 0.25), (22, 0.16), (8, 0.09), (3, 0.05)):
        small = rng.random((max(2, H // scale), max(2, W // scale))).astype(np.float32)
        base += cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC) * weight
    base = (base - base.min()) / (np.ptp(base) + 1e-6)

    # 硬边结构，用于检验降噪是否糊边、色差校正是否对齐
    for i in range(26):
        x = int(rng.integers(80, W - 80))
        y = int(rng.integers(80, H - 80))
        w = int(rng.integers(30, 220))
        h = int(rng.integers(30, 220))
        cv2.rectangle(
            base,
            (x, y),
            (min(x + w, W - 1), min(y + h, H - 1)),
            float(rng.uniform(0.05, 0.95)),
            -1,
        )
    for i in range(18):
        p1 = (int(rng.integers(0, W)), int(rng.integers(0, H)))
        p2 = (int(rng.integers(0, W)), int(rng.integers(0, H)))
        cv2.line(base, p1, p2, float(rng.uniform(0.1, 0.9)), int(rng.integers(1, 4)))

    # 细密纹理区，检验细节保留
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fine = 0.5 + 0.5 * np.sin(xx / 2.4) * np.sin(yy / 2.9)
    region = np.zeros((H, W), np.float32)
    region[H // 3 : H // 3 + 320, W // 4 : W // 4 + 420] = 1.0
    base = base * (1 - region * 0.5) + fine * region * 0.5
    base = _radial_flatten(base)
    return np.clip(base, 0.02, 0.98)


def _radial_flatten(gray):
    """抹平纹理自身的径向亮度趋势。

    单张图估计暗角的前提是场景统计量与半径无关。合成纹理随机生成时
    往往自带径向趋势，会与暗角混叠，让真值检验失去意义。这里按环带
    归一化把趋势去掉，只保留局部结构。
    """
    h, w = gray.shape
    ys = np.arange(h, dtype=np.float32) - (h - 1) / 2
    xs = np.arange(w, dtype=np.float32) - (w - 1) / 2
    r = np.sqrt(ys[:, None] ** 2 + xs[None, :] ** 2) / np.hypot(
        (h - 1) / 2, (w - 1) / 2
    )

    bins = 48
    idx = np.clip((r * bins).astype(np.int32), 0, bins - 1)
    means = np.array(
        [gray[idx == b].mean() if np.any(idx == b) else np.nan for b in range(bins)],
        np.float32,
    )
    valid = np.isfinite(means)
    means[~valid] = np.nanmean(means)
    kernel = np.ones(5, np.float32) / 5
    means = np.convolve(np.pad(means, 2, mode="edge"), kernel, mode="valid")
    correction = float(np.mean(means)) / np.clip(means, 1e-6, None)
    return gray * correction[idx]


def _scale_about_center(ch, s):
    h, w = ch.shape
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    mat = np.array([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]], np.float32)
    return cv2.warpAffine(
        ch, mat, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE
    )


def build(seed=7):
    rng = np.random.default_rng(seed)
    gray = _texture(rng)
    rgb = np.stack([gray * 0.98, gray, gray * 1.02], axis=2).astype(np.float32)
    tint = np.stack([np.linspace(1.06, 0.94, W)] * H).astype(np.float32)
    rgb[..., 0] *= tint
    rgb[..., 2] *= 2.0 - tint
    clean_linear = np.clip(rgb**2.2, 0, 1).astype(np.float32)  # 转到线性光

    # 1 色差
    dirty = clean_linear.copy()
    dirty[..., 0] = _scale_about_center(dirty[..., 0], GROUND_TRUTH["ca_red_scale"])
    dirty[..., 2] = _scale_about_center(dirty[..., 2], GROUND_TRUTH["ca_blue_scale"])

    # 2 暗角，用四次余弦模型，与真实镜头衰减形态一致
    ys = np.arange(H, dtype=np.float32) - (H - 1) / 2
    xs = np.arange(W, dtype=np.float32) - (W - 1) / 2
    r = np.sqrt(ys[:, None] ** 2 + xs[None, :] ** 2) / np.hypot(
        (H - 1) / 2, (W - 1) / 2
    )
    k = (1.0 / GROUND_TRUTH["corner_ratio"]) ** 0.25 - 1.0
    falloff = (1.0 / (1.0 + k * r) ** 4).astype(np.float32)
    dirty = dirty * falloff[..., None]

    # 3 噪声，在gamma空间注入才符合实际观感，之后转回线性
    enc = linear_to_srgb(np.clip(dirty, 0, 1)).astype(np.float32)
    lab = cv2.cvtColor(enc, cv2.COLOR_RGB2Lab)
    lab[..., 0] += rng.normal(
        0, GROUND_TRUTH["luma_sigma"] * 100, lab.shape[:2]
    ).astype(np.float32)
    lab[..., 1] += rng.normal(
        0, GROUND_TRUTH["chroma_sigma"] * 255, lab.shape[:2]
    ).astype(np.float32)
    lab[..., 2] += rng.normal(
        0, GROUND_TRUTH["chroma_sigma"] * 255, lab.shape[:2]
    ).astype(np.float32)
    noisy = np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1)

    # 4 热噪点
    n = GROUND_TRUTH["hot_pixels"]
    ry = rng.integers(2, H - 2, n)
    rx = rng.integers(2, W - 2, n)
    rc = rng.integers(0, 3, n)
    noisy[ry, rx, rc] = np.clip(noisy[ry, rx, rc] + rng.uniform(0.35, 0.75, n), 0, 1)

    return noisy, clean_linear


def main():
    here = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    os.makedirs(here, exist_ok=True)
    noisy, clean = build()
    u8 = (noisy * 255 + 0.5).astype(np.uint8)
    u16 = (noisy * 65535 + 0.5).astype(np.uint16)
    cv2.imwrite(
        os.path.join(here, "test_defects.jpg"),
        cv2.cvtColor(u8, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 98],
    )
    cv2.imwrite(
        os.path.join(here, "test_defects.tif"), cv2.cvtColor(u16, cv2.COLOR_RGB2BGR)
    )
    cv2.imwrite(
        os.path.join(here, "test_clean_reference.jpg"),
        cv2.cvtColor(
            (linear_to_srgb(clean) * 255 + 0.5).astype(np.uint8), cv2.COLOR_RGB2BGR
        ),
        [cv2.IMWRITE_JPEG_QUALITY, 98],
    )
    with open(os.path.join(here, "ground_truth.json"), "w", encoding="utf-8") as fh:
        json.dump(GROUND_TRUTH, fh, ensure_ascii=False, indent=2)
    print(f"已生成测试图与真值文件到 {here}")
    print(json.dumps(GROUND_TRUTH, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
