"""照片筛选的程序化接口，原始图像全程只读。"""

import copy
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import loader
import report
import scoring
import sidecar
from metrics import dedupe, exposure, sharpness, subjects

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CFG = os.path.join(os.path.dirname(HERE), "assets", "default.yaml")


def load_config(path=DEFAULT_CFG, preset=None, overrides=None):
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    presets = cfg.pop("presets", {}) or {}
    if preset:
        if preset not in presets:
            raise ValueError(f"预设不存在: {preset}，可用: {list(presets)}")
        cfg = _merge(cfg, presets[preset])
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            _set_dotted_value(cfg, key, value)
    else:
        for item in overrides or []:
            _set_dotted(cfg, item)
    cfg["_presets"] = list(presets)
    return cfg


def _merge(base, patch):
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        out[k] = (
            _merge(out[k], v)
            if isinstance(v, dict) and isinstance(out.get(k), dict)
            else v
        )
    return out


def _coerce(text):
    low = text.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            continue
    return text


def _set_dotted(cfg, assignment):
    if "=" not in assignment:
        raise ValueError(f"参数格式应为 键=值，收到: {assignment}")
    key, value = assignment.split("=", 1)
    _set_dotted_value(cfg, key, _coerce(value))


def _set_dotted_value(cfg, key, value):
    node = cfg
    parts = key.strip().split(".")
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = value


def analyze_one(path, cfg):
    gray, bgr, info = loader.load_gray(path)
    meta = loader.read_exif(path)

    sm = sharpness.measure(
        gray,
        tiles=int(cfg["sharpness"]["tiles"]),
        edge_percentile=int(cfg["sharpness"]["edge_percentile"]),
    )
    blur = sharpness.classify(
        sm,
        sharp_width=float(cfg["sharpness"]["sharp_width"]),
        soft_width=float(cfg["sharpness"]["soft_width"]),
        anisotropy_thr=float(cfg["sharpness"]["anisotropy"]),
    )
    ex = exposure.measure(bgr)

    faces, focus = None, None
    if cfg["faces"].get("enabled", True):
        faces = subjects.detect(bgr, float(cfg["faces"]["min_face_ratio"]))
        focus = subjects.focus_on_subject(
            sm, faces, float(cfg["faces"]["focus_tolerance"])
        )

    rec = {
        "name": meta["name"],
        "path": path,
        "source": info["source"],
        "orig_size": info["orig_size"],
        "sharpness": sm,
        "blur_type": blur,
        "exposure": ex,
        "faces": faces,
        "focus_check": focus,
        "hash": dedupe.dhash(bgr),
        "timestamp": meta.get("timestamp"),
        "iso": meta.get("iso"),
        "shutter": meta.get("shutter"),
        "aperture": meta.get("aperture"),
        "focal": meta.get("focal"),
        "camera": meta.get("camera"),
        "lens": meta.get("lens"),
    }
    return rec


def _worker(args):
    path, cfg = args
    try:
        return analyze_one(path, cfg), None
    except Exception as exc:
        return None, f"{os.path.basename(path)}: {exc}"


def analyze_all(files, cfg, jobs=1, progress_callback=None):
    """逐张分析。各张之间完全独立，因此可以直接并行。

    单进程约每张0.3秒，两千张十分钟；八进程压到两分钟以内。瓶颈是纯CPU
    的形态学运算与分块统计，不是IO，所以用进程而非线程，绕开GIL。

    记录里不含图像数据，跨进程传输的只是几KB的指标字典，序列化开销可忽略。
    """
    records, failures = [], []
    t0 = time.time()

    def tick(i):
        if progress_callback and (i % 25 == 0 or i == len(files)):
            done = time.time() - t0
            progress_callback(
                {
                    "completed": i,
                    "total": len(files),
                    "elapsed_seconds": round(done, 2),
                    "estimated_remaining_seconds": round(
                        done / max(i, 1) * (len(files) - i), 2
                    ),
                }
            )

    if jobs > 1 and len(files) > 4:
        from concurrent.futures import ProcessPoolExecutor

        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                for i, (rec, err) in enumerate(
                    pool.map(_worker, [(f, cfg) for f in files], chunksize=4), 1
                ):
                    if rec is not None:
                        records.append(rec)
                    else:
                        failures.append(err)
                    tick(i)
            return records, failures, time.time() - t0
        except Exception:
            # 并行启动失败时退回单进程，结果仍由同一确定性流程计算。
            records, failures = [], []
            t0 = time.time()

    for i, path in enumerate(files, 1):
        rec, err = _worker((path, cfg))
        if rec is not None:
            records.append(rec)
        else:
            failures.append(err)
        tick(i)
    return records, failures, time.time() - t0


def _source_snapshot(files):
    return {
        os.path.realpath(path): (os.stat(path).st_size, os.stat(path).st_mtime_ns)
        for path in files
    }


def _planned_outputs(cfg, out_dir):
    outputs = {}
    if cfg["output"].get("csv", True):
        outputs["csv_report"] = os.path.join(out_dir, "cull_report.csv")
    if cfg["output"].get("json", True):
        outputs["json_report"] = os.path.join(out_dir, "cull_report.json")
    if cfg["output"].get("contact_sheet", True):
        outputs["rejected_contact_sheet"] = os.path.join(out_dir, "rejected_sheet.jpg")
    return outputs


def run(target, cfg, write_xmp, out_dir, jobs=1, progress_callback=None):
    files = loader.list_images(target)
    if not files:
        raise ValueError(f"没有找到可处理的图像: {target}")

    outputs = _planned_outputs(cfg, out_dir)
    collisions = [path for path in outputs.values() if os.path.exists(path)]
    if collisions:
        raise FileExistsError(f"拒绝覆盖既有筛片输出: {collisions}")

    before = _source_snapshot(files)

    records, failures, elapsed = analyze_all(
        files, cfg, jobs=jobs, progress_callback=progress_callback
    )

    if cfg["burst"].get("enabled", True):
        groups = dedupe.group(
            records,
            max_distance=int(cfg["burst"]["max_hash_distance"]),
            max_gap_sec=float(cfg["burst"]["max_gap_sec"]),
            require_time=bool(cfg["burst"].get("require_time", False)),
        )
    else:
        groups = list(range(len(records)))
    for r, g in zip(records, groups):
        r["burst_group"] = g
        r["burst_size"] = 1

    for r in records:
        verdict, reasons, quality = scoring.score_one(r, cfg)
        r["verdict"], r["reasons"], r["quality"] = verdict, reasons, quality

    if cfg["burst"].get("enabled", True):
        scoring.resolve_bursts(records, cfg)

    for r in records:
        rating, label = scoring.to_rating(r, cfg)
        r["rating"], r["label"] = rating, label

    os.makedirs(out_dir, exist_ok=True)
    summary = report.summarize(records)
    if "csv_report" in outputs:
        report.write_csv(records, outputs["csv_report"])
    if "json_report" in outputs:
        report.write_json(records, outputs["json_report"], summary)
    sheet = None
    if "rejected_contact_sheet" in outputs:
        sheet = report.contact_sheet(records, outputs["rejected_contact_sheet"])
        if sheet is None:
            outputs["rejected_contact_sheet"] = None

    # 先完整生成可复核报告，再执行显式XMP更新。这样即使报告目录不可写、
    # 联系表生成失败或序列化出错，也不会留下没有对应审计证据的评级边车。
    sidecars_enabled = write_xmp and cfg["output"].get("write_xmp", True)
    if sidecars_enabled:
        for r in records:
            note = f"photo-cull: {r['verdict']}. " + "; ".join(r["reasons"])
            sidecar.write(r["path"], r["rating"], r["label"], note)
    for r in records:
        r.pop("thumb", None)

    if _source_snapshot(files) != before:
        raise RuntimeError("筛片过程中检测到源图文件状态发生变化")

    return {
        "status": "review_required" if failures else "analyzed",
        "records": records,
        "summary": summary,
        "failures": failures,
        "outputs": outputs,
        "xmp_written": sidecars_enabled,
        "xmp_paths": [sidecar.sidecar_path(path) for path in files]
        if sidecars_enabled
        else [],
        "elapsed_seconds": round(elapsed, 2),
    }


def analyze_photos(
    target,
    output_dir,
    *,
    preset=None,
    overrides=None,
    config_path=DEFAULT_CFG,
    jobs=1,
    progress_callback=None,
):
    """分析照片并生成报告，不写入XMP边车。"""
    cfg = load_config(config_path, preset=preset, overrides=overrides)
    return run(
        target,
        cfg,
        write_xmp=False,
        out_dir=os.fspath(output_dir),
        jobs=jobs,
        progress_callback=progress_callback,
    )


def create_cull_sidecars(
    target,
    output_dir,
    *,
    preset=None,
    overrides=None,
    config_path=DEFAULT_CFG,
    jobs=1,
    progress_callback=None,
):
    """分析照片并显式写入评级XMP；不会移动、删除或覆盖源图。"""
    cfg = load_config(config_path, preset=preset, overrides=overrides)
    return run(
        target,
        cfg,
        write_xmp=True,
        out_dir=os.fspath(output_dir),
        jobs=jobs,
        progress_callback=progress_callback,
    )
