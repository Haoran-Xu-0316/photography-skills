"""镜头暗角配置文件。

单张估计的前提是场景亮度统计与半径无关，这个前提在旋转对称的亮度
分布下原理上无法成立，任何算法都分不出是暗角还是景物。唯一的精确解
是拍平场校准帧: 对着均匀光源或纯净天空，同一枚镜头逐档光圈各拍一张，
此时场景已知均匀，测出的径向衰减就是镜头本身的暗角。

校准结果按镜头、焦段、光圈三级索引存起来，之后修图时自动查表，
查到就用精确模型，查不到再退回单张估计。
"""

import json
import os

import numpy as np
from io_utils import luminance
from modules import vignette

# 存到用户目录而非skill目录。skill应保持只读，且校准结果要能跨版本升级保留
STORE = os.environ.get("PHOTO_REPAIR_PROFILES") or os.path.join(
    os.path.expanduser("~"), ".photo-repair", "lens_profiles.json"
)


def _key(meta):
    lens = meta.get("lens") or meta.get("camera") or "unknown"
    return str(lens).strip()


def load_store(path=None):
    path = path or STORE
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_store(store, path=None):
    path = path or STORE
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2)
    return path


def build_entry(rgb_linear, meta, bins=48):
    """从平场帧提取衰减模型。场景均匀，故用中位数而非高分位数。"""
    lum = luminance(rgb_linear).astype(np.float32)
    r = vignette._radius_map(*lum.shape)
    mask = (lum > 0.005) & (lum < 0.995)
    if mask.mean() < 0.6:
        raise ValueError("平场帧曝光不当，有效像素不足六成。建议曝光到直方图中部偏右")

    prof, counts = vignette._profile(lum, r, mask, bins, pct=50.0)
    coef, res = vignette._fit(np.linspace(0, 1, bins), prof, counts)

    # 平场帧本应极其平滑，残差大说明拍到了云、渐变或脏点
    if res > 0.06:
        raise ValueError(
            f"平场帧不够均匀，拟合残差{res:.3f}。避免拍到云层、渐变天空或直射光斑"
        )

    corner = float(np.exp(coef[0] + coef[1]))
    return {
        "coef": [float(c) for c in coef],
        "corner_ratio": round(corner, 4),
        "falloff_stops": round(float(-np.log2(max(corner, 1e-3))), 3),
        "fit_residual": round(res, 4),
        "focal": meta.get("focal"),
        "aperture": meta.get("aperture"),
        "source": os.path.basename(meta.get("path", "")),
    }


def add(store, meta, entry):
    key = _key(meta)
    store.setdefault(key, [])
    focal, aperture = entry.get("focal"), entry.get("aperture")
    store[key] = [
        e
        for e in store[key]
        if not (e.get("focal") == focal and e.get("aperture") == aperture)
    ]
    store[key].append(entry)
    store[key].sort(key=lambda e: (e.get("focal") or 0, e.get("aperture") or 0))
    return key


def lookup(store, meta, focal_tol=0.25, aperture_tol=1.0):
    """按镜头精确匹配，焦段与光圈取最近邻。

    暗角随光圈收缩快速减弱，随焦段变化，容差放太宽会用错模型，
    宁可查不到退回单张估计，也不要套一个明显不对的曲线。
    """
    entries = store.get(_key(meta))
    if not entries:
        return None
    focal, aperture = meta.get("focal"), meta.get("aperture")
    if focal is None and aperture is None:
        return None

    best, best_cost = None, None
    for e in entries:
        cost = 0.0
        if focal and e.get("focal"):
            rel = abs(np.log2(focal / e["focal"]))
            if rel > focal_tol:
                continue
            cost += rel * 2.0
        if aperture and e.get("aperture"):
            stops = abs(np.log2((aperture / e["aperture"]) ** 2))
            if stops > aperture_tol:
                continue
            cost += stops
        if best_cost is None or cost < best_cost:
            best, best_cost = e, cost

    if best is None:
        return None
    return {
        "coef": best["coef"],
        "corner_ratio": best["corner_ratio"],
        "falloff_stops": best["falloff_stops"],
        "confidence": 1.0,
        "symmetry": 1.0,
        "reliable": True,
        "source": "lens_profile",
        "matched": f"{best.get('focal')}mm f/{best.get('aperture')}",
        "note": "",
    }
