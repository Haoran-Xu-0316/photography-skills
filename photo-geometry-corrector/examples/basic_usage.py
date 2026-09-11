"""photo-geometry-corrector的显式水平角度校正示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_geometry_corrector = import_module("photo_geometry_corrector")


def run_example(
    input_path: str | Path,
    output_directory: str | Path,
    confirmed_angle_degrees: float,
) -> dict:
    """分析几何结构，并使用人工确认角度校正水平线。"""

    analysis = photo_geometry_corrector.analyze_geometry(input_path)
    corrected = photo_geometry_corrector.correct_horizon(
        input_path,
        output_directory,
        angle_degrees=confirmed_angle_degrees,
    )
    return {"analysis": analysis, "corrected": corrected}
