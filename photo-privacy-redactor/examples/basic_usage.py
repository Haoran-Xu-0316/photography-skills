"""photo-privacy-redactor的用户矩形遮挡示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_privacy_redactor = import_module("photo_privacy_redactor")


def run_example(
    input_path: str | Path,
    output_directory: str | Path,
) -> dict:
    """检测人脸候选，并遮挡一个由用户确认的归一化矩形。"""

    candidates = photo_privacy_redactor.detect_face_candidates(input_path)
    redacted = photo_privacy_redactor.redact_photo(
        input_path,
        output_directory,
        rectangles=[
            {
                "left": 0.10,
                "top": 0.20,
                "right": 0.35,
                "bottom": 0.55,
                "unit": "normalized",
            }
        ],
        manual_review_confirmed=False,
    )
    return {"candidates": candidates, "redacted": redacted}

