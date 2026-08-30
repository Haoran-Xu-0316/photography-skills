"""Documentation and example checks for every photography skill."""

from __future__ import annotations

import importlib.util
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1]


def _skill_directories() -> list[Path]:
    return sorted(
        directory
        for directory in LIBRARY_ROOT.iterdir()
        if directory.is_dir() and (directory / "SKILL.md").is_file()
    )


def test_every_skill_has_reader_documentation_and_example() -> None:
    for skill_dir in _skill_directories():
        readme = skill_dir / "README.md"
        example = skill_dir / "examples" / "basic_usage.py"
        assert readme.is_file(), f"{skill_dir.name} is missing README.md"
        assert example.is_file(), f"{skill_dir.name} is missing basic_usage.py"

        readme_text = readme.read_text(encoding="utf-8")
        assert "## 功能定位" in readme_text
        assert "## 使用示例" in readme_text
        assert "[`examples/basic_usage.py`](examples/basic_usage.py)" in readme_text
        assert "[`SKILL.md`](SKILL.md)" in readme_text


def test_root_catalog_links_every_skill_and_example() -> None:
    root_readme = (LIBRARY_ROOT / "README.md").read_text(encoding="utf-8")
    for skill_dir in _skill_directories():
        name = skill_dir.name
        assert f"[`{name}`]({name}/README.md)" in root_readme
        assert f"[Python]({name}/examples/basic_usage.py)" in root_readme


def test_examples_are_importable_function_based_modules() -> None:
    for skill_dir in _skill_directories():
        example_path = skill_dir / "examples" / "basic_usage.py"
        example_text = example_path.read_text(encoding="utf-8")
        assert "argparse" not in example_text
        assert "__main__" not in example_text

        module_name = f"example_{skill_dir.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, example_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert callable(module.run_example)

