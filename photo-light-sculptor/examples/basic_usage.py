"""photo-light-sculptor的局部光影示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_light_sculptor = import_module("photo_light_sculptor")


def run_example(
    input_path: str | Path,
    output_directory: str | Path,
    subject_mask_path: str | Path | None = None,
) -> dict:
    """分析主体蒙版并以focus模式生成局部光影结果。"""

    analysis = photo_light_sculptor.analyze_light(
        input_path,
        subject_mask_path=subject_mask_path,
    )
    sculpted = photo_light_sculptor.sculpt_photo(
        input_path,
        output_directory,
        mode="focus",
        strength=1.0,
        subject_mask_path=subject_mask_path,
    )
    return {"analysis": analysis, "sculpted": sculpted}

