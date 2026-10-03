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
