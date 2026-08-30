"""Cross-runtime structural checks for the self-authored skill library."""

from __future__ import annotations

import re
from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1]
OWN_SKILLS = {
    "photo-bracket-fusion",
    "photo-color-grade",
    "photo-composition-crop",
    "photo-cull",
    "photo-focus-stacker",
    "photo-geometry-corrector",
    "photo-light-sculptor",
    "photo-output-preflight",
    "photo-panorama-stitcher",
    "photo-print-layout",
    "photo-privacy-redactor",
    "photo-repair",
    "photo-series-editor",
    "photo-to-3d",
    "standard-format",
}
VENDOR_TOKENS = (
    "codex",
    "openai",
    "chatgpt",
    "claude",
    "gemini",
    "image_gen",
    "referenced_image_paths",
    "num_last_images_to_include",
)
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt"}


def _skill_directories() -> list[Path]:
    return sorted(
        directory
        for directory in LIBRARY_ROOT.iterdir()
        if directory.is_dir() and (directory / "SKILL.md").is_file()
    )


def _frontmatter_value(text: str, key: str) -> str:
    if not text.startswith("---\n"):
        raise AssertionError("SKILL.md must begin with YAML frontmatter")
    sections = text.split("\n---\n", 1)
    if len(sections) != 2:
        raise AssertionError("SKILL.md frontmatter is not closed")
    frontmatter = sections[0]
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"SKILL.md frontmatter is missing {key}")
    return match.group(1).strip().strip('"\'')


def _core_text_files(skill_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in skill_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and "agents" not in path.relative_to(skill_dir).parts
        and "tests" not in path.relative_to(skill_dir).parts
        and "__pycache__" not in path.parts
    )


def test_inventory_is_exactly_the_self_authored_library() -> None:
    assert {directory.name for directory in _skill_directories()} == OWN_SKILLS


def test_skill_entrypoints_follow_the_portable_common_subset() -> None:
    for skill_dir in _skill_directories():
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        name = _frontmatter_value(text, "name")
        description = _frontmatter_value(text, "description")

        assert name == skill_dir.name
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        assert 1 <= len(name) <= 64
        assert 1 <= len(description) <= 1024
        assert re.search(r"^metadata:\n  runtime:\s*\S.+$", text, re.MULTILINE)
        assert "## 运行契约" in text
        assert len(text.splitlines()) <= 500


def test_generic_core_has_no_vendor_or_machine_binding() -> None:
    forbidden_paths = ("/Users/", "~/.codex", "~/.claude", "~/.gemini")
    for skill_dir in _skill_directories():
        for path in _core_text_files(skill_dir):
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            for token in VENDOR_TOKENS:
                assert token not in lowered, f"{path} contains vendor token {token}"
            for fragment in forbidden_paths:
                assert fragment not in text, f"{path} contains machine path {fragment}"


def test_referenced_resources_exist() -> None:
    resource_pattern = re.compile(
        r"(?P<path>(?:scripts|references|assets)/[A-Za-z0-9_.-]+"
        r"(?:/[A-Za-z0-9_.-]+)*)"
    )
    for skill_dir in _skill_directories():
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for match in resource_pattern.finditer(text):
            relative_path = match.group("path")
            assert (skill_dir / relative_path).exists(), (
                f"{skill_dir.name} references missing resource {relative_path}"
            )


def test_scripted_skills_declare_dependencies() -> None:
    for skill_dir in _skill_directories():
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            requirements = skill_dir / "requirements.txt"
            assert requirements.is_file()
            assert requirements.read_text(encoding="utf-8").strip()


def test_optional_openai_adapter_does_not_define_core_behavior() -> None:
    for skill_dir in _skill_directories():
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        assert "agents/openai.yaml" not in skill_text

        adapter = skill_dir / "agents" / "openai.yaml"
        if not adapter.is_file():
            continue
        adapter_text = adapter.read_text(encoding="utf-8")
        assert "display_name:" in adapter_text
        assert "short_description:" in adapter_text
        assert f"${skill_dir.name}" in adapter_text
