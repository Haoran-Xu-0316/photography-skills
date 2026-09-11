"""photo-bracket-fusion的分析优先示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_bracket_fusion = import_module("photo_bracket_fusion")


def run_example(
    input_paths: list[str | Path],
    output_directory: str | Path,
    exposure_times: list[float],
) -> dict:
    """先分析包围曝光；存在阻断项时不执行融合。"""

    analysis = photo_bracket_fusion.analyze_bracket(
        input_paths,
        exposure_times=exposure_times,
    )
    if analysis["blockers"]:
        return {"analysis": analysis, "fusion": None}

    fusion = photo_bracket_fusion.fuse_bracket(
        input_paths,
        output_directory,
        exposure_times=exposure_times,
        motion_handling="reference-frame",
    )
    return {"analysis": analysis, "fusion": fusion}
