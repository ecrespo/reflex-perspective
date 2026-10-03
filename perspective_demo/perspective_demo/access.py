"""Who may use the demo's Perspective WebSocket, and what they may do.

* ``authorize``: a switch on the /server page closes the door to new viewers
  (they are refused with 4403 before any Perspective session exists).
* ``read_only``: set ``PERSPECTIVE_DEMO_READ_ONLY=1`` to refuse every write
  coming from a browser (closed with 4409); the market feed keeps writing from
  Python.

Counters come from the hook and from the library's logger, which is how an
app can get rejection metrics without extra hooks.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any

from starlette.websockets import WebSocket

READ_ONLY_ENV = "PERSPECTIVE_DEMO_READ_ONLY"
REFUSED_CODE = 4403


class Access:
    """Process-wide switch and counters the UI reads and flips."""

    accepting: bool = True
    accepted: int = 0
    refused: int = 0
    writes_refused: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.accepting = True
        cls.accepted = cls.refused = cls.writes_refused = 0


def authorize(websocket: WebSocket) -> int | None:
    """Accept new viewers unless the door is closed."""
    if Access.accepting:
        Access.accepted += 1
        return None
    Access.refused += 1
    return REFUSED_CODE


class _CountRefusedWrites(logging.Filter):
    """Counts read-only refusals and lets the record through to the console."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno == logging.WARNING and "read-only" in record.getMessage():
            Access.writes_refused += 1
        return True


_SERVER_LOGGER = logging.getLogger("reflex_perspective.server")
if not any(isinstance(f, _CountRefusedWrites) for f in _SERVER_LOGGER.filters):
    _SERVER_LOGGER.addFilter(_CountRefusedWrites())


def read_only_from_env(environ: Mapping[str, str]) -> bool:
    return environ.get(READ_ONLY_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def ws_options(environ: Mapping[str, str] = os.environ) -> dict[str, Any]:
    """Keyword options for ``ps.perspective_api`` / ``ps.mount``."""
    return {"authorize": authorize, "read_only": read_only_from_env(environ)}


READ_ONLY = read_only_from_env(os.environ)
