"""Runs the JavaScript unit tests of the React bridge (tests/js, node:test).

The bridge is bundled with esbuild (the same pinned version CI uses for its
syntax check) with React and Reflex's runtime modules stubbed out; the
Perspective packages are only imported lazily and stay external.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "custom_components" / "reflex_perspective" / "perspective_viewer.jsx"
JS = ROOT / "tests" / "js"
ESBUILD = "esbuild@0.25"

pytestmark = pytest.mark.skipif(
    not (shutil.which("node") and shutil.which("npx")), reason="node/npx not installed"
)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False, **kw
    )


def test_bridge_js_unit_tests(tmp_path):
    """REQ-VIEW-011/012: the bridge's pure helpers pass their node:test suite."""
    bundle = tmp_path / "bridge.mjs"
    built = run(
        [
            shutil.which("npx"),
            "--yes",
            ESBUILD,
            str(BRIDGE),
            "--bundle",
            "--format=esm",
            "--platform=node",
            "--loader:.jsx=jsx",
            "--log-level=warning",
            f"--alias:react={JS / 'stubs' / 'react.mjs'}",
            f"--alias:$/env.json={JS / 'stubs' / 'env.json'}",
            f"--alias:$/utils/state={JS / 'stubs' / 'state.mjs'}",
            "--external:@perspective-dev/*",
            f"--outfile={bundle}",
        ]
    )
    assert built.returncode == 0, built.stderr
    tested = run(
        [shutil.which("node"), "--test", str(JS / "bridge.test.mjs")],
        env={**os.environ, "BRIDGE_BUNDLE": bundle.as_uri()},
    )
    assert tested.returncode == 0, tested.stdout + tested.stderr
