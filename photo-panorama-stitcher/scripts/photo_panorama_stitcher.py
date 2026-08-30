"""Deterministic stitching for real, overlapping panorama photographs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

MIN_FEATURES = 12
MIN_MATCHES = 10
MIN_INLIERS = 8
MIN_INLIER_RATIO = 0.25
MIN_OVERLAP_SHARE = 0.08
MIN_EXTENSION_SHARE = 0.05
REVIEW_CONFIDENCE = 0.45
BLOCK_CONFIDENCE = 0.25
MAX_CANVAS_AREA_MULTIPLIER = 12.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_paths(input_paths: Sequence[str | Path]) -> list[Path]:
    paths = [Path(item).expanduser().resolve() for item in input_paths]
    if len(paths) < 2:
        raise ValueError("Panorama stitching requires at least two photographs.")
    if len(set(paths)) != len(paths):
        raise ValueError("Each panorama input path must be unique.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Input photographs not found: {missing}")
    return paths


def _load_rgb(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            oriented = ImageOps.exif_transpose(image)
            rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
    except (OSError, ValueError) as error:
        raise ValueError(f"Unable to decode photograph: {path}") from error
    if min(rgb.shape[:2]) < 64:
        raise ValueError(f"Photograph is too small for reliable stitching: {path}")
    return rgb


def _validate_projection(projection: str, focal_length_px: float | None) -> None:
    if projection not in {"planar", "cylindrical"}:
        raise ValueError("projection must be 'planar' or 'cylindrical'.")
    if focal_length_px is not None:
        value = float(focal_length_px)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("focal_length_px must be finite and positive.")
        if projection != "cylindrical":
            raise ValueError(
                "focal_length_px is only used with cylindrical projection."
            )


def _cylindrical_warp(
    image: np.ndarray,
    focal_length_px: float,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape[:2]
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )
    theta = (grid_x - center_x) / focal_length_px
    relative_y = (grid_y - center_y) / focal_length_px
    map_x = focal_length_px * np.tan(theta) + center_x
    map_y = focal_length_px * relative_y / np.cos(theta) + center_y
    valid = (
        (map_x >= 0)
        & (map_x <= width - 1)
        & (map_y >= 0)
        & (map_y <= height - 1)
    )
    warped = cv2.remap(
        image,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )
    return warped, valid.astype(np.uint8) * 255


def _prepare_images(
    images: Sequence[np.ndarray],
    projection: str,
    focal_length_px: float | None,
) -> tuple[list[np.ndarray], list[np.ndarray], float | None, str]:
    if projection == "planar":
        masks = [np.full(image.shape[:2], 255, dtype=np.uint8) for image in images]
        return [image.copy() for image in images], masks, None, "not_applicable"

    resolved_focal = (
        float(focal_length_px)
        if focal_length_px is not None
        else 0.9 * max(max(image.shape[:2]) for image in images)
    )
    source = "provided" if focal_length_px is not None else "estimated"
    projected: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    for image in images:
        warped, valid = _cylindrical_warp(image, resolved_focal)
        projected.append(warped)
        masks.append(valid)
    return projected, masks, resolved_focal, source


def _feature_detector() -> tuple[object, int, str]:
    if hasattr(cv2, "SIFT_create"):
        return cv2.SIFT_create(nfeatures=4000), cv2.NORM_L2, "SIFT"
    return cv2.ORB_create(nfeatures=5000), cv2.NORM_HAMMING, "ORB"


def _detect(
    detector: object,
    image: np.ndarray,
    mask: np.ndarray,
) -> tuple[list[cv2.KeyPoint], np.ndarray | None]:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    keypoints, descriptors = detector.detectAndCompute(gray, mask)
    return list(keypoints), descriptors


def _polygon_metrics(
    homography: np.ndarray,
    current_shape: tuple[int, int],
    previous_shape: tuple[int, int],
) -> tuple[float, float, float]:
    current_height, current_width = current_shape
    previous_height, previous_width = previous_shape
    current_corners = np.float32(
        [[0, 0], [current_width, 0], [current_width, current_height], [0, current_height]]
    ).reshape(-1, 1, 2)
    previous_corners = np.float32(
        [[0, 0], [previous_width, 0], [previous_width, previous_height], [0, previous_height]]
    ).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(current_corners, homography).reshape(-1, 2)
    # Remove sub-pixel numerical noise that can make OpenCV's convex intersection
    # misclassify otherwise coincident rectangle edges.
    transformed = np.round(transformed, decimals=4)
    previous_polygon = previous_corners.reshape(-1, 2)
    current_area = abs(float(cv2.contourArea(transformed.astype(np.float32))))
    previous_area = float(previous_width * previous_height)
    if current_area < 1.0 or not np.isfinite(transformed).all():
        return 0.0, 0.0, 0.0
    try:
        intersection_area, _ = cv2.intersectConvexConvex(
            transformed.astype(np.float32),
            previous_polygon.astype(np.float32),
        )
    except cv2.error:
        intersection_area = 0.0
    intersection = max(float(intersection_area), 0.0)
    overlap_share = intersection / max(min(current_area, previous_area), 1.0)
    extension_share = max(1.0 - intersection / current_area, 0.0)
    area_scale = current_area / max(float(current_width * current_height), 1.0)
    return overlap_share, extension_share, area_scale


def _pair_geometry(
    previous: np.ndarray,
    current: np.ndarray,
    previous_mask: np.ndarray,
    current_mask: np.ndarray,
    detector: object,
    norm: int,
) -> tuple[dict, np.ndarray | None]:
    previous_points, previous_descriptors = _detect(detector, previous, previous_mask)
    current_points, current_descriptors = _detect(detector, current, current_mask)
    result = {
        "previous_feature_count": len(previous_points),
        "current_feature_count": len(current_points),
        "ratio_test_match_count": 0,
        "ransac_inlier_count": 0,
        "ransac_inlier_ratio": 0.0,
        "estimated_overlap_share": 0.0,
        "estimated_view_extension_share": 0.0,
        "projected_area_scale": 0.0,
        "confidence": 0.0,
        "blockers": [],
    }
    if len(previous_points) < MIN_FEATURES or len(current_points) < MIN_FEATURES:
        result["blockers"].append("insufficient_features")
        return result, None
    if previous_descriptors is None or current_descriptors is None:
        result["blockers"].append("descriptors_unavailable")
        return result, None

    matcher = cv2.BFMatcher(norm)
    raw_matches = matcher.knnMatch(current_descriptors, previous_descriptors, k=2)
    good_matches = [
        pair[0]
        for pair in raw_matches
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
    ]
    result["ratio_test_match_count"] = len(good_matches)
    if len(good_matches) < MIN_MATCHES:
        result["blockers"].append("insufficient_feature_matches")
        return result, None

    current_xy = np.float32(
        [current_points[match.queryIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)
    previous_xy = np.float32(
        [previous_points[match.trainIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(
        current_xy,
        previous_xy,
        cv2.RANSAC,
        4.0,
        maxIters=4000,
        confidence=0.995,
    )
    if homography is None or inlier_mask is None or not np.isfinite(homography).all():
        result["blockers"].append("homography_unavailable")
        return result, None

    inliers = int(inlier_mask.ravel().sum())
    inlier_ratio = inliers / max(len(good_matches), 1)
    overlap, extension, area_scale = _polygon_metrics(
        homography,
        current.shape[:2],
        previous.shape[:2],
    )
    result.update(
        {
            "ransac_inlier_count": inliers,
            "ransac_inlier_ratio": round(float(inlier_ratio), 6),
            "estimated_overlap_share": round(float(overlap), 6),
            "estimated_view_extension_share": round(float(extension), 6),
            "projected_area_scale": round(float(area_scale), 6),
        }
    )

    match_score = min(len(good_matches) / 40.0, 1.0)
    inlier_score = min(inlier_ratio / 0.65, 1.0)
    overlap_score = min(overlap / 0.25, 1.0)
    extension_score = min(extension / 0.25, 1.0)
    pair_confidence = (
        0.20 * match_score
        + 0.35 * inlier_score
        + 0.20 * overlap_score
        + 0.25 * extension_score
    )
    result["confidence"] = round(float(np.clip(pair_confidence, 0.0, 1.0)), 6)

    if inliers < MIN_INLIERS or inlier_ratio < MIN_INLIER_RATIO:
        result["blockers"].append("weak_ransac_consensus")
    if overlap < MIN_OVERLAP_SHARE:
        result["blockers"].append("insufficient_overlap")
    if extension < MIN_EXTENSION_SHARE:
        result["blockers"].append("insufficient_view_extension")
    if not 0.2 <= area_scale <= 5.0:
        result["blockers"].append("unreasonable_projected_geometry")
    if pair_confidence < BLOCK_CONFIDENCE:
        result["blockers"].append("pair_confidence_too_low")
    return result, homography


def _canvas_bounds(
    transforms: Sequence[np.ndarray],
    images: Sequence[np.ndarray],
) -> tuple[list[int], int, int]:
    all_corners: list[np.ndarray] = []
    for transform, image in zip(transforms, images, strict=True):
        height, width = image.shape[:2]
        corners = np.float32(
            [[0, 0], [width, 0], [width, height], [0, height]]
        ).reshape(-1, 1, 2)
        all_corners.append(cv2.perspectiveTransform(corners, transform).reshape(-1, 2))
    points = np.vstack(all_corners)
    minimum = np.floor(points.min(axis=0)).astype(int)
    maximum = np.ceil(points.max(axis=0)).astype(int)
    width = int(maximum[0] - minimum[0])
    height = int(maximum[1] - minimum[1])
    return [int(minimum[0]), int(minimum[1]), int(maximum[0]), int(maximum[1])], width, height


def _analysis_runtime(
    input_paths: Sequence[str | Path],
    projection: str,
    focal_length_px: float | None,
) -> tuple[dict, dict]:
    _validate_projection(projection, focal_length_px)
    paths = _validate_paths(input_paths)
    source_hashes = [_sha256(path) for path in paths]
    images = [_load_rgb(path) for path in paths]
    pixel_hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
    duplicate_content = (
        len(set(source_hashes)) != len(source_hashes)
        or len(set(pixel_hashes)) != len(pixel_hashes)
    )
    projected, projection_masks, resolved_focal, focal_source = _prepare_images(
        images,
        projection,
        focal_length_px,
    )
    detector, norm, feature_name = _feature_detector()
    cv2.setRNGSeed(20260830)
    pair_reports: list[dict] = []
    pair_homographies: list[np.ndarray | None] = []
    blockers: list[str] = []
    warnings: list[str] = []
    if duplicate_content:
        blockers.append("duplicate_source_content")

    for pair_index in range(1, len(projected)):
        pair_report, homography = _pair_geometry(
            projected[pair_index - 1],
            projected[pair_index],
            projection_masks[pair_index - 1],
            projection_masks[pair_index],
            detector,
            norm,
        )
        pair_report["pair"] = [pair_index - 1, pair_index]
        pair_reports.append(pair_report)
        pair_homographies.append(homography)
        blockers.extend(
            f"pair_{pair_index - 1}_{pair_index}:{item}"
            for item in pair_report["blockers"]
        )
        if not pair_report["blockers"] and pair_report["confidence"] < REVIEW_CONFIDENCE:
            warnings.append(f"pair_{pair_index - 1}_{pair_index}:low_confidence")

    transforms: list[np.ndarray] = [np.eye(3, dtype=np.float64)]
    if all(homography is not None for homography in pair_homographies):
        for homography in pair_homographies:
            transform = transforms[-1] @ homography
            transform /= transform[2, 2]
            transforms.append(transform)

    canvas_bounds: list[int] | None = None
    canvas_width = 0
    canvas_height = 0
    if len(transforms) == len(projected):
        canvas_bounds, canvas_width, canvas_height = _canvas_bounds(transforms, projected)
        max_source_area = max(image.shape[0] * image.shape[1] for image in projected)
        if canvas_width <= 0 or canvas_height <= 0:
            blockers.append("invalid_canvas_geometry")
        elif canvas_width * canvas_height > MAX_CANVAS_AREA_MULTIPLIER * max_source_area:
            blockers.append("unreasonable_canvas_size")

    if projection == "cylindrical" and focal_source == "estimated":
        warnings.append("estimated_cylindrical_focal_length")
    pair_confidences = [float(pair["confidence"]) for pair in pair_reports]
    overall_confidence = min(pair_confidences, default=0.0)
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    status = "blocked" if blockers else "review_required" if warnings else "ready"
    report = {
        "status": status,
        "confidence": round(overall_confidence, 6),
        "confidence_meaning": "heuristic failure grading, not a probability",
        "blockers": blockers,
        "warnings": warnings,
        "inputs": [
            {
                "index": index,
                "path": str(path),
                "sha256": digest,
                "width": int(image.shape[1]),
                "height": int(image.shape[0]),
            }
            for index, (path, digest, image) in enumerate(
                zip(paths, source_hashes, images, strict=True)
            )
        ],
        "input_order_contract": "spatially adjacent order supplied by the caller",
        "projection": {
            "model": projection,
            "focal_length_px": resolved_focal,
            "focal_length_source": focal_source,
            "camera_model_claim": "image projection choice, not camera calibration",
        },
        "feature_algorithm": feature_name,
        "pairs": pair_reports,
        "global_transforms_to_first_frame": [
            np.round(transform, 10).tolist() for transform in transforms
        ],
        "estimated_canvas_bounds_xyxy": canvas_bounds,
        "estimated_canvas_size": [canvas_width, canvas_height],
        "claim_boundary": "uses only pixels recorded in the supplied photographs",
        "limitations": [
            "parallax and moving subjects may still create ghosts",
            "automatic confidence does not prove a seamless result",
            "unobserved canvas areas are never generated or filled",
        ],
    }
    runtime = {
        "paths": paths,
        "source_hashes": source_hashes,
        "images": images,
        "projected": projected,
        "projection_masks": projection_masks,
        "transforms": transforms,
    }
    return report, runtime


def analyze_panorama(
    input_paths: Sequence[str | Path],
    *,
    projection: str = "planar",
    focal_length_px: float | None = None,
) -> dict:
    """Analyze real panorama overlap and geometry without writing files."""

    report, _ = _analysis_runtime(input_paths, projection, focal_length_px)
    return report


def _maximum_valid_rectangle(mask: np.ndarray) -> tuple[int, int, int, int]:
    binary = mask.astype(bool)
    height, width = binary.shape
    histogram = np.zeros(width, dtype=np.int32)
    best_area = 0
    best = (0, 0, 0, 0)
    for row in range(height):
        histogram = np.where(binary[row], histogram + 1, 0)
        stack: list[int] = []
        for column in range(width + 1):
            current_height = int(histogram[column]) if column < width else 0
            while stack and int(histogram[stack[-1]]) > current_height:
                top = stack.pop()
                rectangle_height = int(histogram[top])
                left = stack[-1] + 1 if stack else 0
                rectangle_width = column - left
                area = rectangle_height * rectangle_width
                if area > best_area:
                    best_area = area
                    best = (
                        left,
                        row - rectangle_height + 1,
                        rectangle_width,
                        rectangle_height,
                    )
            stack.append(column)
    if best_area == 0:
        raise ValueError("No fully valid panorama crop is available.")
    return best


def _contact_sheet(images: Sequence[np.ndarray], panorama: np.ndarray) -> Image.Image:
    panels = [*images, panorama]
    labels = [f"SOURCE {index + 1:02d}" for index in range(len(images))] + ["PANORAMA"]
    panel_width = 420
    panel_height = 230
    margin = 20
    sheet = Image.new(
        "RGB",
        (panel_width + 2 * margin, len(panels) * (panel_height + 38) + margin),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    y = margin
    for panel, label in zip(panels, labels, strict=True):
        image = Image.fromarray(panel)
        image.thumbnail((panel_width, panel_height), Image.Resampling.LANCZOS)
        x = margin + (panel_width - image.width) // 2
        sheet.paste(image, (x, y))
        draw.text((margin, y + panel_height + 8), label, fill=(35, 35, 35))
        y += panel_height + 38
    return sheet


def _output_targets(output_dir: Path) -> dict[str, Path]:
    return {
        "panorama_16bit_tiff": output_dir / "panorama_16bit.tif",
        "panorama_preview": output_dir / "panorama_preview.jpg",
        "valid_area_mask": output_dir / "valid_area_mask.png",
        "seam_transition_map": output_dir / "seam_transition_map.png",
        "contact_sheet": output_dir / "stitch_contact_sheet.jpg",
        "report": output_dir / "panorama_report.json",
    }


def stitch_panorama(
    input_paths: Sequence[str | Path],
    output_dir: str | Path,
    *,
    projection: str = "planar",
    focal_length_px: float | None = None,
) -> dict:
    """Stitch a validated panorama and write reproducible, non-generative outputs."""

    analysis, runtime = _analysis_runtime(input_paths, projection, focal_length_px)
    if analysis["blockers"]:
        joined = ", ".join(analysis["blockers"])
        raise ValueError(f"Blocked panorama stitching: {joined}")

    destination = Path(output_dir).expanduser().resolve()
    targets = _output_targets(destination)
    source_paths = set(runtime["paths"])
    if any(target in source_paths for target in targets.values()):
        raise ValueError("Output paths must not replace panorama source photographs.")
    existing = [str(target) for target in targets.values() if target.exists()]
    if existing:
        raise FileExistsError(f"Refusing to overwrite existing outputs: {existing}")

    projected: list[np.ndarray] = runtime["projected"]
    projection_masks: list[np.ndarray] = runtime["projection_masks"]
    transforms: list[np.ndarray] = runtime["transforms"]
    bounds = analysis["estimated_canvas_bounds_xyxy"]
    if bounds is None or len(transforms) != len(projected):
        raise ValueError("Panorama canvas geometry is unavailable.")
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    canvas_width = int(maximum_x - minimum_x)
    canvas_height = int(maximum_y - minimum_y)
    translation = np.array(
        [[1.0, 0.0, -minimum_x], [0.0, 1.0, -minimum_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )

    warped_images: list[np.ndarray] = []
    warped_masks: list[np.ndarray] = []
    canvas_transforms: list[np.ndarray] = []
    for image, mask, transform in zip(
        projected,
        projection_masks,
        transforms,
        strict=True,
    ):
        canvas_transform = translation @ transform
        canvas_transforms.append(canvas_transform)
        warped_images.append(
            cv2.warpPerspective(
                image,
                canvas_transform,
                (canvas_width, canvas_height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
            )
        )
        warped_masks.append(
            cv2.warpPerspective(
                mask,
                canvas_transform,
                (canvas_width, canvas_height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
            )
            > 0
        )

    gains = [1.0]
    for index in range(1, len(warped_images)):
        overlap = warped_masks[index - 1] & warped_masks[index]
        previous_luma = cv2.cvtColor(
            warped_images[index - 1], cv2.COLOR_RGB2GRAY
        ).astype(np.float32)
        current_luma = cv2.cvtColor(
            warped_images[index], cv2.COLOR_RGB2GRAY
        ).astype(np.float32)
        useful = overlap & (previous_luma > 8) & (current_luma > 8)
        if int(useful.sum()) >= 128:
            ratio = float(np.median(previous_luma[useful]) / np.median(current_luma[useful]))
            gain = float(np.clip(gains[-1] * ratio, 0.5, 2.0))
        else:
            gain = gains[-1]
        gains.append(gain)

    accumulator = np.zeros((canvas_height, canvas_width, 3), dtype=np.float64)
    weight_sum = np.zeros((canvas_height, canvas_width), dtype=np.float64)
    contributor_count = np.zeros((canvas_height, canvas_width), dtype=np.uint8)
    for image, valid, gain in zip(warped_images, warped_masks, gains, strict=True):
        valid_u8 = valid.astype(np.uint8)
        distance = cv2.distanceTransform(valid_u8, cv2.DIST_L2, 3).astype(np.float64)
        weight = np.where(valid, np.maximum(distance, 1.0), 0.0)
        adjusted = np.clip(image.astype(np.float64) * gain, 0.0, 255.0)
        accumulator += adjusted * weight[..., None]
        weight_sum += weight
        contributor_count += valid.astype(np.uint8)

    union_mask = weight_sum > 0
    panorama_canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.float64)
    panorama_canvas[union_mask] = np.clip(
        accumulator[union_mask] / weight_sum[union_mask, None],
        0,
        255,
    )
    crop_x, crop_y, crop_width, crop_height = _maximum_valid_rectangle(union_mask)
    crop_slice = np.s_[crop_y : crop_y + crop_height, crop_x : crop_x + crop_width]
    panorama_float = panorama_canvas[crop_slice]
    panorama = np.clip(np.round(panorama_float), 0, 255).astype(np.uint8)
    seam_map = np.where(contributor_count[crop_slice] >= 2, 255, 0).astype(np.uint8)

    destination.mkdir(parents=True, exist_ok=True)
    panorama_16bit = np.clip(np.round(panorama_float * 257.0), 0, 65535).astype(
        np.uint16
    )
    if not cv2.imwrite(
        str(targets["panorama_16bit_tiff"]),
        cv2.cvtColor(panorama_16bit, cv2.COLOR_RGB2BGR),
    ):
        raise OSError("Unable to write panorama TIFF.")
    Image.fromarray(panorama).save(
        targets["panorama_preview"],
        quality=95,
        subsampling=0,
    )
    final_valid_mask = union_mask[crop_slice]
    Image.fromarray(final_valid_mask.astype(np.uint8) * 255).save(
        targets["valid_area_mask"]
    )
    Image.fromarray(seam_map).save(targets["seam_transition_map"])
    _contact_sheet(runtime["images"], panorama).save(
        targets["contact_sheet"],
        quality=92,
        subsampling=0,
    )

    after_hashes = [_sha256(path) for path in runtime["paths"]]
    if after_hashes != runtime["source_hashes"]:
        raise RuntimeError("A panorama source file changed during processing.")
    output_hashes = {
        key: _sha256(path)
        for key, path in targets.items()
        if key != "report"
    }
    report = {
        **analysis,
        "recipe": {
            "registration": "adjacent feature matching with RANSAC homographies",
            "exposure_transition": "overlap median luminance, scalar RGB gain",
            "blend": "valid-mask distance feathering",
            "valid_crop": "largest axis-aligned rectangle fully covered by source pixels",
            "generative_fill": False,
            "tiff_precision_claim": "preserves blend precision; does not add captured dynamic range",
        },
        "canvas_transforms": [
            np.round(transform, 10).tolist() for transform in canvas_transforms
        ],
        "exposure_gains": [round(gain, 6) for gain in gains],
        "crop_box_xywh": [crop_x, crop_y, crop_width, crop_height],
        "final_size": [crop_width, crop_height],
        "outputs": {key: str(path) for key, path in targets.items()},
        "output_sha256": output_hashes,
        "source_hashes_verified_after_processing": True,
    }
    targets["report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
