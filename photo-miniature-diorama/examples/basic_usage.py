"""Optional poster composition using the bundled real-photo example.

This does not generate the miniature: the image-capable agent follows SKILL.md.
Call build_example() from Python. No command-line entrypoint is provided.
"""

from pathlib import Path
import importlib.util


def build_example(output_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "miniature_poster", root / "scripts" / "compose_poster.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compose_poster(
        root / "examples" / "garden-source.jpg",
        root / "examples" / "garden-miniature.png",
        output_path,
        # Match the source photograph's 4:3 ratio without cropping or padding.
        photo_fraction=0.5625,
    )
