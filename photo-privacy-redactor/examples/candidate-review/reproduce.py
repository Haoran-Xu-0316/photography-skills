"""Fixed candidate decisions for one inspected synthetic portrait, not general automation."""
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from photo_privacy_redactor import detect_face_candidates, redact_photo


def reproduce_example(output_directory: str | Path) -> dict:
    source = SKILL / "examples/cases/portrait/input/source.png"
    detected = detect_face_candidates(source)
    # Decisions were reviewed on this exact bundled 1152x768 synthetic fixture.
    # A changed detector or fixture requires a fresh review, not ID-based guessing.
    expected = ["face-001", "face-002", "face-003"]
    boxes = [item["candidate_box"] for item in detected["candidates"]]
    reference_boxes = [[591, 98, 744, 251], [1003, 461, 1059, 517], [762, 485, 905, 628]]
    if [item["id"] for item in detected["candidates"]] != expected or boxes != reference_boxes:
        return {"status": "needs-candidate-review", "reason": "Detector output differs from the reviewed fixture", "detection": detected}
    return redact_photo(
        source, output_directory,
        candidate_decisions={"face-001": "redact", "face-002": "reject", "face-003": "reject"},
        manual_review_confirmed=False,
    )
