"""Public programmatic API for deterministic photo color grading."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .color_engine import (
        RAW_EXTENSIONS,
        ImageData,
        analyze_rgb,
        apply_creative_look,
        apply_reference_match,
        apply_technical,
        build_technical_plan,
        load_image,
        save_image,
    )
    from .preview_validate import make_contact_sheet, validate_arrays
except ImportError:
    from color_engine import (
        RAW_EXTENSIONS,
        ImageData,
        analyze_rgb,
        apply_creative_look,
        apply_reference_match,
        apply_technical,
        build_technical_plan,
        load_image,
        save_image,
    )
    from preview_validate import make_contact_sheet, validate_arrays


SKILL_ROOT = Path(__file__).resolve().parents[1]
LOOK_TARGETS_PATH = SKILL_ROOT / "assets" / "look-targets.json"
VALID_MODES = {"correct", "look", "match"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise FileExistsError(f"报告已存在，默认不覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _preflight_outputs(paths: Iterable[Path]) -> None:
    destinations = [Path(path).expanduser().resolve() for path in paths]
    if len({str(path) for path in destinations}) != len(destinations):
        raise ValueError("多个输入会生成同名输出，请拆分目录或调整文件名")
    collisions = [path for path in destinations if path.exists()]
    if collisions:
        raise FileExistsError(f"输出已存在，默认不覆盖: {collisions}")


def _load_looks() -> dict[str, dict[str, Any]]:
    return json.loads(LOOK_TARGETS_PATH.read_text(encoding="utf-8"))


def available_looks() -> dict[str, str]:
    return {name: values["description"] for name, values in _load_looks().items()}


def analyze_photo(input_path: str | Path) -> dict[str, Any]:
    image = load_image(input_path)
    analysis = analyze_rgb(image.rgb)
    return {
        "file": str(image.path),
        "sha256": _sha256(image.path),
        "width": int(image.rgb.shape[1]),
        "height": int(image.rgb.shape[0]),
        "bit_depth": image.bit_depth,
        "source_dtype": image.source_dtype,
        "source_format": image.source_format,
        "icc_profile_present": image.icc_profile is not None,
        "exif_present": image.exif is not None,
        "orientation_normalized": image.orientation_normalized,
        "analysis": analysis,
    }


def _validate_request(
    mode: str, look: str, reference_path: str | Path | None
) -> dict[str, Any] | None:
    if mode not in VALID_MODES:
        raise ValueError(f"不支持的模式: {mode}。可用模式为{sorted(VALID_MODES)}")
    looks = _load_looks()
    if look not in looks:
        raise ValueError(f"不支持的look: {look}。可用look为{sorted(looks)}")
    if mode == "match" and reference_path is None:
        raise ValueError("match模式必须提供reference_path")
    return looks.get(look)


def _process_array(
    image: ImageData,
    mode: str,
    look: str,
    strength: float,
    reference: ImageData | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    if not 0.0 <= strength <= 1.5:
        raise ValueError("strength必须在0.0至1.5之间")
    look_values = _validate_request(mode, look, reference.path if reference else None)
    source_analysis = analyze_rgb(image.rgb)
    technical_plan = build_technical_plan(
        source_analysis, strength=1.0 if mode != "correct" else strength
    )
    result = apply_technical(image.rgb, technical_plan)

    creative_parameters = None
    reference_parameters = None
    if mode == "look":
        creative_parameters = {
            "name": look,
            "strength": strength,
            **(look_values or {}),
        }
        result = apply_creative_look(result, look_values or {}, strength=strength)
    elif mode == "match":
        if reference is None:
            raise ValueError("match模式缺少参考图")
        match_strength = min(strength * 0.70, 1.0)
        result = apply_reference_match(result, reference.rgb, strength=match_strength)
        reference_parameters = {
            "file": str(reference.path),
            "sha256": _sha256(reference.path),
            "strength": match_strength,
        }

    recipe = {
        "mode": mode,
        "technical": technical_plan,
        "creative": creative_parameters,
        "reference": reference_parameters,
    }
    return np.clip(result, 0.0, 1.0), recipe


def _output_suffix(image: ImageData) -> str:
    suffix = image.path.suffix.lower()
    if suffix in RAW_EXTENSIONS or image.bit_depth > 8:
        return ".tif"
    if suffix in {".jpg", ".jpeg"}:
        return ".jpg"
    if suffix == ".png":
        return ".png"
    return ".tif"


def _safe_token(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "result"


def _result_paths(
    image: ImageData, output_dir: str | Path, label: str
) -> dict[str, Path]:
    directory = Path(output_dir).expanduser().resolve()
    stem = image.path.stem
    base_name = f"{stem}_{_safe_token(label)}"
    return {
        "image": directory / f"{base_name}{_output_suffix(image)}",
        "recipe": directory / f"{base_name}.recipe.json",
        "validation": directory / f"{base_name}.validation.json",
    }


def build_preview(
    input_path: str | Path,
    output_dir: str | Path,
    mode: str = "look",
    look: str = "natural-clean",
    reference_path: str | Path | None = None,
) -> dict[str, Any]:
    image = load_image(input_path)
    reference = load_image(reference_path) if reference_path is not None else None
    _validate_request(mode, look, reference_path)

    technical_plan = build_technical_plan(analyze_rgb(image.rgb), strength=1.0)
    corrected = apply_technical(image.rgb, technical_plan)
    variants: dict[str, np.ndarray] = {"ORIGINAL": image.rgb}
    if mode != "correct":
        variants["TECHNICAL"] = corrected

    for label, preview_strength in (
        ("TARGET 70%", 0.70),
        ("TARGET 100%", 1.00),
        ("TARGET 130%", 1.30),
    ):
        if mode == "correct":
            plan = build_technical_plan(
                analyze_rgb(image.rgb), strength=preview_strength
            )
            variants[label] = apply_technical(image.rgb, plan)
        elif mode == "look":
            variants[label] = apply_creative_look(
                corrected,
                _load_looks()[look],
                strength=preview_strength,
            )
        else:
            if reference is None:
                raise ValueError("match模式缺少参考图")
            variants[label] = apply_reference_match(
                corrected,
                reference.rgb,
                strength=min(preview_strength * 0.70, 1.0),
            )

    directory = Path(output_dir).expanduser().resolve()
    preview_path = directory / f"{image.path.stem}_{_safe_token(mode)}_preview.jpg"
    report_path = directory / f"{image.path.stem}_{_safe_token(mode)}_preview.json"
    _preflight_outputs((preview_path, report_path))
    make_contact_sheet(variants, preview_path)
    report = {
        "input": str(image.path),
        "input_sha256": _sha256(image.path),
        "mode": mode,
        "look": look if mode == "look" else None,
        "reference": str(reference.path) if reference else None,
        "preview": str(preview_path),
        "strengths": [0.70, 1.00, 1.30],
        "technical": technical_plan,
    }
    _write_json(report_path, report)
    return {**report, "report": str(report_path)}


def grade_photo(
    input_path: str | Path,
    output_dir: str | Path,
    mode: str = "correct",
    look: str = "natural-clean",
    strength: float = 1.0,
    reference_path: str | Path | None = None,
) -> dict[str, Any]:
    image = load_image(input_path)
    reference = load_image(reference_path) if reference_path is not None else None
    result, recipe = _process_array(image, mode, look, strength, reference)
    label = (
        "corrected"
        if mode == "correct"
        else f"graded-{look}"
        if mode == "look"
        else "matched"
    )
    paths = _result_paths(image, output_dir, label)
    _preflight_outputs(paths.values())

    save_image(image, result, paths["image"])
    rendered = load_image(paths["image"])
    validation = validate_arrays(image.rgb, rendered.rgb)
    validation.update(
        {
            "input": str(image.path),
            "input_sha256": _sha256(image.path),
            "output": str(paths["image"]),
            "output_sha256": _sha256(paths["image"]),
            "dimensions_preserved": image.rgb.shape == rendered.rgb.shape,
            "icc_profile_preserved": bool(image.icc_profile)
            == bool(rendered.icc_profile),
        }
    )
    recipe_payload = {
        "input": str(image.path),
        "input_sha256": _sha256(image.path),
        "output": str(paths["image"]),
        "engine": "deterministic-numpy-opencv",
        "recipe": recipe,
    }
    _write_json(paths["recipe"], recipe_payload)
    _write_json(paths["validation"], validation)
    public_status = (
        "review_required" if validation["status"] == "pass" else "blocked"
    )
    return {
        "status": public_status,
        "technical_status": validation["status"],
        "output": str(paths["image"]),
        "recipe": str(paths["recipe"]),
        "validation": str(paths["validation"]),
        "warnings": validation["warnings"],
        "blocking": validation["blocking"],
    }


def grade_series(
    input_paths: Iterable[str | Path],
    output_dir: str | Path,
    anchor_path: str | Path,
    look: str = "natural-clean",
    strength: float = 1.0,
    match_strength: float = 0.35,
) -> dict[str, Any]:
    paths = [Path(path).expanduser().resolve() for path in input_paths]
    if not paths:
        raise ValueError("系列模式至少需要一张照片")
    if not 0.0 <= match_strength <= 0.7:
        raise ValueError("match_strength必须在0.0至0.7之间")
    looks = _load_looks()
    if look not in looks:
        raise ValueError(f"不支持的look: {look}")

    anchor = load_image(anchor_path)
    images = [load_image(path) for path in paths]
    planned = [
        (image, _result_paths(image, output_dir, f"series-{look}"))
        for image in images
    ]
    _preflight_outputs(
        output_path
        for _, output_paths in planned
        for output_path in output_paths.values()
    )
    anchor_plan = build_technical_plan(analyze_rgb(anchor.rgb), strength=1.0)
    anchor_target = apply_technical(anchor.rgb, anchor_plan)
    anchor_target = apply_creative_look(anchor_target, looks[look], strength=strength)

    results: list[dict[str, Any]] = []
    for image, output_paths in planned:
        try:
            technical_plan = build_technical_plan(analyze_rgb(image.rgb), strength=1.0)
            result = apply_technical(image.rgb, technical_plan)
            result = apply_creative_look(result, looks[look], strength=strength)
            if image.path != anchor.path:
                result = apply_reference_match(
                    result, anchor_target, strength=match_strength
                )

            save_image(image, result, output_paths["image"])
            rendered = load_image(output_paths["image"])
            validation = validate_arrays(image.rgb, rendered.rgb)
            validation.update(
                {
                    "input": str(image.path),
                    "input_sha256": _sha256(image.path),
                    "output": str(output_paths["image"]),
                    "output_sha256": _sha256(output_paths["image"]),
                    "anchor": str(anchor.path),
                    "anchor_sha256": _sha256(anchor.path),
                }
            )
            recipe = {
                "input": str(image.path),
                "input_sha256": _sha256(image.path),
                "output": str(output_paths["image"]),
                "engine": "deterministic-numpy-opencv",
                "recipe": {
                    "mode": "series",
                    "technical": technical_plan,
                    "creative": {"name": look, "strength": strength, **looks[look]},
                    "anchor": str(anchor.path),
                    "match_strength": 0.0
                    if image.path == anchor.path
                    else match_strength,
                },
            }
            _write_json(output_paths["recipe"], recipe)
            _write_json(output_paths["validation"], validation)
            results.append(
                {
                    "input": str(image.path),
                    "status": "review_required"
                    if validation["status"] == "pass"
                    else "blocked",
                    "technical_status": validation["status"],
                    "output": str(output_paths["image"]),
                    "recipe": str(output_paths["recipe"]),
                    "validation": str(output_paths["validation"]),
                    "warnings": validation["warnings"],
                    "blocking": validation["blocking"],
                }
            )
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(
                {"input": str(image.path), "status": "error", "error": str(exc)}
            )

    return {
        "status": "review_required"
        if all(item.get("technical_status") == "pass" for item in results)
        else "blocked",
        "anchor": str(anchor.path),
        "look": look,
        "strength": strength,
        "match_strength": match_strength,
        "results": results,
    }
