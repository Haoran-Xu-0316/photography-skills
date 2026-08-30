"""photo-repair的诊断、预览和修复示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_repair = import_module("photo_repair")


def run_example(
    input_paths: list[str | Path],
    output_root: str | Path,
) -> dict:
    """使用高感预设完成诊断、首张预览和批量修复。"""

    if not input_paths:
        raise ValueError("input_paths不能为空")

    paths = [Path(path) for path in input_paths]
    root = Path(output_root)
    diagnosis = photo_repair.diagnose_photos(paths, preset="high_iso")
    preview = photo_repair.build_repair_preview(
        paths[0],
        root / "preview",
        preset="high_iso",
    )
    repaired = photo_repair.repair_photos(
        paths,
        root / "repaired",
        preset="high_iso",
    )
    return {"diagnosis": diagnosis, "preview": preview, "repaired": repaired}

