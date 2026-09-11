"""Deterministic alignment and exposure fusion for real bracketed photographs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import ExifTags, Image, ImageDraw, ImageOps

MIN_BRACKET_EV = 0.5
MAX_SHIFT_SHARE = 0.10
MIN_VIEW_CONFIDENCE = 0.45
MOTION_MEDIUM_SHARE = 0.005
MOTION_HIGH_SHARE = 0.03


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        oriented = ImageOps.exif_transpose(image)
        return np.asarray(oriented.convert("RGB"), dtype=np.uint8)


def _read_exposure_time(path: Path) -> float | None:
    exposure_tag = next(
        (tag for tag, name in ExifTags.TAGS.items() if name == "ExposureTime"),
        None,
    )
    if exposure_tag is None:
        return None
    try:
        with Image.open(path) as image:
            value = image.getexif().get(exposure_tag)
        if value is None:
            return None
        exposure = float(value)
        return exposure if exposure > 0 else None
    except (OSError, TypeError, ValueError, ZeroDivisionError):
        return None


def _validate_paths(input_paths: Sequence[str | Path]) -> list[Path]:
    paths = [Path(item).expanduser().resolve() for item in input_paths]
    if len(paths) < 2:
        raise ValueError("Exposure fusion requires at least two input photographs.")
    if len(set(paths)) != len(paths):
        raise ValueError("Each input path must be unique.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Input photographs not found: {missing}")
    return paths


def _resolve_exposure_times(
    paths: Sequence[Path],
    exposure_times: Sequence[float] | None,
) -> tuple[list[float | None], str]:
    if exposure_times is not None:
        values = [float(value) for value in exposure_times]
        if len(values) != len(paths):
            raise ValueError("exposure_times must match the number of input paths.")
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("Every exposure time must be finite and positive.")
        return values, "provided"

    values = [_read_exposure_time(path) for path in paths]
    if all(value is not None for value in values):
        return values, "exif"
    return values, "unverified"


def _gray(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def _robust_normalize(gray: np.ndarray) -> np.ndarray:
    values = gray.astype(np.float32) / 255.0
    low, high = np.percentile(values, (2.0, 98.0))
    if high - low < 1e-4:
        return np.zeros_like(values)
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    return normalized.astype(np.float32, copy=False)


def _correlation(left: np.ndarray, right: np.ndarray, mask: np.ndarray) -> float:
    left_values = left[mask].astype(np.float64)
    right_values = right[mask].astype(np.float64)
    if left_values.size < 256:
        return 0.0
    left_values -= left_values.mean()
    right_values -= right_values.mean()
    denominator = float(np.linalg.norm(left_values) * np.linalg.norm(right_values))
    if denominator < 1e-12:
        return 0.0
    return float(np.dot(left_values, right_values) / denominator)


def _view_confidence(reference: np.ndarray, candidate: np.ndarray, valid: np.ndarray) -> float:
    ref_norm = _robust_normalize(_gray(reference))
    candidate_norm = _robust_normalize(_gray(candidate))
    intensity = _correlation(ref_norm, candidate_norm, valid)

    ref_x = cv2.Sobel(ref_norm, cv2.CV_32F, 1, 0, ksize=3)
    ref_y = cv2.Sobel(ref_norm, cv2.CV_32F, 0, 1, ksize=3)
    cand_x = cv2.Sobel(candidate_norm, cv2.CV_32F, 1, 0, ksize=3)
    cand_y = cv2.Sobel(candidate_norm, cv2.CV_32F, 0, 1, ksize=3)
    ref_edge = cv2.magnitude(ref_x, ref_y)
    candidate_edge = cv2.magnitude(cand_x, cand_y)
    edge = _correlation(ref_edge, candidate_edge, valid)
    return float(np.clip(max(intensity, edge), 0.0, 1.0))


def _choose_reference_index(
    images: Sequence[np.ndarray],
    exposure_times: Sequence[float | None],
    exposure_source: str,
) -> int:
    if exposure_source in {"provided", "exif"}:
        values = np.asarray(exposure_times, dtype=np.float64)
        target = float(np.median(np.log2(values)))
        return int(np.argmin(np.abs(np.log2(values) - target)))
    medians = np.asarray([np.median(_gray(image)) for image in images])
    return int(np.argsort(medians)[len(medians) // 2])


def _translate(
    image: np.ndarray, shift: tuple[int, int]
) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    matrix = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
    shifted = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    valid = cv2.warpAffine(
        np.full((height, width), 255, dtype=np.uint8),
        matrix,
        (width, height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
    )
    return shifted, valid > 0


def _align_images(
    images: Sequence[np.ndarray], reference_index: int
) -> tuple[list[np.ndarray], list[tuple[int, int]], list[np.ndarray], list[float]]:
    aligner = cv2.createAlignMTB(max_bits=6, exclude_range=4, cut=False)
    reference_gray = np.round(
        _robust_normalize(_gray(images[reference_index])) * 255.0
    ).astype(np.uint8)
    height, width = images[reference_index].shape[:2]
    aligned: list[np.ndarray] = []
    shifts: list[tuple[int, int]] = []
    validity: list[np.ndarray] = []
    confidence: list[float] = []

    for index, image in enumerate(images):
        image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        if index == reference_index:
            shift = (0, 0)
            aligned_rgb = image.copy()
            valid = np.ones((height, width), dtype=bool)
        else:
            candidate_gray = np.round(
                _robust_normalize(_gray(image)) * 255.0
            ).astype(np.uint8)
            calculated = aligner.calculateShift(reference_gray, candidate_gray)
            mtb_shift = (int(calculated[0]), int(calculated[1]))
            mtb_bgr = aligner.shiftMat(image_bgr, mtb_shift)
            mtb_rgb = cv2.cvtColor(mtb_bgr, cv2.COLOR_BGR2RGB)
            mtb_valid_image = aligner.shiftMat(
                np.full((height, width), 255, np.uint8), mtb_shift
            )
            mtb_valid = mtb_valid_image > 0

            reference_phase = _robust_normalize(reference_gray)
            candidate_phase = _robust_normalize(candidate_gray)
            phase_shift, _ = cv2.phaseCorrelate(reference_phase, candidate_phase)
            phase_candidate = (
                round(-phase_shift[0]),
                round(-phase_shift[1]),
            )
            phase_rgb, phase_valid = _translate(image, phase_candidate)
            zero_rgb, zero_valid = _translate(image, (0, 0))
            candidates = [
                (mtb_shift, mtb_rgb, mtb_valid),
                (phase_candidate, phase_rgb, phase_valid),
                ((0, 0), zero_rgb, zero_valid),
            ]
            shift, aligned_rgb, valid = max(
                candidates,
                key=lambda item: _view_confidence(
                    images[reference_index], item[1], item[2]
                ),
            )
        aligned.append(aligned_rgb)
        shifts.append(shift)
        validity.append(valid)
        confidence.append(_view_confidence(images[reference_index], aligned_rgb, valid))
    return aligned, shifts, validity, confidence


def _estimated_ev_span(
    images: Sequence[np.ndarray],
    exposure_times: Sequence[float | None],
    exposure_source: str,
) -> float:
    if exposure_source in {"provided", "exif"}:
        values = np.asarray(exposure_times, dtype=np.float64)
        return float(np.log2(values.max() / values.min()))
    medians = np.asarray([max(float(np.median(_gray(image))), 1.0) for image in images])
    return float(np.log2(medians.max() / medians.min()))


def _motion_mask(
    aligned: Sequence[np.ndarray], validity: Sequence[np.ndarray]
) -> tuple[np.ndarray, float]:
    # Match global monotonic exposure responses before testing local changes.
    # This is display-space compensation, not radiometric HDR calibration.
    reference = aligned[len(aligned) // 2].astype(np.uint8)
    valid = np.logical_and.reduce(validity).astype(bool)
    residual = np.zeros(reference.shape[:2], dtype=np.float32)
    quantiles = np.linspace(2, 98, 97)
    valid_count = int(np.count_nonzero(valid))
    for frame in aligned:
        for channel in range(3):
            source = frame[..., channel]
            target = reference[..., channel]
            x, y = np.array([]), np.array([])
            if valid_count >= 96:
                source_quantiles = np.percentile(source[valid], quantiles)
                target_quantiles = np.percentile(target[valid], quantiles)
                usable = (
                    (source_quantiles > 4) & (source_quantiles < 251)
                    & (target_quantiles > 4) & (target_quantiles < 251)
                )
                x, indices = np.unique(source_quantiles[usable], return_index=True)
                y = target_quantiles[usable][indices]
            if len(x) < 4:
                # An unconstrained curve must not erase observed differences.
                difference = np.abs(source.astype(np.float32) - target) / 255
            else:
                mapped = np.interp(source, x, np.maximum.accumulate(y))
                difference = np.abs(mapped - target) / 255
                low_tail = (source <= x[0]) & (target <= y[0] + 8)
                high_tail = (source >= x[-1]) & (target >= y[-1] - 8)
                difference[low_tail | high_tail] = 0
            residual = np.maximum(residual, difference)
    mask = ((residual > 0.12) & valid).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask[~valid] = 0
    motion_share = float(np.count_nonzero(mask) / max(valid_count, 1))
    return mask, motion_share


def _risk_level(motion_share: float) -> str:
    if motion_share <= MOTION_MEDIUM_SHARE:
        return "low"
    if motion_share <= MOTION_HIGH_SHARE:
        return "medium"
    return "high"


def analyze_bracket(
    input_paths: Sequence[str | Path],
    exposure_times: Sequence[float] | None = None,
) -> dict:
    """Validate a bracket and estimate alignment and motion risk without writing files."""

    paths = _validate_paths(input_paths)
    images = [_load_rgb(path) for path in paths]
    times, exposure_source = _resolve_exposure_times(paths, exposure_times)
    hashes = [_sha256(path) for path in paths]
    pixel_hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
    dimensions = [(int(image.shape[1]), int(image.shape[0])) for image in images]
    blockers: list[str] = []
    warnings: list[str] = []

    if len(set(hashes)) != len(hashes) or len(set(pixel_hashes)) != len(pixel_hashes):
        blockers.append("duplicate_content")
    if len(set(dimensions)) != 1:
        blockers.append("dimension_mismatch")
        return {
            "status": "blocked",
            "blockers": blockers,
            "warnings": warnings,
            "inputs": [
                {"path": str(path), "sha256": digest, "dimensions": list(size)}
                for path, digest, size in zip(paths, hashes, dimensions, strict=True)
            ],
            "exposure_times_seconds": times,
            "exposure_source": exposure_source,
        }

    reference_index = _choose_reference_index(images, times, exposure_source)
    aligned, shifts, validity, confidence = _align_images(images, reference_index)
    ev_span = _estimated_ev_span(images, times, exposure_source)
    mask, motion_share = _motion_mask(aligned, validity)
    del mask

    short_edge = min(dimensions[0])
    if ev_span < MIN_BRACKET_EV:
        blockers.append("insufficient_exposure_span")
    if max(max(abs(x), abs(y)) for x, y in shifts) > short_edge * MAX_SHIFT_SHARE:
        blockers.append("alignment_shift_too_large")
    if min(confidence) < MIN_VIEW_CONFIDENCE:
        blockers.append("same_view_confidence_too_low")
    if exposure_source == "unverified":
        warnings.append("exposure_times_unverified")
    risk = _risk_level(motion_share)
    if risk != "low":
        warnings.append(f"ghost_risk_{risk}")

    status = "blocked" if blockers else ("review_required" if risk != "low" else "pass")
    return {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "inputs": [
            {
                "path": str(path),
                "sha256": digest,
                "dimensions": list(size),
                "median_luminance_8bit": float(np.median(_gray(image))),
            }
            for path, digest, size, image in zip(
                paths, hashes, dimensions, images, strict=True
            )
        ],
        "exposure_times_seconds": times,
        "exposure_source": exposure_source,
        "exposure_span_ev": ev_span,
        "reference_index": reference_index,
        "alignment_shifts_xy": [list(shift) for shift in shifts],
        "same_view_confidence": confidence,
        "ghost_risk": {
            "level": risk,
            "affected_share": motion_share,
        },
    }


def _ensure_absent(paths: Sequence[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite existing outputs: {existing}")


def _suppress_motion_with_reference(
    fused: np.ndarray,
    reference: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    reference_float = reference.astype(np.float32) / 255.0
    fused_luma = cv2.cvtColor(fused, cv2.COLOR_RGB2GRAY)
    reference_luma = cv2.cvtColor(reference_float, cv2.COLOR_RGB2GRAY)
    static = mask == 0
    usable = np.logical_and(static, reference_luma > 0.03)
    if usable.any():
        scale = float(np.median(fused_luma[usable]) / np.median(reference_luma[usable]))
    else:
        scale = 1.0
    reference_float = np.clip(reference_float * np.clip(scale, 0.5, 2.0), 0.0, 1.0)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 1.5)
    return fused * (1.0 - alpha[..., None]) + reference_float * alpha[..., None]


def _save_contact_sheet(
    aligned: Sequence[np.ndarray],
    shifts: Sequence[tuple[int, int]],
    output_path: Path,
) -> None:
    thumb_width = 320
    thumbs: list[Image.Image] = []
    for index, (image, shift) in enumerate(zip(aligned, shifts, strict=True)):
        pil_image = Image.fromarray(image)
        thumb_height = max(1, round(pil_image.height * thumb_width / pil_image.width))
        thumb = pil_image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (thumb_width, thumb_height + 28), "white")
        frame.paste(thumb, (0, 28))
        ImageDraw.Draw(frame).text(
            (8, 7),
            f"Frame {index + 1}  shift=({shift[0]}, {shift[1]})",
            fill="black",
        )
        thumbs.append(frame)
    sheet = Image.new(
        "RGB",
        (thumb_width * len(thumbs), max(thumb.height for thumb in thumbs)),
        "white",
    )
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, (index * thumb_width, 0))
    sheet.save(output_path, quality=92)


def fuse_bracket(
    input_paths: Sequence[str | Path],
    output_dir: str | Path,
    exposure_times: Sequence[float] | None = None,
    motion_handling: str = "reference-frame",
) -> dict:
    """Align and fuse a valid exposure bracket into a display-referred image."""

    if motion_handling not in {"reference-frame", "report-only"}:
        raise ValueError("motion_handling must be 'reference-frame' or 'report-only'.")
    paths = _validate_paths(input_paths)
    analysis = analyze_bracket(paths, exposure_times=exposure_times)
    if analysis["blockers"]:
        raise ValueError(f"Bracket validation blocked fusion: {analysis['blockers']}")

    images = [_load_rgb(path) for path in paths]
    reference_index = int(analysis["reference_index"])
    aligned, shifts, validity, _ = _align_images(images, reference_index)
    motion_mask, motion_share = _motion_mask(aligned, validity)

    merge = cv2.createMergeMertens(
        contrast_weight=1.0,
        saturation_weight=1.0,
        exposure_weight=1.0,
    )
    aligned_bgr = [cv2.cvtColor(image, cv2.COLOR_RGB2BGR) for image in aligned]
    fused_bgr = np.clip(merge.process(aligned_bgr), 0.0, 1.0)
    fused = cv2.cvtColor(fused_bgr, cv2.COLOR_BGR2RGB)
    if motion_handling == "reference-frame" and motion_mask.any():
        fused = _suppress_motion_with_reference(
            fused,
            aligned[reference_index],
            motion_mask,
        )
    fused = np.clip(fused, 0.0, 1.0)

    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    tiff_path = destination / "exposure_fused_16bit.tif"
    preview_path = destination / "exposure_fused_preview.jpg"
    mask_path = destination / "ghost_risk_mask.png"
    contact_path = destination / "alignment_contact_sheet.jpg"
    report_path = destination / "bracket_fusion_report.json"
    output_paths = [tiff_path, preview_path, mask_path, contact_path, report_path]
    _ensure_absent(output_paths)

    fused_16 = np.round(fused * 65535.0).astype(np.uint16)
    fused_8 = np.round(fused * 255.0).astype(np.uint8)
    if not cv2.imwrite(str(tiff_path), cv2.cvtColor(fused_16, cv2.COLOR_RGB2BGR)):
        raise OSError(f"Could not write {tiff_path}")
    if not cv2.imwrite(
        str(preview_path),
        cv2.cvtColor(fused_8, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 95],
    ):
        raise OSError(f"Could not write {preview_path}")
    if not cv2.imwrite(str(mask_path), motion_mask):
        raise OSError(f"Could not write {mask_path}")
    _save_contact_sheet(aligned, shifts, contact_path)

    after_hashes = [_sha256(path) for path in paths]
    if after_hashes != [item["sha256"] for item in analysis["inputs"]]:
        raise RuntimeError("An exposure-bracket source file changed during processing.")

    risk = _risk_level(motion_share)
    report = {
        **analysis,
        "status": "review_required" if risk != "low" else "pass",
        "ghost_risk": {"level": risk, "affected_share": motion_share},
        "recipe": {
            "alignment": "OpenCV MTB and phase-correlation integer translation selection",
            "fusion": "OpenCV MergeMertens display-referred exposure fusion",
            "fusion_weights": {
                "contrast": 1.0,
                "saturation": 1.0,
                "exposure": 1.0,
            },
            "motion_detection": "per-channel monotonic quantile compensation; residual threshold 0.12",
            "motion_handling": motion_handling,
            "claim_boundary": "not scene-linear HDR or a radiance map",
        },
        "outputs": {},
        "source_hashes_verified_after_processing": True,
    }
    for path in [tiff_path, preview_path, mask_path, contact_path]:
        report["outputs"][path.name] = {
            "path": str(path),
            "sha256": _sha256(path),
        }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report["outputs"][report_path.name] = {
        "path": str(report_path),
        "sha256": _sha256(report_path),
    }
    return report
