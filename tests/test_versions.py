"""Perspective version pins (constitution Art. 3, REQ-VER-004/005)."""

import importlib.util
import re
from pathlib import Path

import pytest

pytest.importorskip("tomllib")  # the checker runs on Python 3.11+ (CI uses 3.13)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_perspective_versions.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_perspective_versions", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_tree(root: Path, npm: str, server: str, dev: str) -> Path:
    viewer = root / "custom_components" / "reflex_perspective" / "viewer.py"
    viewer.parent.mkdir(parents=True)
    viewer.write_text(f'PERSPECTIVE_VERSION = "{npm}"\n', encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project.optional-dependencies]\n"
        f"server = [\"perspective-python=={server}; python_version >= '3.11'\"]\n"
        f'dev = ["pytest", "perspective-python=={dev}; python_version >= \'3.11\'"]\n',
        encoding="utf-8",
    )
    return root


def test_repo_pins_are_in_sync():
    """REQ-VER-004: the repository's three Perspective pins match."""
    checker = load_checker()
    assert checker.mismatch(checker.read_pins(ROOT)) is None


def test_mismatched_pins_fail_naming_all_versions(tmp_path):
    """REQ-VER-004: a mismatch fails and the error names the three versions."""
    checker = load_checker()
    root = make_tree(tmp_path, npm="5.5.0", server="5.5.1", dev="5.5.1")

    assert checker.main(root) == 1
    error = checker.mismatch(checker.read_pins(root))
    assert "5.5.0" in error
    assert error.count("5.5.1") == 2


def test_missing_pin_fails(tmp_path):
    """REQ-VER-004: a pin that cannot be read is a failure, not a pass (Art. 5)."""
    checker = load_checker()
    root = make_tree(tmp_path, npm="5.5.1", server="5.5.1", dev="5.5.1")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace("perspective-python==5.5.1", "pytest", 1)
    )

    assert checker.main(root) == 1


def test_dependabot_ignores_perspective_python():
    """REQ-VER-005: Dependabot never bumps perspective-python on its own."""
    config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*- package-ecosystem:\s*", config)
    uv = [b for b in blocks if b.startswith("uv")]
    assert len(uv) == 1
    assert re.search(
        r"ignore:\s*\n\s*- dependency-name:\s*\"?perspective-python\"?", uv[0]
    )
