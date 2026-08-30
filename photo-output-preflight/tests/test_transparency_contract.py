from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_output_preflight import inspect_delivery, prepare_web_copies


def test_palette_transparency_is_detected_and_preserved(tmp_path: Path) -> None:
    source = tmp_path / "palette.png"
    image = Image.new("P", (1400, 900), color=1)
    image.putpalette([0, 0, 0, 220, 80, 30] + [0, 0, 0] * 254)
    image.info["transparency"] = 0
    image.save(source, transparency=0)

    inspection = inspect_delivery([source], tmp_path / "inspection", target="web")
    issues = {item["code"] for item in inspection["files"][0]["issues"]}
    assert inspection["files"][0]["has_alpha"] is True
    assert "web-transparency-review" in issues

    result = prepare_web_copies([source], tmp_path / "exports", long_edge=900)
    output = Path(result["exports"][0]["output"])
    assert output.suffix == ".png"
    assert result["exports"][0]["has_alpha"] is True
