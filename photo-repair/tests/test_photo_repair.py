from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_repair import (  # noqa: E402
    build_repair_preview,
    diagnose_photos,
    repair_photos,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_noisy_photo(path: Path, seed: int = 11) -> None:
    height, width = 120, 180
    x = np.linspace(35, 215, width, dtype=np.float32)
    base = np.repeat(x[None, :, None], height, axis=0)
    base = np.repeat(base, 3, axis=2)
    rng = np.random.default_rng(seed)
    noisy = np.clip(base + rng.normal(0, 9, base.shape), 0, 255).astype(np.uint8)
    image = Image.fromarray(noisy, mode="RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((45, 28, 130, 92), outline=(245, 80, 40), width=3)
    image.save(path, quality=96)


def test_diagnosis_and_preview_keep_source_read_only(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    _make_noisy_photo(source)
    source_hash = _sha256(source)

    diagnosis = diagnose_photos(source)
    preview = build_repair_preview(source, tmp_path / "preview", crop_size=80)

    assert diagnosis["status"] == "analyzed"
    assert diagnosis["reports"][0]["resolution"] == "180x120"
    assert Path(preview["preview"]).is_file()
    assert preview["status"] == "review_required"
    assert _sha256(source) == source_hash

    with pytest.raises(FileExistsError):
        build_repair_preview(source, tmp_path / "preview", crop_size=80)


def test_repair_outputs_report_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    _make_noisy_photo(source, seed=21)
    source_hash = _sha256(source)
    output = tmp_path / "repaired"

    result = repair_photos(
        source,
        output,
        overrides={
            "vignette.enabled": False,
            "ca.enabled": False,
            "denoise.luma_method": "bilateral",
        },
    )

    report = result["reports"][0]
    assert result["status"] == "review_required"
    assert Path(report["result"]["output"]).is_file()
    exif_status = report["result"]["exif_copy_status"]
    assert exif_status in {"not_present", "preserved"} or exif_status.startswith(
        "failed:"
    )
    assert (output / "source_report.json").is_file()
    assert _sha256(source) == source_hash

    with pytest.raises(FileExistsError):
        repair_photos(source, output)


def test_duplicate_output_names_are_blocked_before_processing(tmp_path: Path) -> None:
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "same.jpg"
    second = second_dir / "same.jpg"
    _make_noisy_photo(first, seed=1)
    _make_noisy_photo(second, seed=2)

    with pytest.raises(ValueError, match="同名输出"):
        repair_photos([first, second], tmp_path / "output")
