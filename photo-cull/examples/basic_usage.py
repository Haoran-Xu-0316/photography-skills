"""photo-cull的安全基础示例，只生成报告，不写XMP。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_cull = import_module("photo_cull")


def run_example(
    input_directory: str | Path,
    output_directory: str | Path,
) -> dict:
    """分析照片并写入新的报告目录，不创建XMP边车文件。"""

    return photo_cull.analyze_photos(
        Path(input_directory),
        Path(output_directory),
        preset="landscape",
        jobs=1,
    )

