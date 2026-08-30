"""Create a non-destructive draft sequence and numbered contact sheet."""

from __future__ import annotations

import csv
import hashlib
import json
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import ExifTags, Image, ImageDraw, ImageFont, ImageOps

VALID_STRATEGIES = {"chronology", "visual-rhythm", "manual"}
DATETIME_TAGS = {
    key
    for key, value in ExifTags.TAGS.items()
    if value in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_time(image: Image.Image) -> str | None:
    exif = image.getexif()
    values = [exif.get(tag) for tag in DATETIME_TAGS if exif.get(tag)]
    for value in values:
        text = str(value)
        for pattern in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                time.strptime(text, pattern)
                return text.replace(":", "-", 2).replace(" ", "T", 1)
            except ValueError:
                continue
    return None


def _perceptual_hash(gray: np.ndarray) -> int:
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(
        np.float32
    )
    transformed = cv2.dct(resized)
    low_frequency = transformed[:8, :8].copy()
    threshold = float(np.median(low_frequency.ravel()[1:]))
    bits = low_frequency > threshold
    value = 0
    for bit in bits.ravel():
        value = (value << 1) | int(bit)
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _measure(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        captured = _capture_time(image)
        oriented = ImageOps.exif_transpose(image)
        rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    sample = cv2.resize(
        rgb, (192, max(1, round(192 * height / width))), interpolation=cv2.INTER_AREA
    )
    sample_float = sample.astype(np.float32) / 255.0
    lab = cv2.cvtColor(sample_float, cv2.COLOR_RGB2LAB)
    hsv = cv2.cvtColor(sample_float, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(sample, cv2.COLOR_RGB2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    edges = cv2.Canny(gray, 80, 160)
    orientation = (
        "landscape" if width > height else "portrait" if height > width else "square"
    )
    return {
        "path": str(path),
        "filename": path.name,
        "sha256": _hash(path),
        "captured_at": captured,
        "width": width,
        "height": height,
        "orientation": orientation,
        "luma": float(np.median(gray) / 255.0),
        "saturation": float(np.mean(hsv[..., 1])),
        "lab_mean": [float(value) for value in np.mean(lab, axis=(0, 1))],
        "edge_density": float(np.mean(edges > 0)),
        "sharpness": float(np.var(laplacian)),
        "phash": _perceptual_hash(gray),
    }


def _visual_distance(left: dict[str, Any], right: dict[str, Any]) -> float:
    lab_left = np.asarray(left["lab_mean"], dtype=np.float32)
    lab_right = np.asarray(right["lab_mean"], dtype=np.float32)
    color_distance = float(
        np.linalg.norm((lab_left - lab_right) / np.array([100.0, 128.0, 128.0]))
    )
    luma_distance = abs(left["luma"] - right["luma"])
    edge_distance = abs(left["edge_density"] - right["edge_density"])
    orientation_change = 0.18 if left["orientation"] != right["orientation"] else 0.0
    return (
        0.45 * color_distance
        + 0.28 * luma_distance
        + 0.17 * edge_distance
        + orientation_change
    )


def _chronology_key(item: dict[str, Any]) -> tuple[bool, str, str]:
    captured = item["captured_at"]
    return captured is None, captured or "", item["filename"].casefold()


def _sequence_visual_rhythm(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) < 2:
        return items.copy()
    dated = [item for item in items if item["captured_at"] is not None]
    start = min(dated, key=_chronology_key) if dated else items[0]
    ordered = [start]
    remaining = [item for item in items if item is not start]
    while remaining:
        current = ordered[-1]
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for candidate in remaining:
            distance = _visual_distance(current, candidate)
            phash_distance = _hamming(current["phash"], candidate["phash"])
            near_duplicate = (
                phash_distance <= 8 and _visual_distance(current, candidate) <= 0.12
            )
            duplicate_penalty = 1.0 if near_duplicate and len(remaining) > 1 else 0.0
            repeated_orientation = (
                0.08
                if (
                    len(ordered) >= 2
                    and ordered[-2]["orientation"]
                    == current["orientation"]
                    == candidate["orientation"]
                )
                else 0.0
            )
            score = distance - duplicate_penalty - repeated_orientation
            scored.append((score, candidate["filename"].casefold(), candidate))
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        selected = scored[0][2]
        ordered.append(selected)
        remaining.remove(selected)
    return ordered


def _similar_pairs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(items):
        for right in items[left_index + 1 :]:
            distance = _hamming(left["phash"], right["phash"])
            if distance <= 8 and _visual_distance(left, right) <= 0.12:
                pairs.append(
                    {
                        "left": left["filename"],
                        "right": right["filename"],
                        "phash_distance": distance,
                    }
                )
    return pairs


def _contact_sheet(items: list[dict[str, Any]], path: Path) -> None:
    tile_width, tile_height = 300, 224
    label_height, gap, margin = 50, 18, 24
    columns = min(4, max(1, len(items)))
    rows = (len(items) + columns - 1) // columns
    canvas_width = margin * 2 + columns * tile_width + (columns - 1) * gap
    canvas_height = margin * 2 + rows * (tile_height + label_height) + (rows - 1) * gap
    canvas = Image.new("RGB", (canvas_width, canvas_height), (236, 234, 228))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        x = margin + column * (tile_width + gap)
        y = margin + row * (tile_height + label_height + gap)
        with Image.open(item["path"]) as image:
            preview = ImageOps.exif_transpose(image).convert("RGB")
            preview.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        backing = Image.new("RGB", (tile_width, tile_height), (38, 38, 36))
        paste_x = (tile_width - preview.width) // 2
        paste_y = (tile_height - preview.height) // 2
        backing.paste(preview, (paste_x, paste_y))
        canvas.paste(backing, (x, y))
        draw.rectangle((x, y, x + 38, y + 28), fill=(242, 95, 92))
        draw.text((x + 10, y + 8), f"{index + 1:02d}", fill="white", font=font)
        draw.text(
            (x, y + tile_height + 10), item["filename"], fill=(25, 25, 25), font=font
        )
    canvas.save(path, quality=94)


def _public_record(index: int, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "position": index,
        "path": item["path"],
        "filename": item["filename"],
        "sha256": item["sha256"],
        "captured_at": item["captured_at"],
        "orientation": item["orientation"],
        "luma": round(item["luma"], 6),
        "saturation": round(item["saturation"], 6),
        "edge_density": round(item["edge_density"], 6),
        "sharpness": round(item["sharpness"], 6),
    }


def build_series(
    input_paths: list[str | Path] | tuple[str | Path, ...],
    output_dir: str | Path,
    strategy: str = "visual-rhythm",
    visual_review_confirmed: bool = False,
) -> dict[str, Any]:
    if strategy not in VALID_STRATEGIES:
        raise ValueError(f"不支持的策略: {strategy}")
    if not input_paths:
        raise ValueError("input_paths不能为空")
    if visual_review_confirmed and strategy != "manual":
        raise ValueError("只有manual策略允许记录visual_review_confirmed=True")
    sources = [Path(path).expanduser().resolve() for path in input_paths]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("找不到照片: " + ", ".join(missing))
    if len(set(sources)) != len(sources):
        raise ValueError("input_paths包含重复路径")
    before_hashes = {str(path): _hash(path) for path in sources}
    measured = [_measure(path) for path in sources]
    if strategy == "manual":
        ordered = measured.copy()
    elif strategy == "chronology":
        ordered = sorted(measured, key=_chronology_key)
    else:
        ordered = _sequence_visual_rhythm(measured)

    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "series_sequence.json"
    csv_path = directory / "series_sequence.csv"
    contact_path = directory / "series_contact_sheet.jpg"
    existing = [
        str(path) for path in (json_path, csv_path, contact_path) if path.exists()
    ]
    if existing:
        raise FileExistsError("输出已存在，默认不覆盖: " + ", ".join(existing))

    records = [
        _public_record(index, item) for index, item in enumerate(ordered, start=1)
    ]
    pairs = _similar_pairs(measured)
    adjacent_similar = []
    for left, right in pairwise(ordered):
        distance = _hamming(left["phash"], right["phash"])
        if distance <= 8 and _visual_distance(left, right) <= 0.12:
            adjacent_similar.append(
                {
                    "left": left["filename"],
                    "right": right["filename"],
                    "phash_distance": distance,
                }
            )
    preserved = all(_hash(path) == before_hashes[str(path)] for path in sources)
    if not preserved:
        status = "blocked"
    elif visual_review_confirmed:
        status = "series-reviewed"
    else:
        status = "draft-review-required"
    payload = {
        "strategy": strategy,
        "status": status,
        "originals_preserved": preserved,
        "visual_review_confirmed": bool(visual_review_confirmed),
        "sequence": records,
        "similar_pairs": pairs,
        "adjacent_similar_pairs": adjacent_similar,
        "review_note": (
            "已按人工确认顺序生成复核版。"
            if visual_review_confirmed
            else "当前顺序仍是初稿，必须观看联系表后再确定最终叙事。"
        ),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    _contact_sheet(ordered, contact_path)
    return {
        "status": payload["status"],
        "visual_review_confirmed": payload["visual_review_confirmed"],
        "sequence": records,
        "similar_pairs": pairs,
        "adjacent_similar_pairs": adjacent_similar,
        "manifest": str(json_path),
        "csv": str(csv_path),
        "contact_sheet": str(contact_path),
    }
