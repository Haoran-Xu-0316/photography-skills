"""Inspect delivery readiness without making aesthetic photo edits."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageCms, ImageOps

VALID_TARGETS = {"web", "print", "archive"}
GPS_TAG = next(key for key, value in ExifTags.TAGS.items() if value == "GPSInfo")
ORIENTATION_TAG = next(
    key for key, value in ExifTags.TAGS.items() if value == "Orientation"
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _status(issues: list[dict[str, str]]) -> str:
    severities = {issue["severity"] for issue in issues}
    if "blocked" in severities:
        return "blocked"
    if "warning" in severities:
        return "warning"
    return "pass"


def _issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _profile_description(icc: bytes | None) -> str | None:
    if not icc:
        return None
    try:
        profile = ImageCms.ImageCmsProfile(BytesIO(icc))
        return ImageCms.getProfileDescription(profile).strip() or "embedded-profile"
    except (OSError, TypeError, ValueError):
        return "unreadable-profile"


def _bit_depth(mode: str) -> str:
    if mode.startswith("I;16"):
        return "16-bit"
    if mode in {"I", "F"}:
        return "high-bit-or-float"
    return "8-bit-per-channel-or-indexed"


def _has_transparency(image: Image.Image) -> bool:
    return "A" in image.getbands() or "transparency" in image.info


def _inspect_file(
    path: Path,
    target: str,
    print_width_cm: float | None,
    print_height_cm: float | None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = ImageOps.exif_transpose(image).size
            file_format = image.format or path.suffix.lstrip(".").upper()
            mode = image.mode
            has_alpha = _has_transparency(image)
            icc = image.info.get("icc_profile")
            exif = image.getexif()
            has_gps = bool(exif.get(GPS_TAG))
            dpi = image.info.get("dpi")
    except (OSError, ValueError) as error:
        issues.append(
            _issue("unreadable-image", "blocked", f"无法完整读取图像: {error}")
        )
        return {
            "path": str(path),
            "filename": path.name,
            "sha256": _hash(path),
            "status": "blocked",
            "issues": issues,
        }

    profile = _profile_description(icc)
    ppi = None
    if target == "web":
        long_edge = max(width, height)
        if long_edge < 1200:
            issues.append(_issue("web-resolution-low", "blocked", "长边低于1200像素。"))
        elif long_edge < 1600:
            issues.append(
                _issue("web-resolution-review", "warning", "长边低于建议的1600像素。")
            )
        if file_format.upper() not in {"JPEG", "PNG", "WEBP"}:
            issues.append(_issue("web-format", "warning", "格式并非常用网页交付格式。"))
        if path.stat().st_size > 10 * 1024 * 1024:
            issues.append(
                _issue("web-file-size", "warning", "文件大于10MB，可能影响网页加载。")
            )
        if profile is None:
            issues.append(
                _issue("icc-missing", "warning", "未嵌入ICC，不能确认网页色彩空间。")
            )
        elif "sRGB" not in profile:
            issues.append(
                _issue(
                    "web-profile-review",
                    "warning",
                    f"嵌入配置为{profile}，需转换至sRGB。",
                )
            )
        if has_gps:
            issues.append(
                _issue("gps-present", "warning", "EXIF包含GPS，公开发布前需确认隐私。")
            )
        if has_alpha:
            issues.append(
                _issue(
                    "web-transparency-review",
                    "warning",
                    "图像包含透明通道，需检查透明边缘和目标网页背景。",
                )
            )
    elif target == "print":
        if print_width_cm is None or print_height_cm is None:
            raise ValueError("print模式必须提供print_width_cm和print_height_cm")
        if print_width_cm <= 0 or print_height_cm <= 0:
            raise ValueError("印刷成品尺寸必须为正数")
        ppi = min(width / (print_width_cm / 2.54), height / (print_height_cm / 2.54))
        if ppi < 240:
            issues.append(
                _issue("print-ppi-low", "blocked", f"有效PPI仅{ppi:.1f}，低于240。")
            )
        elif ppi < 300:
            issues.append(
                _issue(
                    "print-ppi-review", "warning", f"有效PPI为{ppi:.1f}，低于300目标。"
                )
            )
        if profile is None:
            issues.append(
                _issue(
                    "icc-missing", "warning", "未嵌入ICC，无法完成可靠印刷色彩管理。"
                )
            )
        issues.append(
            _issue(
                "printer-profile-required",
                "warning",
                "尚未提供印厂目标ICC，不执行CMYK转换。",
            )
        )

    return {
        "path": str(path),
        "filename": path.name,
        "sha256": _hash(path),
        "file_size_bytes": path.stat().st_size,
        "format": file_format,
        "width": width,
        "height": height,
        "mode": mode,
        "bit_depth": _bit_depth(mode),
        "has_alpha": has_alpha,
        "icc_profile": profile,
        "has_gps": has_gps,
        "dpi_metadata": list(dpi) if isinstance(dpi, tuple) else dpi,
        "effective_ppi": round(ppi, 2) if ppi is not None else None,
        "status": _status(issues),
        "issues": issues,
    }


def inspect_delivery(
    input_paths: list[str | Path] | tuple[str | Path, ...],
    output_dir: str | Path,
    target: str = "web",
    print_width_cm: float | None = None,
    print_height_cm: float | None = None,
) -> dict[str, Any]:
    if target not in VALID_TARGETS:
        raise ValueError(f"不支持的目标: {target}")
    if not input_paths:
        raise ValueError("input_paths不能为空")
    sources = [Path(path).expanduser().resolve() for path in input_paths]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("找不到照片: " + ", ".join(missing))
    if len(set(sources)) != len(sources):
        raise ValueError("input_paths包含重复路径")
    records = [
        _inspect_file(path, target, print_width_cm, print_height_cm) for path in sources
    ]
    if target == "archive":
        by_filename: dict[str, list[dict[str, Any]]] = {}
        by_hash: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            by_filename.setdefault(record["filename"].casefold(), []).append(record)
            by_hash.setdefault(record["sha256"], []).append(record)
            if not Path(record["path"]).suffix:
                record["issues"].append(
                    _issue("extension-missing", "warning", "文件缺少扩展名。")
                )
        for matches in by_filename.values():
            if len(matches) > 1 and len({item["sha256"] for item in matches}) > 1:
                for record in matches:
                    record["issues"].append(
                        _issue(
                            "same-name-different-content",
                            "warning",
                            "发现同名但内容不同的文件。",
                        )
                    )
        for matches in by_hash.values():
            if len(matches) > 1:
                for record in matches:
                    record["issues"].append(
                        _issue(
                            "duplicate-content", "warning", "发现哈希相同的重复内容。"
                        )
                    )
        for record in records:
            record["status"] = _status(record["issues"])
    aggregate = "pass"
    if any(record["status"] == "blocked" for record in records):
        aggregate = "blocked"
    elif any(record["status"] == "warning" for record in records):
        aggregate = "warning"
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / f"delivery_{target}_report.json"
    if report_path.exists():
        raise FileExistsError(f"输出已存在，默认不覆盖: {report_path}")
    report = {
        "target": target,
        "status": aggregate,
        "print_size_cm": (
            {"width": print_width_cm, "height": print_height_cm}
            if target == "print"
            else None
        ),
        "files": records,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**report, "report": str(report_path)}


def _converted_rgb(image: Image.Image, icc: bytes | None) -> tuple[Image.Image, str]:
    rgb = image.convert("RGB")
    if not icc:
        return rgb, "missing-source-profile"
    try:
        source_profile = ImageCms.ImageCmsProfile(BytesIO(icc))
        destination_profile = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(
            rgb,
            source_profile,
            destination_profile,
            outputMode="RGB",
        )
        return converted, "converted-to-srgb"
    except (OSError, TypeError, ValueError):
        return rgb, "source-profile-unreadable"


def prepare_web_copies(
    input_paths: list[str | Path] | tuple[str | Path, ...],
    output_dir: str | Path,
    long_edge: int = 2400,
    remove_gps: bool = True,
) -> dict[str, Any]:
    if not input_paths:
        raise ValueError("input_paths不能为空")
    if long_edge < 320:
        raise ValueError("long_edge不得低于320像素")
    sources = [Path(path).expanduser().resolve() for path in input_paths]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("找不到照片: " + ", ".join(missing))
    if len(set(sources)) != len(sources):
        raise ValueError("input_paths包含重复路径")
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    report_path = directory / "web_export_report.json"
    planned: list[tuple[Path, Path]] = []
    for source in sources:
        with Image.open(source) as image:
            extension = ".png" if _has_transparency(image) else ".jpg"
        planned.append((source, directory / f"{source.stem}_web{extension}"))
    destinations = [destination for _, destination in planned]
    if len(set(destinations)) != len(destinations):
        raise ValueError("输入文件会生成同名网页副本，请先消除同名冲突")
    existing = [str(path) for _, path in planned if path.exists()]
    if report_path.exists():
        existing.append(str(report_path))
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))

    exports: list[dict[str, Any]] = []
    for source, destination in planned:
        original_hash = _hash(source)
        with Image.open(source) as image:
            icc = image.info.get("icc_profile")
            exif = image.getexif()
            oriented = ImageOps.exif_transpose(image)
            alpha = (
                oriented.convert("RGBA").getchannel("A")
                if _has_transparency(image)
                else None
            )
            converted, color_action = _converted_rgb(oriented, icc)
            if alpha is not None:
                converted.putalpha(alpha)
            if max(converted.size) > long_edge:
                scale = long_edge / max(converted.size)
                converted = converted.resize(
                    (round(converted.width * scale), round(converted.height * scale)),
                    Image.Resampling.LANCZOS,
                )
            if ORIENTATION_TAG in exif:
                del exif[ORIENTATION_TAG]
            gps_removed = False
            if remove_gps and GPS_TAG in exif:
                del exif[GPS_TAG]
                gps_removed = True
            options: dict[str, Any] = {}
            if destination.suffix == ".jpg":
                options.update(quality=95, subsampling=0, optimize=True)
                if exif:
                    options["exif"] = exif.tobytes()
            elif exif:
                options["exif"] = exif.tobytes()
            if color_action == "converted-to-srgb":
                options["icc_profile"] = ImageCms.ImageCmsProfile(
                    ImageCms.createProfile("sRGB")
                ).tobytes()
            converted.save(destination, **options)
        with Image.open(destination) as exported:
            export_size = ImageOps.exif_transpose(exported).size
            export_has_alpha = _has_transparency(exported)
        exports.append(
            {
                "input": str(source),
                "input_sha256": original_hash,
                "output": str(destination),
                "output_sha256": _hash(destination),
                "width": export_size[0],
                "height": export_size[1],
                "has_alpha": export_has_alpha,
                "color_action": color_action,
                "gps_removed": gps_removed,
                "original_preserved": _hash(source) == original_hash,
            }
        )
    status = (
        "pass" if all(item["original_preserved"] for item in exports) else "blocked"
    )
    report = {
        "status": status,
        "long_edge": long_edge,
        "remove_gps": remove_gps,
        "exports": exports,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**report, "report": str(report_path)}
