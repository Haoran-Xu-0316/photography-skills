"""photo-focus-stacker的分析优先示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_focus_stacker = import_module("photo_focus_stacker")


def run_example(
    input_paths: list[str | Path],
    output_directory: str | Path,
) -> dict:
    """先分析焦点序列；存在阻断项时不执行合成。"""

    analysis = photo_focus_stacker.analyze_focus_stack(input_paths)
    if analysis["blockers"]:
        return {"analysis": analysis, "stack": None}

    stack = photo_focus_stacker.stack_focus(
        input_paths,
        output_directory,
        reference_index=None,
        blend_radius=7,
    )
    return {"analysis": analysis, "stack": stack}
