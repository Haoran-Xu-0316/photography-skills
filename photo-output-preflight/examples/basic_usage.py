"""photo-output-preflight的网页交付示例。"""

import sys
from importlib import import_module
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
photo_output_preflight = import_module("photo_output_preflight")


def run_example(
    input_paths: list[str | Path],
    output_root: str | Path,
) -> dict:
    """先检查网页交付条件，通过后再生成最长边2400像素的副本。"""

    root = Path(output_root)
    report = photo_output_preflight.inspect_delivery(
        input_paths,
        root / "inspection",
        target="web",
    )
    exports = None
    if report["status"] != "blocked":
        exports = photo_output_preflight.prepare_web_copies(
            input_paths,
            root / "copies",
            long_edge=2400,
            remove_gps=True,
        )
    return {"report": report, "exports": exports}
