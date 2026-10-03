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
    assert options["on_reject"] is access.on_reject


@pytest.mark.parametrize(
    ("value", "expected"), [("3", 3), ("1", 1), ("", None), ("0", None), ("x", None)]
)
def test_max_sessions_from_env(value, expected):
    """REQ-SRV-019 (demo): PERSPECTIVE_DEMO_MAX_SESSIONS caps the hub."""
    assert (
        access.ws_options({access.MAX_SESSIONS_ENV: value})["max_sessions"] == expected
    )


def test_defaults_off():
    """REQ-SRV-017 (demo): without variables the demo is writable and uncapped."""
    options = access.ws_options({})
    assert options["read_only"] is False
    assert options["max_sessions"] is None


def connect_and_close_code(app, frame=None):
    with (
        TestClient(app) as client,
        client.websocket_connect("/perspective") as ws,
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        if frame is not None:
            ws.send_bytes(frame)
        ws.receive_bytes()
    return exc.value.code


def test_closed_door_refuses_and_is_counted():
    """REQ-SRV-011/020 (demo): closing the door refuses with 4403, counted."""
    hub = ps.PerspectiveHub()
    app = hub.asgi_app("/perspective", **access.ws_options({}))
    access.Access.accepting = False
    assert connect_and_close_code(app) == 4403
    assert access.Access.rejections == {4403: 1}


def test_refused_writes_are_counted():
    """REQ-SRV-014/020 (demo): each read-only refusal is counted by on_reject."""
    hub = ps.PerspectiveHub()
    app = hub.asgi_app("/perspective", **access.ws_options({access.READ_ONLY_ENV: "1"}))
    assert connect_and_close_code(app, b"\x08\x80") == 4409  # malformed (Art. 2)
    assert access.Access.rejections == {4409: 1}
    assert access.rejection_summary() == "4409×1"
