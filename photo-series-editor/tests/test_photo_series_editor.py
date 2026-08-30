from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_series_editor import build_series


def _save(
    path: Path, color: tuple[int, int, int], captured_at: str, accent: bool = False
) -> None:
    rgb = np.full((150, 220, 3), color, dtype=np.uint8)
    if accent:
        rgb[25:100, 125:185] = [245, 215, 40]
    image = Image.fromarray(rgb, mode="RGB")
    exif = image.getexif()
    exif[36867] = captured_at
    image.save(path, exif=exif)


def _fixtures(root: Path) -> list[Path]:
    paths = [
        root / name for name in ("third.jpg", "first.jpg", "second.jpg", "echo.jpg")
    ]
    _save(paths[0], (30, 60, 120), "2026:01:03 10:00:00", accent=True)
    _save(paths[1], (210, 200, 185), "2026:01:01 10:00:00")
    _save(paths[2], (155, 45, 38), "2026:01:02 10:00:00", accent=True)
    _save(paths[3], (30, 60, 120), "2026:01:04 10:00:00", accent=True)
    return paths


def test_chronology_and_original_preservation(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = build_series(paths, tmp_path / "chronology", strategy="chronology")
    assert [item["filename"] for item in result["sequence"]] == [
        "first.jpg",
        "second.jpg",
        "third.jpg",
        "echo.jpg",
    ]
    assert result["status"] == "draft-review-required"
    assert Path(result["contact_sheet"]).is_file()
    assert all(
        hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path] for path in paths
    )


def test_visual_rhythm_separates_near_duplicates(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    result = build_series(paths, tmp_path / "rhythm", strategy="visual-rhythm")
    filenames = [item["filename"] for item in result["sequence"]]
    assert result["similar_pairs"]
    assert filenames[0] == "first.jpg"
    assert abs(filenames.index("third.jpg") - filenames.index("echo.jpg")) > 1
    assert not result["adjacent_similar_pairs"]
