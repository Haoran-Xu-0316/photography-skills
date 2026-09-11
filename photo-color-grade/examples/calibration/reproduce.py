"""Explicit calibration of known synthetic exposure and RGB gain errors."""
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from photo_color_grade import calibrate_photo


def reproduce_case(topic: str, output_directory: str | Path) -> dict:
    if topic not in {"animal", "city", "portrait"}:
        raise ValueError("Unknown bundled calibration case")
    source = Path(__file__).resolve().parent / topic / "input.png"
    return calibrate_photo(
        source, output_directory, exposure_stops=1,
        white_balance_gains=(1 / 1.15, 1, 1 / .85),
    )
