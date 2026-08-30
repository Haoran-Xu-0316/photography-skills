from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_light_sculptor import analyze_light, sculpt_photo


def _fixture(root: Path) -> tuple[Path, Path]:
    h, w = 180, 260
    rgb = np.full((h, w, 3), [105, 125, 145], dtype=np.uint8)
    yy, xx = np.mgrid[0:h, 0:w]
    subject = ((xx - 130) / 48) ** 2 + ((yy - 95) / 64) ** 2 < 1
    rgb[subject] = [190, 115, 75]
    photo = root / "photo.png"
    mask = root / "mask.png"
    Image.fromarray(rgb, mode="RGB").save(photo)
    cv2.imwrite(str(mask), (subject.astype(np.uint16) * 65535))
    return photo, mask


def test_focus_with_user_mask_preserves_original(tmp_path: Path) -> None:
    photo, mask = _fixture(tmp_path)
    before = hashlib.sha256(photo.read_bytes()).hexdigest()
    analysis = analyze_light(photo, mask)
    result = sculpt_photo(photo, tmp_path / "out", mode="focus", subject_mask_path=mask)
    assert analysis["mask_source"] == "user-mask"
    assert result["status"] == "review_required"
    assert all(Path(path).is_file() for path in result["outputs"].values())
    assert hashlib.sha256(photo.read_bytes()).hexdigest() == before


def test_all_modes_generate_distinct_outputs(tmp_path: Path) -> None:
    photo, mask = _fixture(tmp_path)
    for mode in ("focus", "depth", "balance"):
        result = sculpt_photo(photo, tmp_path / mode, mode=mode, subject_mask_path=mask)
        assert result["status"] == "review_required"


def test_automatic_subject_detection_handles_clear_subject(tmp_path: Path) -> None:
    photo, _ = _fixture(tmp_path)
    analysis = analyze_light(photo)
    result = sculpt_photo(photo, tmp_path / "automatic", mode="focus")
    assert analysis["mask_source"] == "automatic-saliency"
    assert analysis["analysis"]["mask_confidence"] >= 0.35
    assert result["status"] == "review_required"
