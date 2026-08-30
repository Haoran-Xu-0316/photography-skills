"""photo-to-3d使用用户深度图的完全离线示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_to_3d = import_module("photo_to_3d")


def run_example(
    input_path: str | Path,
    output_directory: str | Path,
    depth_map_path: str | Path,
) -> dict:
    """检查照片并利用用户深度图生成2.5D视差作品。"""

    analysis = photo_to_3d.analyze_photo(input_path)
    converted = photo_to_3d.convert_photo_to_3d(
        input_path,
        output_directory,
        mode="parallax",
        depth_map_path=depth_map_path,
        allow_model_download=False,
        parallax_strength=0.02,
    )
    return {"analysis": analysis, "converted": converted}

