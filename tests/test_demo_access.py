"""Demo app WebSocket access options (T-006): authorize + read-only."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("perspective")

from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "perspective_demo"))

from perspective_demo import access
from reflex_perspective import server as ps


@pytest.fixture(autouse=True)
def fresh_access():
    access.Access.reset()
    yield
    access.Access.reset()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("YES", True), ("0", False), ("", False)],
)
def test_read_only_from_env(value, expected):
    """REQ-SRV-013 (demo): PERSPECTIVE_DEMO_READ_ONLY turns read-only on."""
    options = access.ws_options({access.READ_ONLY_ENV: value})
    assert options["read_only"] is expected
    assert options["authorize"] is access.authorize


def test_read_only_off_by_default():
    """REQ-SRV-017 (demo): without the variable the demo stays writable."""
    assert access.ws_options({})["read_only"] is False


def test_authorize_counts_and_refuses_when_closed():
    """REQ-SRV-011 (demo): closing the door refuses new viewers with 4403."""
    hub = ps.PerspectiveHub()
    app = hub.asgi_app("/perspective", **access.ws_options({}))
    with TestClient(app) as client:
        with client.websocket_connect("/perspective"):
            pass
        access.Access.accepting = False
        with (
            client.websocket_connect("/perspective") as ws,
            pytest.raises(WebSocketDisconnect) as exc,
        ):
            ws.receive_bytes()
    assert exc.value.code == 4403
    assert (access.Access.accepted, access.Access.refused) == (1, 1)


def test_refused_writes_are_counted_from_the_library_log():
    """REQ-SRV-014 (demo): each read-only refusal bumps the counter."""
    hub = ps.PerspectiveHub()
    app = hub.asgi_app("/perspective", **access.ws_options({access.READ_ONLY_ENV: "1"}))
    with (
        TestClient(app) as client,
        client.websocket_connect("/perspective") as ws,
        pytest.raises(WebSocketDisconnect),
    ):
        ws.send_bytes(b"\x08\x80")  # malformed frame (Art. 2 allows hand-written)
        ws.receive_bytes()
    assert access.Access.writes_refused == 1
