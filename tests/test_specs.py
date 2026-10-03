"""Consistency of the spec-anchored artifacts in ``specs/`` and ``changes/``.

Constitution Art. 7: every behavior change is a proposal in ``changes/``
(proposal + delta-spec + tasks) approved before implementing.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs"
CHANGES = ROOT / "changes"

APPROVED_STATES = {"aprobada", "en curso", "implementada"}
REQUIRED_FILES = ("proposal.md", "delta-spec.md", "tasks.md")


def active_changes() -> list[Path]:
    return sorted(
        p for p in CHANGES.iterdir() if p.is_dir() and not p.name.startswith("_")
    )


def proposal_state(change: Path) -> str | None:
    text = (change / "proposal.md").read_text(encoding="utf-8")
    match = re.search(r"Estado:\s*\*\*(.+?)\*\*", text)
    return match.group(1).strip().lower() if match else None


@pytest.mark.parametrize("change", active_changes(), ids=lambda p: p.name)
def test_active_change_has_required_files(change):
    """Art. 7: each change ships proposal, delta-spec and tasks."""
    missing = [f for f in REQUIRED_FILES if not (change / f).is_file()]
    assert not missing, f"{change.name} lacks {missing}"


@pytest.mark.parametrize("change", active_changes(), ids=lambda p: p.name)
def test_active_change_is_indexed(change):
    """Art. 7: changes/README.md lists every open change."""
    index = (CHANGES / "README.md").read_text(encoding="utf-8")
    assert f"`{change.name}/`" in index


@pytest.mark.parametrize("change", active_changes(), ids=lambda p: p.name)
def test_active_change_is_approved(change):
    """Art. 7: a proposal on an integration branch is approved (review happens in its PR)."""
    assert proposal_state(change) in APPROVED_STATES


def test_constitution_is_ratified():
    """Art. 7: no amendment of the constitution is pending approval."""
    text = (SPECS / "constitution.md").read_text(encoding="utf-8")
    amendments = text.split("## Enmiendas", 1)[1].split("\n## ", 1)[0]
    rows = [r for r in amendments.splitlines() if r.startswith("| 20")]
    assert rows, "the amendments table is empty"
    assert not [r for r in rows if "pendiente" in r.lower()]


def test_readme_documents_authorize_and_read_only():
    """REQ-SRV-017: the README documents the WebSocket access controls."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in [
        "authorize=",
        "read_only=True",
        "4409",
        "1011",
        'edit_mode="EDIT"',
        "PERSPECTIVE_DEMO_READ_ONLY",
    ]:
        assert needle in readme, needle
    assert "has no authentication" not in readme


def test_changelog_lists_releases():
    """Art. 4: CHANGELOG.md records every release (Keep a Changelog)."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.2.0]" in changelog
    assert "## [0.1.0]" in changelog
    assert "### Security" in changelog


FOLDED_REQS = [f"REQ-SRV-0{n}" for n in range(10, 19)] + [
    "REQ-VER-003",
    "REQ-VER-004",
    "REQ-VER-005",
]


@pytest.mark.parametrize("req", FOLDED_REQS)
def test_prd_contains_folded_requirement(req):
    """Art. 7: implemented deltas are folded into the PRD."""
    prd = (SPECS / "prd" / "reflex-perspective.md").read_text(encoding="utf-8")
    assert f"**{req}**" in prd


def test_api_spec_read_table_matches_code():
    """REQ-SRV-013 / Art. 3: the API spec's read table is the code's table."""
    pytest.importorskip("perspective")
    from reflex_perspective import server as ps
    from reflex_perspective.viewer import PERSPECTIVE_VERSION

    api = (SPECS / "api" / "server-api-v1.md").read_text(encoding="utf-8")
    section = api.split("### 2.2", 1)[1].split("\n### ", 1)[0].split("Escrituras", 1)[0]
    documented = {int(n) for n in re.findall(r"\|\s*(\d+)\s*\|\s*`\w+_req`", section)}
    assert documented == ps.READ_VARIANTS[PERSPECTIVE_VERSION]


def test_newest_changelog_entry_is_the_package_version():
    """Art. 4/7: the version being released has the newest CHANGELOG entry."""
    tomllib = pytest.importorskip("tomllib")

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert newest and newest.group(1) == version


def test_archived_changes_are_implemented():
    """Art. 7: only implemented proposals move to changes/_archivo/."""
    archive = CHANGES / "_archivo"
    archived = sorted(p for p in archive.iterdir() if p.is_dir())
    assert archived, "no archived changes"
    for change in archived:
        assert proposal_state(change) == "implementada", change.name
