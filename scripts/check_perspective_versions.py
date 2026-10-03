"""Fail if the Perspective pins drift apart (constitution Art. 3, REQ-VER-004).

The npm packages (``PERSPECTIVE_VERSION`` in ``viewer.py``) and
``perspective-python`` (``server`` and ``dev`` extras) speak one protobuf
protocol, so all three must be the same exact version. Run from CI::

    python scripts/check_perspective_versions.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import tomllib

VIEWER = Path("custom_components/reflex_perspective/viewer.py")


def _extra_pin(extras: dict[str, list[str]], extra: str) -> str | None:
    for requirement in extras.get(extra, []):
        match = re.match(r"\s*perspective-python\s*==\s*([^\s;,]+)", requirement)
        if match:
            return match.group(1)
    return None


def read_pins(root: Path) -> dict[str, str | None]:
    """The three pins, keyed by where they live (``None`` if not found)."""
    viewer = (root / VIEWER).read_text(encoding="utf-8")
    npm = re.search(r'^PERSPECTIVE_VERSION\s*=\s*"([^"]+)"', viewer, re.MULTILINE)
    with (root / "pyproject.toml").open("rb") as f:
        extras = tomllib.load(f)["project"]["optional-dependencies"]
    return {
        "viewer.py PERSPECTIVE_VERSION": npm.group(1) if npm else None,
        "[server] perspective-python": _extra_pin(extras, "server"),
        "[dev] perspective-python": _extra_pin(extras, "dev"),
    }


def mismatch(pins: dict[str, str | None]) -> str | None:
    """An error message naming every pin, or ``None`` when they all match."""
    values = set(pins.values())
    if None not in values and len(values) == 1:
        return None
    found = ", ".join(f"{k}={v or 'missing'}" for k, v in pins.items())
    return f"Perspective versions out of sync: {found}"


def main(root: Path) -> int:
    error = mismatch(read_pins(root))
    if error:
        print(f"::error::{error}")
        return 1
    print(f"Perspective pins in sync: {next(iter(read_pins(root).values()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parents[1]))
