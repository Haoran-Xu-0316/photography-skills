from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = SKILL_ROOT / "assets" / "pdf-template" / "build_pdf_template.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("standard_pdf_builder", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_html_template_has_no_machine_specific_runtime_reference() -> None:
    template = (
        SKILL_ROOT / "assets" / "html-template" / "standard-html-template.html"
    ).read_text(encoding="utf-8")
    assert "/Users/" not in template
    assert "conda activate" not in template
    assert "https://" not in template
    assert "http://" not in template


def test_pdf_builder_requires_explicit_overwrite(tmp_path: Path) -> None:
    builder = _load_builder()
    destination = tmp_path / "existing.pdf"
    destination.write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="默认不覆盖"):
        builder.build(destination)


def test_pdf_builder_exposes_cross_platform_font_override() -> None:
    builder = _load_builder()
    parameter_names = builder.build.__annotations__
    assert "font_sources" in parameter_names
    assert {"CN_TITLE", "CN_BODY", "CN_BOLD", "EN_BODY", "EN_BOLD", "NUM"} == set(
        builder.FONT_CHAIN
    )
