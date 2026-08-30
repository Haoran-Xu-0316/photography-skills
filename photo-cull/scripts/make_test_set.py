"""生成筛片测试集。

每张图的缺陷类型与程度写死在文件名和真值文件里，用于检验各项指标
能否复现真值。真实照片没有真值可比，只能靠合成集验证指标本身成立。

覆盖六类：清晰、失焦、抖动、连拍重复、过曝、欠曝，以及一张浅景深图
用于检验主体锐利但背景虚化时不会被误判为糊片。
"""

import json
import os
import sys

import cv2
import numpy as np

H, W = 1400, 2100


def _scene(rng, kind="general"):
    """构造带丰富硬边的场景，边缘宽度指标依赖真实阶跃边。"""
    img = np.zeros((H, W, 3), np.float32)
    for scale, weight in ((200, 0.5), (70, 0.28), (25, 0.14), (9, 0.08)):
        small = rng.random((max(2, H // scale), max(2, W // scale), 3)).astype(
            np.float32
        )
        img += cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC) * weight
    img = (img - img.min()) / (np.ptp(img) + 1e-6) * 0.5 + 0.2

    for _ in range(34):
        x, y = int(rng.integers(40, W - 240)), int(rng.integers(40, H - 240))
        bw, bh = int(rng.integers(50, 230)), int(rng.integers(50, 230))
        color = rng.uniform(0.05, 0.95, 3).astype(np.float32)
        cv2.rectangle(img, (x, y), (x + bw, y + bh), color.tolist(), -1)
    for _ in range(22):
        p1 = (int(rng.integers(0, W)), int(rng.integers(0, H)))
        p2 = (int(rng.integers(0, W)), int(rng.integers(0, H)))
        cv2.line(
            img, p1, p2, rng.uniform(0.05, 0.95, 3).tolist(), int(rng.integers(2, 6))
        )
    for _ in range(14):
        c = (int(rng.integers(100, W - 100)), int(rng.integers(100, H - 100)))
        cv2.circle(
            img, c, int(rng.integers(20, 90)), rng.uniform(0.05, 0.95, 3).tolist(), -1
        )
    return np.clip(img, 0.01, 0.99)


def _defocus(img, radius):
    if radius <= 0:
        return img
    k = int(radius * 2) * 2 + 1
    disk = np.zeros((k, k), np.float32)
    cv2.circle(disk, (k // 2, k // 2), int(radius), 1.0, -1)
    disk /= disk.sum()
    return cv2.filter2D(img, -1, disk)


def _motion(img, length, angle):
    if length <= 1:
        return img
    k = np.zeros((length, length), np.float32)
    c = length // 2
    rad = np.deg2rad(angle)
    for t in np.linspace(-c, c, length * 3):
        x, y = int(round(c + np.cos(rad) * t)), int(round(c - np.sin(rad) * t))
        if 0 <= x < length and 0 <= y < length:
            k[y, x] = 1.0
    k /= k.sum()
    return cv2.filter2D(img, -1, k)


def _shallow_dof(img, rng, blur=7.0):
    """主体锐利背景虚化。用于检验浅景深不被误判为失焦。"""
    mask = np.zeros((H, W), np.float32)
    cv2.ellipse(mask, (W // 2, H // 2), (W // 6, H // 3), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), 40)[..., None]
    return img * mask + _defocus(img, blur) * (1 - mask)


def _expose(img, stops):
    return np.clip(img * (2.0**stops), 0, 1)


def _noise(img, rng, sigma=0.006):
    return np.clip(img + rng.normal(0, sigma, img.shape).astype(np.float32), 0, 1)


def build(out_dir, seed=5):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)
    truth = {}
    # 每张独立场景。若共用同一底图，感知哈希会把它们全部并成一个连拍组，
    # 连拍检测就失去了检验意义
    scenes = {n: _scene(np.random.default_rng(seed * 100 + n)) for n in range(1, 10)}

    def save(name, img, **meta):
        img = _noise(np.clip(img, 0, 1), rng)
        path = os.path.join(out_dir, name)
        cv2.imwrite(
            path,
            (img[..., ::-1] * 255 + 0.5).astype(np.uint8),
            [cv2.IMWRITE_JPEG_QUALITY, 96],
        )
        truth[name] = meta

    save("01_sharp.jpg", scenes[1], defect="none", expect="sharp")
    save(
        "02_defocus_r2.jpg",
        _defocus(scenes[2], 2.0),
        defect="defocus",
        radius=2.0,
        expect="defocus",
    )
    save(
        "03_defocus_r4.jpg",
        _defocus(scenes[3], 4.0),
        defect="defocus",
        radius=4.0,
        expect="defocus",
    )
    save(
        "04_defocus_r8.jpg",
        _defocus(scenes[4], 8.0),
        defect="defocus",
        radius=8.0,
        expect="defocus",
    )
    save(
        "05_motion_9px_0deg.jpg",
        _motion(scenes[5], 9, 0),
        defect="motion",
        length=9,
        angle=0,
        expect="motion_blur",
    )
    save(
        "06_motion_17px_60deg.jpg",
        _motion(scenes[6], 17, 60),
        defect="motion",
        length=17,
        angle=60,
        expect="motion_blur",
    )
    save(
        "07_shallow_dof.jpg",
        _shallow_dof(scenes[7], rng),
        defect="none",
        expect="sharp",
        note="浅景深，主体锐利背景虚化，不应判为糊",
    )
    save(
        "08_overexposed.jpg",
        _expose(scenes[8], 1.6),
        defect="overexposed",
        stops=2.0,
        expect="sharp",
    )
    save(
        "09_underexposed.jpg",
        _expose(scenes[9], -2.6),
        defect="underexposed",
        stops=-2.6,
        expect="sharp",
    )

    # 连拍组：同一构图的五张，轻微位移与不同程度模糊，只有一张最锐
    burst_base = _scene(np.random.default_rng(seed + 1))
    for i, blur in enumerate([1.5, 0.0, 3.0, 2.2, 5.0], start=1):
        M = np.float32([[1, 0, rng.uniform(-6, 6)], [0, 1, rng.uniform(-6, 6)]])
        shifted = cv2.warpAffine(burst_base, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        soft = shifted if blur <= 0 else cv2.GaussianBlur(shifted, (0, 0), blur)
        save(
            f"10_burst_{i}.jpg",
            soft,
            defect="burst",
            burst_group="A",
            blur_radius=blur,
            expect="sharp" if blur == 0.0 else "soft",
            best_of_burst=(blur == 0.0),
        )

    with open(os.path.join(out_dir, "ground_truth.json"), "w", encoding="utf-8") as fh:
        json.dump(truth, fh, ensure_ascii=False, indent=2)
    print(f"已生成 {len(truth)} 张测试图到 {out_dir}")
    return truth


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
