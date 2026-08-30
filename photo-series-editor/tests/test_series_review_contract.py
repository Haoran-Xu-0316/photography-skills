from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from photo_series_editor import build_series


def _photos(root: Path) -> list[Path]:
    paths = [root / "one.png", root / "two.png"]
    Image.fromarray(np.full((80, 120, 3), 40, dtype=np.uint8), mode="RGB").save(
        paths[0]
    )
    Image.fromarray(np.full((80, 120, 3), 210, dtype=np.uint8), mode="RGB").save(
        paths[1]
    )
    return paths


def test_reviewed_status_requires_manual_order(tmp_path: Path) -> None:
    paths = _photos(tmp_path)
    with pytest.raises(ValueError, match="manual"):
        build_series(
            paths,
            tmp_path / "invalid",
            strategy="visual-rhythm",
            visual_review_confirmed=True,
        )

    result = build_series(
        list(reversed(paths)),
        tmp_path / "reviewed",
        strategy="manual",
        visual_review_confirmed=True,
    )
    assert result["status"] == "series-reviewed"
    assert result["visual_review_confirmed"] is True
    assert [item["filename"] for item in result["sequence"]] == ["two.png", "one.png"]
