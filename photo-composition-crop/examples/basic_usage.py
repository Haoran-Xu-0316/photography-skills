"""photo-composition-crop的多比例裁切示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_composition_crop = import_module("photo_composition_crop")


def run_example(
    input_path: str | Path,
    output_directory: str | Path,
    focus_point: tuple[float, float] | None = None,
) -> dict:
    """分析构图并生成1:1、4:5和16:9三种裁切草案。"""

    analysis = photo_composition_crop.analyze_composition(
        input_path,
        focus_point=focus_point,
    )
    crops = photo_composition_crop.create_crop_set(
        input_path,
        output_directory,
        aspect_ratios=("1:1", "4:5", "16:9"),
        focus_point=focus_point,
    )
    return {"analysis": analysis, "crops": crops}

