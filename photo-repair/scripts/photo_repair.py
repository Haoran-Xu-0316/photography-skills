"""照片缺陷诊断与修复的程序化接口。"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import io_utils
import pipeline
import preview as repair_preview

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DEFAULT_CFG = SKILL_ROOT / "assets" / "default.yaml"
SUPPORTED = io_utils.RAW_EXT | io_utils.LDR_EXT


def _collect(input_source):
    if isinstance(input_source, (str, os.PathLike)):
        candidate = Path(input_source).expanduser().resolve()
        if candidate.is_file():
            paths = [candidate]
        elif candidate.is_dir():
            paths = sorted(
                path
                for path in candidate.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED
            )
        else:
            raise FileNotFoundError(f"输入不存在: {candidate}")
    else:
        paths = [Path(path).expanduser().resolve() for path in input_source]

    unique_paths = []
    seen = set()
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"输入文件不存在: {path}")
        if path.suffix.lower() not in SUPPORTED:
            raise ValueError(f"不支持的图像格式: {path.suffix}")
        identity = str(path)
        if identity not in seen:
            seen.add(identity)
            unique_paths.append(path)
    if not unique_paths:
        raise ValueError("没有找到可处理的图像")
    return unique_paths


def _source_snapshot(paths):
    return {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in paths}


def _assert_sources_unchanged(paths, before):
    if _source_snapshot(paths) != before:
        raise RuntimeError("处理过程中检测到源图文件状态发生变化")


def _load_config(config_path, preset, overrides):
    return pipeline.load_config(
        os.fspath(config_path), preset=preset, overrides=overrides
    )


def _clean_report(report):
    return {key: value for key, value in report.items() if not key.startswith("_")}


def diagnose_photos(
    input_source,
    *,
    preset=None,
    overrides=None,
    config_path=DEFAULT_CFG,
):
    """诊断一张或一批照片，不生成像素输出。"""
    paths = _collect(input_source)
    before = _source_snapshot(paths)
    config = _load_config(config_path, preset, overrides)
    reports = []
    for path in paths:
        started = time.monotonic()
        image, metadata = io_utils.load(os.fspath(path), config.get("raw"))
        report = pipeline.diagnose(image, metadata, config)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        reports.append(_clean_report(report))
    _assert_sources_unchanged(paths, before)
    return {"status": "analyzed", "reports": reports}


def build_repair_preview(
    input_path,
    output_dir,
    *,
    preset=None,
    overrides=None,
    auto=True,
    crop_size=420,
    config_path=DEFAULT_CFG,
):
    """生成中心、边缘和边角的修复前后对照，不覆盖既有输出。"""
    paths = _collect([input_path])
    source = paths[0]
    before = _source_snapshot(paths)
    output_directory = Path(output_dir).expanduser().resolve()
    preview_path = output_directory / f"{source.stem}_preview.png"
    if preview_path.exists():
        raise FileExistsError(f"拒绝覆盖既有修复预览: {preview_path}")
    if preview_path == source:
        raise ValueError("修复预览路径不得与源图相同")

    config = _load_config(config_path, preset, overrides)
    config["_auto_preview"] = bool(auto)
    output_path, report, used, geometry_log = repair_preview.build(
        os.fspath(source),
        config,
        os.fspath(preview_path),
        size=int(crop_size),
    )
    _assert_sources_unchanged(paths, before)
    return {
        "status": "review_required",
        "preview": output_path,
        "report": _clean_report(report),
        "parameters": {
            key: used[key]
            for key in ("hotpixel", "ca", "vignette", "denoise", "sharpen")
        },
        "geometry_log": geometry_log,
    }


def _expected_outputs(paths, output_dir, config):
    output_directory = Path(output_dir).expanduser().resolve()
    planned = []
    for source in paths:
        metadata = {"is_raw": source.suffix.lower() in io_utils.RAW_EXT}
        image_path = Path(
            io_utils.resolve_output_path(
                os.fspath(output_directory / f"{source.stem}_fixed"),
                metadata,
                config.get("output"),
            )
        )
        report_path = output_directory / f"{source.stem}_report.json"
        planned.append((source, image_path, report_path))
    destinations = [
        destination for _, image, report in planned for destination in (image, report)
    ]
    if len({str(path) for path in destinations}) != len(destinations):
        raise ValueError("多个输入会生成同名输出，请拆分目录或调整文件名")
    collisions = [path for path in destinations if path.exists()]
    if collisions:
        raise FileExistsError(f"拒绝覆盖既有修复输出: {collisions}")
    return planned


def repair_photos(
    input_source,
    output_dir,
    *,
    preset=None,
    overrides=None,
    auto=True,
    config_path=DEFAULT_CFG,
):
    """按诊断结果修复照片并生成报告，始终保留源图。"""
    paths = _collect(input_source)
    before = _source_snapshot(paths)
    config = _load_config(config_path, preset, overrides)
    planned = _expected_outputs(paths, output_dir, config)
    Path(output_dir).expanduser().resolve().mkdir(parents=True, exist_ok=True)

    reports = []
    for source, _, _ in planned:
        started = time.monotonic()
        report = pipeline.process_file(
            os.fspath(source),
            config,
            os.fspath(Path(output_dir).expanduser().resolve()),
            auto=auto,
        )
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        reports.append(_clean_report(report))

    _assert_sources_unchanged(paths, before)
    return {"status": "review_required", "reports": reports}


def build_lens_profile(
    flat_field_inputs,
    profile_store_path,
    *,
    preset=None,
    overrides=None,
    allow_update=False,
    config_path=DEFAULT_CFG,
):
    """从平场帧建立镜头暗角配置；更新既有配置必须显式允许。"""
    paths = _collect(flat_field_inputs)
    before = _source_snapshot(paths)
    store_path = Path(profile_store_path).expanduser().resolve()
    if store_path.exists() and not allow_update:
        raise FileExistsError(f"镜头配置已存在，显式允许更新后才能写入: {store_path}")
    config = _load_config(config_path, preset, overrides)
    results, saved_path = pipeline.calibrate(
        [os.fspath(path) for path in paths], config, store_path=os.fspath(store_path)
    )
    _assert_sources_unchanged(paths, before)
    return {
        "status": "review_required"
        if any(not item["ok"] for item in results)
        else "created",
        "profile_store": saved_path,
        "results": results,
    }
