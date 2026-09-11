"""photo-print-layout的A4双栏拼版示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_print_layout = import_module("photo_print_layout")


def run_example(
    input_paths: list[str | Path],
    output_directory: str | Path,
) -> dict:
    """分析A4双栏版式，PPI合格时生成页面、PDF和清单。"""

    settings = {
        "paper_size_mm": (210, 297),
        "grid": (2, 2),
        "fit_strategy": "contain",
        "margins_mm": (15, 15, 18, 20),
        "gap_mm": 6,
        "bleed_mm": 3,
        "binding_edge": "left",
        "binding_safe_mm": 8,
        "dpi": 300,
        "minimum_ppi": 240,
    }
    plan = photo_print_layout.analyze_print_layout(input_paths, **settings)
    low_ppi = any("below minimum" in warning for warning in plan["warnings"])
    if low_ppi:
        return {"plan": plan, "layout": None}

    layout = photo_print_layout.create_print_layout(
        input_paths,
        output_directory,
        **settings,
    )
    return {"plan": plan, "layout": layout}
