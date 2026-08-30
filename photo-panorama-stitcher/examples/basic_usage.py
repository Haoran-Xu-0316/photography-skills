"""photo-panorama-stitcher的平面投影示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_panorama_stitcher = import_module("photo_panorama_stitcher")


def run_example(
    ordered_input_paths: list[str | Path],
    output_directory: str | Path,
) -> dict:
    """先分析空间相邻照片；存在阻断项时不进行拼接。"""

    analysis = photo_panorama_stitcher.analyze_panorama(
        ordered_input_paths,
        projection="planar",
    )
    if analysis["blockers"]:
        return {"analysis": analysis, "panorama": None}

    panorama = photo_panorama_stitcher.stitch_panorama(
        ordered_input_paths,
        output_directory,
        projection="planar",
    )
    return {"analysis": analysis, "panorama": panorama}

