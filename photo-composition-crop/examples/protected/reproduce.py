"""Protect the observed subject extent, not merely a point of visual interest."""
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from photo_composition_crop import create_crop_set


def reproduce_case(topic: str, output_directory: str | Path) -> dict:
    choices = {
        "animal": (("1:1", "16:9"), (.17, .08, .78, .78)),
        "city": (("1:1", "16:9"), (.35, .32, .96, .78)),
        "portrait": (("1:1", "4:5"), (.40, .02, .80, .99)),
    }
    if topic not in choices:
        raise ValueError("Unknown protected crop case")
    ratios, region = choices[topic]
    return create_crop_set(
        SKILL / "examples/cases" / topic / "input/source.png",
        output_directory, aspect_ratios=ratios, protected_region=region,
    )
