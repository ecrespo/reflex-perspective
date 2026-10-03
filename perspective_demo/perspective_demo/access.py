"""Who may use the demo's Perspective WebSocket, and what they may do.

* ``authorize``: a switch on the /server page closes the door to new viewers
  (they are refused with 4403 before any Perspective session exists).
* ``read_only``: set ``PERSPECTIVE_DEMO_READ_ONLY=1`` to refuse every write
  coming from a browser (closed with 4409); the market feed keeps writing from
  Python.
* ``max_sessions``: set ``PERSPECTIVE_DEMO_MAX_SESSIONS=N`` to cap the hub;
  extra tabs are refused with 4429 and keep retrying until a slot frees up.
* ``on_reject`` counts every refusal by close code for the /server page.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping
from typing import Any

from starlette.websockets import WebSocket

READ_ONLY_ENV = "PERSPECTIVE_DEMO_READ_ONLY"
MAX_SESSIONS_ENV = "PERSPECTIVE_DEMO_MAX_SESSIONS"
REFUSED_CODE = 4403


class Access:
    """Process-wide switch and counters the UI reads and flips."""

    accepting: bool = True
    rejections: Counter[int] = Counter()

    @classmethod
    def reset(cls) -> None:
        cls.accepting = True
        cls.rejections = Counter()


def authorize(websocket: WebSocket) -> int | None:
    """Accept new viewers unless the door is closed."""
    return None if Access.accepting else REFUSED_CODE


def on_reject(code: int, websocket: WebSocket) -> None:
    """Count refusals by close code (metrics hook)."""
    Access.rejections[code] += 1


def rejection_summary() -> str:
    return ", ".join(f"{code}×{n}" for code, n in sorted(Access.rejections.items()))


def read_only_from_env(environ: Mapping[str, str]) -> bool:
    return environ.get(READ_ONLY_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def max_sessions_from_env(environ: Mapping[str, str]) -> int | None:
    value = environ.get(MAX_SESSIONS_ENV, "").strip()
    return int(value) if value.isdigit() and int(value) >= 1 else None


def ws_options(environ: Mapping[str, str] = os.environ) -> dict[str, Any]:
    """Keyword options for ``ps.perspective_api`` / ``ps.mount``."""
    return {
        "authorize": authorize,
        "on_reject": on_reject,
        "read_only": read_only_from_env(environ),
        "max_sessions": max_sessions_from_env(environ),
    }


READ_ONLY = read_only_from_env(os.environ)
MAX_SESSIONS = max_sessions_from_env(os.environ)
