"""流水线编排。

处理顺序是本项目最不能改的部分:

    坏点 -> 色差 -> 暗角 -> 降噪 -> 锐化

暗角校正必须在降噪之前。校正会给边角施加最高数倍的增益，噪声被同步
放大，若先降噪后校正，边角会明显比中心脏。锐化必须在最后，否则后续
任何平滑操作都会抵消掉锐化，同时前面步骤残留的噪声会被锐化放大。
"""

import copy
import json
import os

import io_utils
import numpy as np
import repair_metrics as metrics
from modules import ca, denoise, hotpixel, lensprofile, sharpen, vignette


def load_config(path, preset=None, overrides=None):
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    presets = cfg.pop("presets", {}) or {}
    explicit = set()
    if preset:
        if preset not in presets:
            raise KeyError(f"预设不存在: {preset}，可用: {list(presets)}")
        cfg = _deep_merge(cfg, presets[preset])
        explicit |= _dotted_keys(presets[preset])
    cfg["_presets"] = list(presets)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            explicit.add(_set_dotted_value(cfg, key, value))
    else:
        for item in overrides or []:
            explicit.add(_set_dotted(cfg, item))
    # 记录用户显式指定过的参数，自动推荐不得覆盖，否则预设形同虚设
    cfg["_explicit"] = sorted(explicit)
    return cfg


def _dotted_keys(node, prefix=""):
    keys = set()
    for k, v in (node or {}).items():
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            keys |= _dotted_keys(v, path + ".")
        else:
            keys.add(path)
    return keys


def _deep_merge(base, patch):
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _coerce(text):
    low = text.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _set_dotted(cfg, assignment):
    if "=" not in assignment:
        raise ValueError(f"参数格式应为 键=值，收到: {assignment}")
    key, value = assignment.split("=", 1)
    return _set_dotted_value(cfg, key, _coerce(value))


def _set_dotted_value(cfg, key, value):
    node = cfg
    parts = key.strip().split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value
    return key.strip()


def calibrate(paths, cfg, store_path=None):
    """从平场帧建立镜头暗角配置文件。"""
    store = lensprofile.load_store(store_path)
    results = []
    for path in paths:
        rgb, meta = io_utils.load(path, cfg.get("raw"))
        try:
            entry = lensprofile.build_entry(rgb, meta)
        except ValueError as exc:
            results.append(
                {"file": os.path.basename(path), "ok": False, "reason": str(exc)}
            )
            continue
        key = lensprofile.add(store, meta, entry)
        results.append(
            {"file": os.path.basename(path), "ok": True, "lens": key, **entry}
        )
    return results, lensprofile.save_store(store, store_path)


def diagnose(rgb_linear, meta, cfg):
    """只测量不修改，输出可量化的问题清单。"""
    noise = metrics.estimate_noise(rgb_linear)
    clip = metrics.clipping_stats(rgb_linear)
    vig = vignette.measure(
        rgb_linear,
        bins=int(cfg.get("diagnose", {}).get("vignette_bins", 40)),
        min_confidence=float(cfg.get("vignette", {}).get("min_confidence", 0.35)),
    )
    chrom = ca.measure(rgb_linear)
    profile_hit = (
        lensprofile.lookup(lensprofile.load_store(), meta)
        if cfg.get("vignette", {}).get("use_lens_profile", True)
        else None
    )
    if profile_hit:
        vig = dict(vig)
        vig["lens_profile"] = profile_hit["matched"]
        vig["profile_corner_ratio"] = profile_hit["corner_ratio"]
    prior = metrics.iso_prior_sigma(meta.iso)

    report = {
        "file": os.path.basename(meta.get("path", "")),
        "exif": meta.describe(),
        "iso": meta.iso,
        "resolution": f"{rgb_linear.shape[1]}x{rgb_linear.shape[0]}",
        "noise": noise,
        "iso_prior_sigma": None if prior is None else round(prior, 5),
        "exposure": clip,
        "vignette": {k: v for k, v in vig.items() if k != "profile"},
        "chromatic_aberration": chrom,
        "issues": [],
    }
    report["_vignette_full"] = vig

    sl, sc = noise["luma_sigma"], noise["chroma_sigma"]
    if sl > 0.022 or sc > 0.020:
        report["issues"].append(
            f"噪声偏高，亮度sigma={sl:.4f} 色度sigma={sc:.4f}，建议降噪"
        )
    elif sl > 0.010:
        report["issues"].append(f"轻度噪声，亮度sigma={sl:.4f}，可轻降")
    if prior and sl > prior * 1.6:
        report["issues"].append("实测噪声显著高于该ISO预期，多为欠曝后期提亮所致")

    if vig["reliable"] and vig["falloff_stops"] > 0.25:
        report["issues"].append(
            f"暗角{vig['falloff_stops']:.2f}档，边角亮度为中心的{vig['corner_ratio']:.2f}倍"
        )
    elif vig["note"]:
        report["issues"].append(f"暗角判定: {vig['note']}")

    if chrom["reliable"] and chrom["max_shift_px"] >= 0.6:
        report["issues"].append(f"横向色差边角位移{chrom['max_shift_px']:.2f}像素")

    if clip["highlight_clip_pct"] > 2.0:
        report["issues"].append(
            f"高光溢出{clip['highlight_clip_pct']:.2f}%，该部分无法恢复"
        )
    if clip["shadow_crush_pct"] > 5.0:
        report["issues"].append(f"暗部死黑{clip['shadow_crush_pct']:.2f}%")

    if not report["issues"]:
        report["issues"].append("未检出明显问题")
    return report


def auto_params(report, cfg):
    """按诊断结果推荐参数。

    只填用户没有显式指定的参数。预设和程序化覆盖值优先级最高，
    否则用户选了预设却被自动推荐覆盖，预设形同虚设。
    """
    cfg = copy.deepcopy(cfg)
    explicit = set(cfg.get("_explicit", []))
    sl = report["noise"]["luma_sigma"]
    sc = report["noise"]["chroma_sigma"]

    def put(key, value):
        if key in explicit:
            return
        section, name = key.split(".")
        cfg[section][name] = value

    if sl < 0.006 and sc < 0.006:
        put("denoise.luma_strength", 0.0)
        put("denoise.chroma_strength", 1.5)
    elif sl < 0.014:
        put("denoise.luma_strength", 0.75)
        put("denoise.chroma_strength", 2.5)
        put("denoise.detail_recovery", 0.45)
    elif sl < 0.030:
        put("denoise.luma_strength", 0.95)
        put("denoise.chroma_strength", 3.2)
        put("denoise.detail_recovery", 0.35)
    else:
        put("denoise.luma_strength", 1.15)
        put("denoise.chroma_strength", 4.0)
        put("denoise.detail_recovery", 0.25)

    vig = report["vignette"]
    if vig.get("reliable") and vig.get("falloff_stops", 0) > 0.15:
        # 保留约一成暗角，全补会让画面显得平，且边角信噪比过度恶化
        put("vignette.strength", 0.9)
    else:
        put("vignette.strength", min(cfg["vignette"].get("strength", 1.0), 0.5))

    if report["chromatic_aberration"].get("max_shift_px", 0) < 0.4:
        put("ca.enabled", False)

    # 降噪越重越需要补锐，但补过头噪点回流
    put("sharpen.amount", float(np.clip(0.25 + sl * 6.0, 0.25, 0.6)))
    cfg["_auto"] = True
    return cfg


def run_pipeline(rgb_linear, meta, cfg, report=None, stages=None):
    """执行修复。stages为None时按配置全跑，否则只跑指定阶段。"""
    stages = stages or ("hotpixel", "ca", "vignette", "denoise", "sharpen")
    img = rgb_linear
    log = {}

    if "hotpixel" in stages and cfg["hotpixel"].get("enabled", True):
        sigma_hint = (report or {}).get("noise", {}).get("luma_sigma", 0.004)
        img, log["hotpixel"] = hotpixel.detect_and_fix(
            img,
            sigma_hint=sigma_hint,
            k=float(cfg["hotpixel"].get("k", 8.0)),
            max_fix_ratio=float(cfg["hotpixel"].get("max_fix_ratio", 0.0008)),
        )

    if "ca" in stages and cfg["ca"].get("enabled", True):
        model = (report or {}).get("chromatic_aberration") or ca.measure(img)
        img, log["ca"] = ca.apply(
            img,
            model,
            strength=float(cfg["ca"].get("strength", 1.0)),
            min_shift_px=float(cfg["ca"].get("min_shift_px", 0.4)),
        )

    if "vignette" in stages and cfg["vignette"].get("enabled", True):
        model = None
        if cfg["vignette"].get("use_lens_profile", True):
            # 平场校准出的模型是精确解，优先于单张盲估
            model = lensprofile.lookup(lensprofile.load_store(), meta)
        model = model or (report or {}).get("_vignette_full") or vignette.measure(img)
        img, log["vignette"] = vignette.apply(
            img,
            model,
            strength=float(cfg["vignette"].get("strength", 1.0)),
            max_gain=float(cfg["vignette"].get("max_gain", 3.5)),
            auto_strength=bool(cfg["vignette"].get("auto_strength", True)),
        )

    if "denoise" in stages and cfg["denoise"].get("enabled", True):
        noise = (report or {}).get("noise") or metrics.estimate_noise(img)
        prior = metrics.iso_prior_sigma(meta.iso)
        img, log["denoise"] = denoise.apply(img, noise, cfg["denoise"], iso_prior=prior)

    if "sharpen" in stages and cfg["sharpen"].get("enabled", True):
        img, log["sharpen"] = sharpen.apply(img, cfg["sharpen"])

    return img, log


def process_file(path, cfg, out_dir, auto=True, save_report=True):
    rgb, meta = io_utils.load(path, cfg.get("raw"))
    stem = os.path.splitext(os.path.basename(path))[0]
    target = io_utils.resolve_output_path(
        os.path.join(out_dir, stem + "_fixed"), meta, cfg.get("output")
    )
    report_path = os.path.join(out_dir, stem + "_report.json")
    collisions = [
        candidate
        for candidate in (target, report_path if save_report else None)
        if candidate and os.path.exists(candidate)
    ]
    if collisions:
        raise FileExistsError(f"拒绝覆盖既有修复输出: {collisions}")

    report = diagnose(rgb, meta, cfg)
    used = auto_params(report, cfg) if auto else cfg
    out, log = run_pipeline(rgb, meta, used, report=report)

    os.makedirs(out_dir, exist_ok=True)
    target = io_utils.save(
        os.path.join(out_dir, stem + "_fixed"), out, meta, cfg.get("output")
    )

    after = metrics.estimate_noise(out)
    report["result"] = {
        "output": target,
        "exif_copy_status": meta.get("exif_copy_status", "not_applicable"),
        "stages": log,
        "noise_after": after,
        "luma_noise_reduction_pct": _reduction(
            report["noise"]["luma_sigma"], after["luma_sigma"]
        ),
        "chroma_noise_reduction_pct": _reduction(
            report["noise"]["chroma_sigma"], after["chroma_sigma"]
        ),
        "params": {
            k: used[k] for k in ("hotpixel", "ca", "vignette", "denoise", "sharpen")
        },
    }
    if save_report:
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {k: v for k, v in report.items() if not k.startswith("_")},
                fh,
                ensure_ascii=False,
                indent=2,
            )
    return report


def _reduction(before, after):
    if before <= 1e-6:
        return 0.0
    return round(100.0 * (1.0 - after / before), 1)
