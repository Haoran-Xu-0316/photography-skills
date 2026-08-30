from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import photo_privacy_redactor as redactor


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> Path:
    array = np.full((90, 140, 3), (210, 180, 150), dtype=np.uint8)
    array[15:75, 20:120] = (90, 140, 190)
    Image.fromarray(array, mode="RGB").save(path)
    return path


def _candidate() -> list[dict[str, object]]:
    return [
        {
            "id": "face-001",
            "detector": "test-detector",
            "candidate_box": [40, 20, 70, 55],
            "suggested_redaction_box": [35, 12, 75, 64],
            "status": "pending",
        }
    ]


def _scan(
    candidates: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    return candidates, {"available": True, "name": "test-detector", "reason": None}


def test_actual_candidate_scanner_returns_review_only_report(tmp_path: Path) -> None:
    source = _source(tmp_path / "scanner.png")
    result = redactor.detect_face_candidates(source)
    assert result["candidate_only"] is True
    assert result["input_sha256"] == _hash(source)
    assert isinstance(result["candidates"], list)
    assert isinstance(result["face_detector"]["available"], bool)
    if not result["face_detector"]["available"]:
        assert result["face_detector"]["reason"]


def test_user_rectangle_is_opaque_and_original_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    before = _hash(source)
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan([]))
    result = redactor.redact_photo(
        source,
        tmp_path / "out",
        rectangles=[
            {
                "left": 0.2,
                "top": 0.25,
                "right": 0.5,
                "bottom": 0.75,
                "unit": "normalized",
            }
        ],
    )
    with Image.open(result["redacted_output"]) as image:
        pixels = np.asarray(image.convert("RGB"))
    assert np.all(pixels[30:65, 30:65] == 0)
    assert _hash(source) == before
    assert result["status"] == "needs-manual-review"
    assert result["metadata_action"] == "preserved-with-orientation-normalized-not-reviewed"


def test_unconfirmed_face_candidate_is_not_redacted_or_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan(_candidate()))
    result = redactor.redact_photo(source, tmp_path / "pending")
    with Image.open(result["mask_output"]) as image:
        mask = np.asarray(image)
    assert not mask.any()
    assert result["status"] == "needs-candidate-review"
    assert result["pending_candidate_ids"] == ["face-001"]


def test_confirmed_candidate_requires_manual_missed_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan(_candidate()))
    result = redactor.redact_photo(
        source,
        tmp_path / "confirmed",
        candidate_decisions={"face-001": "redact"},
    )
    with Image.open(result["mask_output"]) as image:
        mask = np.asarray(image)
    assert np.all(mask[12:64, 35:75] == 255)
    assert result["status"] == "needs-manual-review"


def test_resolved_candidates_and_manual_confirmation_have_reviewed_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan(_candidate()))
    result = redactor.redact_photo(
        source,
        tmp_path / "reviewed",
        candidate_decisions={"face-001": "reject"},
        manual_review_confirmed=True,
    )
    assert result["status"] == "content-redaction-reviewed"
    assert result["covered_pixels"] == 0
    assert not result["manual_missed_review_required"]


def test_user_mask_and_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    user_mask = np.zeros((45, 70), dtype=np.uint8)
    user_mask[10:30, 20:50] = 255
    mask_path = tmp_path / "mask.png"
    Image.fromarray(user_mask, mode="L").save(mask_path)
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan([]))
    output_dir = tmp_path / "masked"
    result = redactor.redact_photo(source, output_dir, mask_paths=[mask_path])
    assert result["covered_pixels"] > 0
    with pytest.raises(FileExistsError):
        redactor.redact_photo(source, output_dir, mask_paths=[mask_path])


def test_output_normalizes_exif_orientation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "rotated.jpg"
    image = Image.new("RGB", (80, 40), (120, 150, 180))
    exif = image.getexif()
    exif[274] = 6
    image.save(source, exif=exif)
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan([]))
    result = redactor.redact_photo(
        source,
        tmp_path / "rotated-output",
        manual_review_confirmed=True,
    )
    with Image.open(result["redacted_output"]) as output:
        assert output.size == (40, 80)
        assert output.getexif().get(274) == 1


def test_unknown_or_invalid_candidate_decision_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path / "photo.png")
    monkeypatch.setattr(redactor, "_detect_candidates", lambda _rgb: _scan(_candidate()))
    with pytest.raises(ValueError, match="未知候选"):
        redactor.redact_photo(
            source,
            tmp_path / "unknown",
            candidate_decisions={"face-999": "redact"},
        )
    with pytest.raises(ValueError, match="只接受"):
        redactor.redact_photo(
            source,
            tmp_path / "invalid",
            candidate_decisions={"face-001": "blur"},  # type: ignore[dict-item]
        )
