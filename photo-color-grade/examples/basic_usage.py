"""photo-color-grade的技术校色示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_color_grade = import_module("photo_color_grade")


def run_example(
    input_path: str | Path,
    output_root: str | Path,
) -> dict:
    """分析照片，生成技术校色预览，并写入新的最终目录。"""

    source = Path(input_path)
    root = Path(output_root)
    analysis = photo_color_grade.analyze_photo(source)
    preview = photo_color_grade.build_preview(
        source,
        root / "preview",
        mode="correct",
    )
    graded = photo_color_grade.grade_photo(
        source,
        root / "final",
        mode="correct",
    )
    return {"analysis": analysis, "preview": preview, "graded": graded}

