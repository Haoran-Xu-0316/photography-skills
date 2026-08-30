"""Rigid alignment and source-constrained focus stacking for real photographs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

MIN_ALIGNMENT_CONFIDENCE = 0.45
BREATHING_REVIEW_SHARE = 0.015
BREATHING_BLOCK_SHARE = 0.05
EXPOSURE_REVIEW_EV = 0.5
MOTION_MEDIUM_SHARE = 0.005
MOTION_HIGH_SHARE = 0.03
LOW_CONFIDENCE_REVIEW_SHARE = 0.35

OUTPUT_NAMES = (
    "focus_stacked_16bit.tif",
    "focus_stacked_preview.jpg",
    "focus_source_map.png",
    "focus_confidence.png",
    "motion_or_breathing_risk_mask.png",
    "alignment_contact_sheet.jpg",
    "focus_stack_report.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_paths(input_paths: Sequence[str | Path]) -> list[Path]:
    paths = [Path(item).expanduser().resolve() for item in input_paths]
    if len(paths) < 2:
        raise ValueError("Focus stacking requires at least two input photographs.")
    if len(set(paths)) != len(paths):
        raise ValueError("Each input path must be unique.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Input photographs not found: {missing}")
    return paths


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        oriented = ImageOps.exif_transpose(image)
        return np.asarray(oriented.convert("RGB"), dtype=np.uint8)


def _gray_float(rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0


def _normalize_for_alignment(gray: np.ndarray) -> np.ndarray:
    low, high = np.percentile(gray, (2.0, 98.0))
    if high - low < 1e-4:
        return np.zeros_like(gray, dtype=np.float32)
    return np.clip((gray - low) / (high - low), 0.0, 1.0).astype(np.float32)


def _reference_index(count: int, requested: int | None) -> int:
    if requested is None:
        return count // 2
    index = int(requested)
    if index < 0 or index >= count:
        raise ValueError("reference_index is outside the input sequence.")
    return index


def _warp_rigid(
    image: np.ndarray,
    matrix: np.ndarray,
    size: tuple[int, int],
    interpolation: int,
) -> np.ndarray:
    return cv2.warpAffine(
        image,
        matrix,
        size,
        flags=interpolation | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
    )


def _align_rigid(
    images: Sequence[np.ndarray], reference_index: int
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], list[float]]:
    height, width = images[reference_index].shape[:2]
    reference = _normalize_for_alignment(_gray_float(images[reference_index]))
    aligned: list[np.ndarray] = []
    matrices: list[np.ndarray] = []
    valid_masks: list[np.ndarray] = []
    confidences: list[float] = []

    for index, image in enumerate(images):
        if index == reference_index:
            matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.float32)
            confidence = 1.0
        else:
            candidate = _normalize_for_alignment(_gray_float(image))
            matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], np.float32)
            try:
                confidence, matrix = cv2.findTransformECC(
                    reference,
                    candidate,
                    matrix,
                    cv2.MOTION_EUCLIDEAN,
                    (
                        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                        120,
                        1e-6,
                    ),
                    None,
                    5,
                )
            except cv2.error:
                confidence = 0.0

        warped = _warp_rigid(image, matrix, (width, height), cv2.INTER_LINEAR)
        validity = _warp_rigid(
            np.full((height, width), 255, np.uint8),
            matrix,
            (width, height),
            cv2.INTER_NEAREST,
        )
        aligned.append(warped)
        matrices.append(matrix.copy())
        valid_masks.append(validity > 0)
        confidences.append(float(np.clip(confidence, 0.0, 1.0)))
    return aligned, matrices, valid_masks, confidences


def _estimate_breathing_share(reference: np.ndarray, candidate: np.ndarray) -> float | None:
    detector = cv2.ORB_create(nfeatures=2000, fastThreshold=8)
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY)
    cand_gray = cv2.cvtColor(candidate, cv2.COLOR_RGB2GRAY)
    ref_points, ref_desc = detector.detectAndCompute(ref_gray, None)
    cand_points, cand_desc = detector.detectAndCompute(cand_gray, None)
    if ref_desc is None or cand_desc is None or len(ref_points) < 12 or len(cand_points) < 12:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(cand_desc, ref_desc, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance]
    if len(good) < 10:
        return None
    source = np.float32([cand_points[item.queryIdx].pt for item in good])
    target = np.float32([ref_points[item.trainIdx].pt for item in good])
    matrix, inliers = cv2.estimateAffinePartial2D(
        source,
        target,
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
        maxIters=3000,
        confidence=0.99,
    )
    if matrix is None or inliers is None or int(inliers.sum()) < 8:
        return None
    scale = math.hypot(float(matrix[0, 0]), float(matrix[0, 1]))
    return abs(scale - 1.0)


def _exposure_span_ev(images: Sequence[np.ndarray]) -> float:
    medians = [max(float(np.median(_gray_float(image))), 1.0 / 255.0) for image in images]
    return float(math.log2(max(medians) / min(medians)))


def _focus_energy(rgb: np.ndarray) -> np.ndarray:
    gray = _gray_float(rgb)
    energies: list[np.ndarray] = []
    for sigma in (0.7, 1.4, 2.8):
        smooth = cv2.GaussianBlur(gray, (0, 0), sigma)
        laplacian = cv2.Laplacian(smooth, cv2.CV_32F, ksize=3)
        energy = cv2.GaussianBlur(laplacian * laplacian, (0, 0), sigma * 1.5)
        energies.append(energy)
    combined = energies[0] + 0.7 * energies[1] + 0.4 * energies[2]
    return np.maximum(combined, 1e-10)


def _focus_metrics(
    aligned: Sequence[np.ndarray], valid_masks: Sequence[np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, list[float]]:
    energy = np.stack([_focus_energy(image) for image in aligned])
    valid = np.stack(valid_masks)
    energy = np.where(valid, energy, -1.0)
    source_map = np.argmax(energy, axis=0).astype(np.uint16)

    sorted_energy = np.sort(np.maximum(energy, 0.0), axis=0)
    best = sorted_energy[-1]
    second = sorted_energy[-2]
    confidence = np.clip((best - second) / (best + second + 1e-8), 0.0, 1.0)
    textured = best > np.percentile(best, 35.0)
    low_confidence = np.logical_and(confidence < 0.12, textured)
    low_confidence_share = float(low_confidence.sum() / max(textured.sum(), 1))

    contributions = [float(np.mean(source_map == index)) for index in range(len(aligned))]
    return energy, source_map, confidence, low_confidence_share, contributions


def _tile_winners(energy: np.ndarray) -> list[int]:
    _, height, width = energy.shape
    winners: list[int] = []
    for row in range(4):
        y0, y1 = height * row // 4, height * (row + 1) // 4
        for column in range(4):
            x0, x1 = width * column // 4, width * (column + 1) // 4
            scores = np.mean(np.maximum(energy[:, y0:y1, x0:x1], 0.0), axis=(1, 2))
            winners.append(int(np.argmax(scores)))
    return sorted(set(winners))


def _risk_mask(
    aligned: Sequence[np.ndarray], valid_masks: Sequence[np.ndarray]
) -> tuple[np.ndarray, float]:
    normalized = []
    for image in aligned:
        gray = _normalize_for_alignment(_gray_float(image))
        # Strong low-pass filtering suppresses the expected high-frequency change
        # caused by moving the focal plane. Remaining differences are more likely
        # to be subject motion, occlusion change, or severe focus breathing.
        normalized.append(cv2.GaussianBlur(gray, (0, 0), 14.0))
    stack = np.stack(normalized)
    common_valid = np.logical_and.reduce(valid_masks)
    temporal_range = stack.max(axis=0) - stack.min(axis=0)
    mask = np.logical_and(temporal_range > 0.16, common_valid).astype(np.uint8) * 255
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)
    affected = float(np.logical_and(mask > 0, common_valid).sum() / max(common_valid.sum(), 1))
    return mask, affected


def _risk_level(affected_share: float) -> str:
    if affected_share <= MOTION_MEDIUM_SHARE:
        return "low"
    if affected_share <= MOTION_HIGH_SHARE:
        return "medium"
    return "high"


def _analysis(
    paths: Sequence[Path], images: Sequence[np.ndarray], reference_index: int
) -> tuple[dict, list[np.ndarray], list[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    hashes = [_sha256(path) for path in paths]
    dimensions = [(int(image.shape[1]), int(image.shape[0])) for image in images]
    blockers: list[str] = []
    warnings: list[str] = []

    pixel_hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
    if len(set(hashes)) != len(hashes) or len(set(pixel_hashes)) != len(pixel_hashes):
        blockers.append("duplicate_content")
    if len(set(dimensions)) != 1:
        blockers.append("dimension_mismatch")
        report = {
            "status": "blocked",
            "blockers": blockers,
            "warnings": warnings,
            "reference_index": reference_index,
            "inputs": [
                {"path": str(path), "sha256": digest, "dimensions": list(size)}
                for path, digest, size in zip(paths, hashes, dimensions, strict=True)
            ],
        }
        return report, [], [], np.empty(0), np.empty(0), np.empty(0)

    aligned, matrices, valid_masks, confidence = _align_rigid(images, reference_index)
    energy, source_map, focus_confidence, low_share, contributions = _focus_metrics(
        aligned, valid_masks
    )
    diverse_sources = _tile_winners(energy)
    risk_mask, risk_share = _risk_mask(aligned, valid_masks)
    exposure_span = _exposure_span_ev(images)
    breathing = [
        0.0 if index == reference_index else _estimate_breathing_share(images[reference_index], image)
        for index, image in enumerate(images)
    ]
    measured_breathing = [value for value in breathing if value is not None]
    max_breathing = max(measured_breathing, default=0.0)

    if min(confidence) < MIN_ALIGNMENT_CONFIDENCE:
        blockers.append("rigid_alignment_confidence_too_low")
    if len(diverse_sources) < 2:
        blockers.append("focus_plane_diversity_low")
    if max_breathing > BREATHING_BLOCK_SHARE:
        blockers.append("focus_breathing_too_large_for_rigid_alignment")
    elif max_breathing > BREATHING_REVIEW_SHARE:
        warnings.append("focus_breathing_review_required")
    if any(value is None for value in breathing):
        warnings.append("focus_breathing_measurement_unavailable_for_some_frames")
    if exposure_span > EXPOSURE_REVIEW_EV:
        warnings.append("exposure_variation_not_used_for_hdr")
    risk = _risk_level(risk_share)
    if risk != "low":
        warnings.append(f"motion_or_breathing_risk_{risk}")
    if low_share > LOW_CONFIDENCE_REVIEW_SHARE:
        warnings.append("focus_source_confidence_low")

    status = "blocked" if blockers else ("review_required" if warnings else "pass")
    report = {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "reference_index": reference_index,
        "inputs": [
            {
                "path": str(path),
                "sha256": digest,
                "dimensions": list(size),
                "focus_contribution_share": contributions[index],
            }
            for index, (path, digest, size) in enumerate(
                zip(paths, hashes, dimensions, strict=True)
            )
        ],
        "alignment": {
            "model": "rigid rotation and translation only",
            "confidence": confidence,
            "inverse_warp_matrices": [matrix.tolist() for matrix in matrices],
        },
        "focus_plane": {
            "tile_winner_source_indices": diverse_sources,
            "low_confidence_share_of_textured_area": low_share,
        },
        "focus_breathing": {
            "estimated_scale_delta_share": breathing,
            "maximum_measured_scale_delta_share": max_breathing,
            "applied_as_alignment_scale": False,
        },
        "exposure_span_ev_from_median_luminance": exposure_span,
        "motion_or_breathing_risk": {
            "level": risk,
            "affected_share": risk_share,
        },
    }
    return report, aligned, valid_masks, source_map, focus_confidence, risk_mask


def analyze_focus_stack(
    input_paths: Sequence[str | Path], reference_index: int | None = None
) -> dict:
    """Analyze whether real multi-focus frames are suitable for rigid focus stacking."""

    paths = _validate_paths(input_paths)
    images = [_load_rgb(path) for path in paths]
    reference = _reference_index(len(paths), reference_index)
    report, _, _, _, _, _ = _analysis(paths, images, reference)
    return report


def _blend_sources(
    aligned: Sequence[np.ndarray],
    valid_masks: Sequence[np.ndarray],
    source_map: np.ndarray,
    blend_radius: int,
) -> np.ndarray:
    if blend_radius < 0 or blend_radius > 64:
        raise ValueError("blend_radius must be between 0 and 64 pixels.")
    image_stack = np.stack(aligned).astype(np.float32) / 255.0
    if len(valid_masks) != len(aligned):
        raise ValueError("valid_masks must match the number of aligned frames.")
    weights = []
    for index, valid in enumerate(valid_masks):
        if valid.shape != source_map.shape:
            raise ValueError("Every valid mask must match the focus source map.")
        mask = (source_map == index).astype(np.float32)
        if blend_radius > 0:
            sigma = max(blend_radius / 3.0, 0.5)
            mask = cv2.GaussianBlur(mask, (0, 0), sigma)
        # Alignment introduces invalid borders. Remove their weights after
        # smoothing so a neighboring source cannot bleed black padding into the
        # composite merely because its focus region touches an image edge.
        mask *= valid.astype(np.float32)
        weights.append(mask)
    weight_stack = np.stack(weights)
    total_weight = weight_stack.sum(axis=0, keepdims=True)
    if np.any(total_weight <= 1e-8):
        raise ValueError("No valid aligned source covers part of the focus stack.")
    weight_stack /= total_weight
    composite = np.sum(image_stack * weight_stack[..., None], axis=0)
    return np.clip(composite, 0.0, 1.0)


def _save_contact_sheet(aligned: Sequence[np.ndarray], destination: Path) -> None:
    thumbs: list[Image.Image] = []
    for index, rgb in enumerate(aligned):
        image = Image.fromarray(rgb)
        image.thumbnail((360, 240), Image.Resampling.LANCZOS)
        panel = Image.new("RGB", (380, image.height + 38), "white")
        panel.paste(image, ((380 - image.width) // 2, 28))
        ImageDraw.Draw(panel).text((10, 7), f"SOURCE {index}", fill=(20, 20, 20))
        thumbs.append(panel)
    sheet = Image.new("RGB", (380, sum(item.height for item in thumbs)), (235, 235, 235))
    y = 0
    for panel in thumbs:
        sheet.paste(panel, (0, y))
        y += panel.height
    sheet.save(destination, quality=92)


def _ensure_output_targets(output_dir: Path, input_paths: Sequence[Path]) -> dict[str, Path]:
    resolved_dir = output_dir.expanduser().resolve()
    targets = {name: resolved_dir / name for name in OUTPUT_NAMES}
    input_set = set(input_paths)
    collisions = [str(path) for path in targets.values() if path.resolve() in input_set]
    if collisions:
        raise ValueError(f"Output paths collide with input photographs: {collisions}")
    existing = [str(path) for path in targets.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite existing outputs: {existing}")
    return targets


def stack_focus(
    input_paths: Sequence[str | Path],
    output_dir: str | Path,
    *,
    reference_index: int | None = None,
    blend_radius: int = 7,
) -> dict:
    """Create a source-constrained focus stack and deterministic review artifacts."""

    paths = _validate_paths(input_paths)
    images = [_load_rgb(path) for path in paths]
    reference = _reference_index(len(paths), reference_index)
    report, aligned, valid_masks, source_map, focus_confidence, risk_mask = _analysis(
        paths, images, reference
    )
    if report["status"] == "blocked":
        raise ValueError(f"Input set failed focus stacking checks: {report['blockers']}")

    targets = _ensure_output_targets(Path(output_dir), paths)
    targets[OUTPUT_NAMES[0]].parent.mkdir(parents=True, exist_ok=True)
    composite = _blend_sources(
        aligned,
        valid_masks,
        source_map,
        int(blend_radius),
    )
    composite_16 = np.round(composite * 65535.0).astype(np.uint16)
    preview = np.round(composite * 255.0).astype(np.uint8)
    source_scale = 65535.0 / max(len(paths) - 1, 1)
    source_encoded = np.round(source_map.astype(np.float32) * source_scale).astype(np.uint16)
    confidence_encoded = np.round(focus_confidence * 65535.0).astype(np.uint16)

    if not cv2.imwrite(
        str(targets["focus_stacked_16bit.tif"]),
        cv2.cvtColor(composite_16, cv2.COLOR_RGB2BGR),
    ):
        raise OSError("Could not save the 16-bit focus stack.")
    Image.fromarray(preview).save(targets["focus_stacked_preview.jpg"], quality=95)
    if not cv2.imwrite(str(targets["focus_source_map.png"]), source_encoded):
        raise OSError("Could not save the focus source map.")
    if not cv2.imwrite(str(targets["focus_confidence.png"]), confidence_encoded):
        raise OSError("Could not save the focus confidence map.")
    if not cv2.imwrite(str(targets["motion_or_breathing_risk_mask.png"]), risk_mask):
        raise OSError("Could not save the risk mask.")
    _save_contact_sheet(aligned, targets["alignment_contact_sheet.jpg"])

    after_hashes = [_sha256(path) for path in paths]
    if after_hashes != [item["sha256"] for item in report["inputs"]]:
        raise RuntimeError("A focus-stack source file changed during processing.")

    report["recipe"] = {
        "alignment": "OpenCV ECC Euclidean transform: rotation and translation only",
        "focus_measure": "multi-scale local Laplacian energy",
        "selection": "per-pixel best measured source frame",
        "blend_radius_pixels": int(blend_radius),
        "claim_boundary": "no detail synthesized beyond recorded input frames",
    }
    report["outputs"] = {key: str(value) for key, value in targets.items()}
    report["source_hashes_verified_after_processing"] = True
    report["output_sha256"] = {
        key: _sha256(path)
        for key, path in targets.items()
        if key != "focus_stack_report.json"
    }
    targets["focus_stack_report.json"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
