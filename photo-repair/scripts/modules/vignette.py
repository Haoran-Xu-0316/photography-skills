"""暗角检测与校正。

难点不在校正而在检测。逆光天空、暗前景、四角有暗物体的构图，
都会让简单的径向亮度统计误判成暗角，强行校正会把画面拉花。

三重防护:
    1. 环带内取中位数而非均值，抑制局部亮暗物体
    2. 分四象限独立统计，象限之间差异过大说明是构图造成的亮度不均，
       而非镜头暗角(镜头暗角必然旋转对称)，据此给出置信度
    3. 置信度低时自动衰减校正强度，而不是直接放弃
"""

import numpy as np
from io_utils import luminance


def _radius_map(h, w, center=None):
    cy, cx = ((h - 1) / 2, (w - 1) / 2) if center is None else center
    ys = np.arange(h, dtype=np.float32) - cy
    xs = np.arange(w, dtype=np.float32) - cx
    norm = np.hypot(cy, cx)
    r = np.sqrt(ys[:, None] ** 2 + xs[None, :] ** 2) / norm
    return r.astype(np.float32)


def _profile(lum, r, mask, bins, pct=80.0, min_count=200):
    """环带亮度剖面。

    统计量取高分位数而非中位数，这是本模块最关键的一处选择。
    暗角把边角压暗，若用中位数并配合暗部有效性阈值，边角会有更多像素
    落到阈值以下被剔除，剩下的都是偏亮像素，外圈统计被系统性抬高，
    暗角被严重低估。高分位数落在曝光充分的像素上，远离黑位截断和
    噪声底噪，且暗角是乘性的，对任何分位数的缩放比例都一致。
    """
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(r[mask], edges) - 1, 0, bins - 1)
    vals = lum[mask]
    prof = np.full(bins, np.nan, np.float32)
    counts = np.zeros(bins, np.int64)
    for b in range(bins):
        sel = vals[idx == b]
        counts[b] = sel.size
        if sel.size >= min_count:
            prof[b] = np.percentile(sel, pct)
    return prof, counts


def _lstsq_log(rv, logy, w, orders):
    design = np.stack([rv**k for k in orders], axis=1)
    coef, *_ = np.linalg.lstsq(design * w[:, None], logy * w, rcond=None)
    return coef, design


def _huber_weights(res, base_w):
    scale = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-6
    return base_w * np.clip(1.345 * scale / np.maximum(np.abs(res), 1e-9), 0.0, 1.0)


def _fit(rv, prof, counts, iters=6):
    """对数空间稳健拟合 log L(r) = a + c1*r^2 + c2*r^4。

    截距a必须参与拟合。早期版本先把剖面除以最内圈的值再拟合无截距模型，
    等于把一个只有几千像素支撑的高方差单点估计当成基准，中心基准偏高
    多少，暗角就被低估多少。让a自己去吸收场景整体亮度，衰减量由
    exp(c1+c2)给出，与任何一圈的绝对值无关。

    退化分支同样必须带截距。只投影到r^2而不同时估计常数项，等价于强迫
    曲线过原点，是有偏估计，实测只能还原三成左右的衰减量。

    权重用Huber迭代重加权，避免个别被大面积景物占据的环带拉偏整条曲线。
    """
    v = np.isfinite(prof) & (prof > 0)
    r = rv[v].astype(np.float64)
    logy = np.log(prof[v].astype(np.float64))
    base_w = np.sqrt(counts[v].astype(np.float64))

    def solve(orders):
        w = base_w.copy()
        coef = design = None
        for _ in range(iters):
            coef, design = _lstsq_log(r, logy, w, orders)
            w = _huber_weights(logy - design @ coef, base_w)
        return coef, float(np.sqrt(np.mean((logy - design @ coef) ** 2)))

    coef, res = solve((0, 2, 4))
    c = np.array([coef[1], coef[2]])

    probe = np.linspace(0, 1, 64)
    curve = np.exp(c[0] * probe**2 + c[1] * probe**4)
    # 容差随衰减幅度缩放，避免近乎平坦的曲线因数值抖动被误判为非单调
    tol = max(1e-4, 0.02 * abs(curve[0] - curve[-1]))
    if np.any(np.diff(curve) > tol):
        coef2, res = solve((0, 2))
        c = np.array([min(float(coef2[1]), 0.0), 0.0])
    return c, res


def measure(rgb_linear, bins=40, min_confidence=0.35, percentile=70.0):
    """返回暗角衰减模型。模型形式 m(r) = exp(c1*r^2 + c2*r^4)。

    前提假设是场景亮度统计量与半径无关。天空在上、暗前景在下这类构图
    会违反该假设，象限检验能识别其中的方向性成分并降低置信度；但若场景
    恰好存在旋转对称的亮度趋势，单张估计原理上无法与暗角区分，此时需要
    用平场校准帧建立镜头配置文件。
    """
    lum = luminance(rgb_linear).astype(np.float32)
    h, w = lum.shape
    r = _radius_map(h, w)

    # 只排除真实饱和像素。任何针对亮度本身的绝对阈值都会造成半径相关的
    # 选择偏差: 边角被暗角压暗后更容易躲过高光掩膜、更容易撞上暗部掩膜
    mask = lum < 0.995
    if mask.mean() < 0.15:
        return _empty_model("画面过曝，有效像素不足")

    prof, counts = _profile(lum, r, mask, bins, pct=percentile)
    if np.isfinite(prof).sum() < bins * 0.5:
        return _empty_model("有效环带不足")

    rv = np.linspace(0.0, 1.0, bins)
    coef, fit_res = _fit(rv, prof, counts)

    # 方向性检验。镜头暗角旋转对称，侧光、天空亮地面暗这类构图造成的
    # 明暗不均带方向性。分左右上下四个半幅各算一条衰减比，半幅样本量是
    # 象限的两倍，统计稳定得多。象限级独立拟合试过，同一枚镜头的真实暗角
    # 在四个象限能估出两倍以上的差距，误杀严重，不可用
    hh, ww = lum.shape
    halves = []
    for sl in (
        (slice(None), slice(0, ww // 2)),
        (slice(None), slice(ww // 2, ww)),
        (slice(0, hh // 2), slice(None)),
        (slice(hh // 2, hh), slice(None)),
    ):
        hp, _ = _profile(lum[sl], r[sl], mask[sl], bins, pct=percentile, min_count=200)
        inner = np.nanmedian(hp[2 : max(4, int(bins * 0.35))])
        outer = np.nanmedian(hp[int(bins * 0.75) :])
        halves.append(outer / inner if np.isfinite(inner) and inner > 1e-6 else np.nan)

    arr = np.asarray(halves, dtype=np.float64)
    corner_log = float(coef[0] + coef[1])
    if np.isfinite(arr).all() and np.nanmean(arr) > 1e-6:
        level = float(np.nanmean(arr))
        asym = max(abs(arr[0] - arr[1]), abs(arr[2] - arr[3])) / level
        # 场景本底差异实测在0.11到0.18，明确的方向性光照在0.39以上
        sym = float(np.clip(1.0 - (asym - 0.15) / 0.20, 0.0, 1.0))
    else:
        asym, sym = float("nan"), 0.0
    # 拟合残差过大说明剖面不服从单调径向模型，同样应降低置信度
    quality = float(np.clip(1.0 - fit_res / 0.30, 0.0, 1.0))
    confidence = round(float(sym * 0.7 + quality * 0.3), 3)

    corner = float(np.exp(corner_log))
    model = {
        "coef": [float(c) for c in coef],
        "corner_ratio": round(corner, 4),
        "falloff_stops": round(float(-np.log2(max(corner, 1e-3))), 3),
        "confidence": confidence,
        "symmetry": round(sym, 3),
        "asymmetry": None if not np.isfinite(asym) else round(float(asym), 4),
        "fit_residual": round(fit_res, 4),
        "half_ratios": [
            None if not np.isfinite(x) else round(float(x), 4) for x in arr
        ],
        "reliable": bool(confidence >= min_confidence and 0.12 < corner < 1.03),
        "profile": [None if not np.isfinite(v) else round(float(v), 6) for v in prof],
        "note": "",
    }
    if corner >= 1.03:
        model["note"] = "边角不暗于中心，无需校正"
        model["reliable"] = False
    elif confidence < min_confidence:
        model["note"] = "径向衰减不对称或不服从暗角模型，判定不可靠，已降低校正强度"
    return model


def _empty_model(note):
    return {
        "coef": [0.0, 0.0],
        "corner_ratio": 1.0,
        "falloff_stops": 0.0,
        "confidence": 0.0,
        "reliable": False,
        "profile": [],
        "note": note,
    }


def gain_map(shape, coef, strength=1.0, max_gain=3.5):
    h, w = shape
    r = _radius_map(h, w)
    m = np.exp(coef[0] * r**2 + coef[1] * r**4)
    m = np.clip(m, 1.0 / max_gain, 1.0)
    gain = (1.0 / m) ** float(strength)
    return np.clip(gain, 1.0, max_gain).astype(np.float32)


def apply(rgb_linear, model, strength=1.0, max_gain=3.5, auto_strength=True):
    """在线性光下施加增益。必须在降噪之前调用，否则边角噪声会被一并放大。"""
    if not model.get("reliable"):
        if not auto_strength:
            return rgb_linear, {
                "applied": False,
                "reason": model.get("note", "模型不可靠"),
            }
        strength = strength * float(model.get("confidence", 0.0))
        if strength < 0.08:
            return rgb_linear, {
                "applied": False,
                "reason": model.get("note", "模型不可靠"),
            }

    gain = gain_map(rgb_linear.shape[:2], model["coef"], strength, max_gain)
    out = rgb_linear * gain[..., None]
    return np.clip(out, 0.0, 1.0), {
        "applied": True,
        "strength": round(float(strength), 3),
        "max_gain_used": round(float(gain.max()), 3),
    }
