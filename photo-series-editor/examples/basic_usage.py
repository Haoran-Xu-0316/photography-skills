"""photo-series-editor的初稿与人工确认示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_series_editor = import_module("photo_series_editor")


def run_example(
    selected_paths: list[str | Path],
    draft_output_directory: str | Path,
) -> dict:
    """生成视觉节奏初稿；返回结果仍需要查看联系表。"""

    return photo_series_editor.build_series(
        selected_paths,
        draft_output_directory,
        strategy="visual-rhythm",
    )


def finalize_reviewed_example(
    reviewed_ordered_paths: list[str | Path],
    final_output_directory: str | Path,
) -> dict:
    """仅在人工看过联系表并确定顺序后生成最终清单。"""

    return photo_series_editor.build_series(
        reviewed_ordered_paths,
        final_output_directory,
        strategy="manual",
        visual_review_confirmed=True,
    )
