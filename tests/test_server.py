"""Tests for reflex_perspective.server (requires perspective-python)."""

import asyncio
import importlib.metadata
import logging
import threading

import pytest

perspective = pytest.importorskip("perspective")

from starlette.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocket, WebSocketDisconnect  # noqa: E402

from reflex_perspective import server as ps  # noqa: E402
from reflex_perspective.viewer import PERSPECTIVE_VERSION  # noqa: E402


def make_hub():
    return ps.PerspectiveHub()


class Recorder:
    """Official ``perspective.Client`` on an in-process session that keeps every
    request frame it sends (constitution Art. 2: real protocol messages)."""

    def __init__(self):
        self.server = perspective.Server()
        self.frames: list[bytes] = []
        session = self.server.new_session(
            lambda resp: self.client.handle_response(resp)
        )

        def send(req):
            self.frames.append(bytes(req))
            session.handle_request(req)

        self.client = perspective.Client(send)

    def capture(self, fn):
        start = len(self.frames)
        fn()
        return self.frames[start:]


def official_frames():
    """``{operation: (frames, expected variant)}`` sent by the official client."""
    rec = Recorder()
    c = rec.client
    ops = {}

    def op(name, variant, fn):
        ops[name] = (rec.capture(fn), variant)

    op("make_table", 27, lambda: c.table([{"id": 1, "x": 1.0}], name="t", index="id"))
    t = c.open_table("t")
    op("get_hosted_tables", 4, c.get_hosted_table_names)
    op("size", 8, t.size)
    op("schema", 7, t.schema)
    op("validate_expressions", 9, lambda: t.validate_expressions({"e": '"x" + 1'}))
    op("make_port", 5, t.make_port)
    op("table_on_delete", 29, lambda: t.on_delete(lambda *a: None))
    view = {}
    op("view", 6, lambda: view.setdefault("v", t.view(group_by=["id"])))
    v = view["v"]
    op("to_arrow", 16, v.to_arrow)
    op("to_csv", 25, v.to_csv)
    op("to_json", 26, v.to_json)
    op("to_columns", 24, v.to_columns)
    op("dimensions", 12, v.dimensions)
    op("view_schema", 15, v.schema)
    op("get_config", 14, v.get_config)
    op("expand", 19, lambda: v.expand(0))
    op("collapse", 18, lambda: v.collapse(0))
    op("min_max", 20, lambda: v.get_min_max("x"))
    cb = {}
    op("on_update", 21, lambda: cb.setdefault("u", v.on_update(lambda *a: None)))
    op("remove_update", 22, lambda: v.remove_update(cb["u"]))
    op("on_remove", 39, lambda: cb.setdefault("r", v.on_remove(lambda *a: None)))
    op("view_on_delete", 34, lambda: v.on_delete(lambda *a: None))
    op("system_info", 17, c.system_info)
    op("view_delete", 11, v.delete)
    op("update", 33, lambda: t.update([{"id": 2, "x": 2.0}]))
    op("remove", 31, lambda: t.remove([2]))
    op("replace", 32, lambda: t.replace([{"id": 3, "x": 3.0}]))
    op("clear", 32, t.clear)
    other = {}
    op("other", 27, lambda: other.setdefault("o", c.table([{"id": 1}], name="o")))
    op("table_delete", 28, other["o"].delete)
    op("join", 38, lambda: c.join(t, c.table([{"id": 1, "y": 2}], name="p"), "id"))
    return ops


FRAMES = official_frames()
WRITES = ["update", "remove", "replace", "clear", "make_table", "join", "table_delete"]
READS = [n for n in FRAMES if n not in {*WRITES, "other"}]


def frame(name: str) -> bytes:
    """The single frame of a recorded operation (the one carrying its variant)."""
    frames, variant = FRAMES[name]
    return next(f for f in frames if ps.request_variant(f) == variant)


# Hand-written frames: only for malformed or tampered input (Art. 2).
SMUGGLED_WRITE = b"\x08\x07\x12\x01t\x42\x00" + b"\x8a\x02\x00"  # size + update
UNKNOWN_VARIANT = b"\x08\x07\x9a\x06\x00"  # field 99
MALFORMED = {
    "truncated_varint": b"\x08\x80",
    "length_overflow": b"\x08\x01\x42\x05ab",
    "unknown_wire_type": b"\x08\x01\x43",
    "variant_not_a_message": b"\x08\x01\x40\x01",
    "field_zero": b"\x02\x00",
    "no_variant": b"\x08\x01\x12\x01t",
}


def test_table_lifecycle():
    hub = make_hub()
    hub.table({"id": "integer", "v": "float"}, name="t", index="id")
    assert hub.has_table("t")
    hub.update("t", [{"id": 1, "v": 1.5}, {"id": 2, "v": 2.5}])
    hub.update("t", [{"id": 1, "v": 10.0}])  # upsert
    assert hub.size("t") == 2
    rows = hub.query("t", sort=[["id", "asc"]])
    assert rows[0]["v"] == 10.0
    hub.remove("t", [2])
    assert hub.size("t") == 1
    hub.clear("t")
    assert hub.size("t") == 0
    hub.delete_table("t")
    assert not hub.has_table("t")


def test_table_is_idempotent_and_replace():
    hub = make_hub()
    a = hub.table([{"x": 1}], name="same")
    b = hub.table([{"x": 2}, {"x": 3}], name="same")
    assert a is b and hub.size("same") == 1
    hub.table([{"x": 2}, {"x": 3}], name="same", replace=True)
    assert hub.size("same") == 2


def test_get_table_missing():
    with pytest.raises(KeyError):
        make_hub().get_table("nope")


def test_query_group_by():
    hub = make_hub()
    hub.table([{"k": "a", "v": 1}, {"k": "a", "v": 2}, {"k": "b", "v": 5}], name="g")
    rows = hub.query("g", group_by=["k"], columns=["v"], aggregates={"v": "sum"})
    totals = {tuple(r["__ROW_PATH__"]): r["v"] for r in rows}
    assert totals[()] == 8 and totals[("a",)] == 3


def test_websocket_endpoint_accepts_and_serves():
    hub = make_hub()
    hub.table([{"x": 1}], name="ws")
    app = hub.asgi_app("/perspective")
    with TestClient(app) as client, client.websocket_connect("/perspective") as ws:
        # Empty and text frames are ignored by the handler instead of reaching the engine.
        ws.send_bytes(b"")
        ws.send_text("hello")
    assert hub.size("ws") == 1


def test_mount_appends_transformer():
    class FakeApp:
        api_transformer = None

    app = FakeApp()
    hub = ps.mount(app, hub=make_hub())
    assert isinstance(hub, ps.PerspectiveHub)
    assert app.api_transformer is not None
    ps.mount(app, path="/other", hub=hub)
    assert isinstance(app.api_transformer, list) and len(app.api_transformer) == 2


@pytest.mark.asyncio
async def test_run_periodically_calls_function():
    import asyncio

    calls = []
    task = asyncio.create_task(ps.run_periodically(lambda: calls.append(1), 0.01)())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 2


def test_origin_allowed():
    assert ps.origin_allowed(None, ["http://app.test"])
    assert ps.origin_allowed("http://evil.test", ["*"])
    assert ps.origin_allowed("http://app.test", ["http://app.test/"])
    assert not ps.origin_allowed("http://evil.test", ["http://app.test"])


def test_websocket_rejects_foreign_origin():
    app = make_hub().asgi_app("/perspective", allowed_origins=["http://app.test"])
    with TestClient(app) as client:
        with client.websocket_connect(
            "/perspective", headers={"origin": "http://app.test"}
        ):
            pass
        with (
            pytest.raises(WebSocketDisconnect) as exc,
            client.websocket_connect(
                "/perspective", headers={"origin": "http://evil.test"}
            ),
        ):
            pass
        assert exc.value.code == 1008


def test_cache_drops_tables_deleted_elsewhere():
    hub = make_hub()
    hub.table([{"x": 1}], name="gone")
    hub.client.open_table("gone").delete()
    with pytest.raises(KeyError):
        hub.get_table("gone")
    hub.table([{"x": 1}, {"x": 2}], name="gone")
    assert hub.size("gone") == 2


# ------------------------------------------------------- read-only classifier
@pytest.mark.parametrize("name", list(FRAMES))
def test_request_variant_matches_official_client(name):
    """REQ-SRV-013: each official-client operation carries the expected variant."""
    frames, variant = FRAMES[name]
    assert variant in [ps.request_variant(f) for f in frames]


@pytest.mark.parametrize("name", READS)
def test_classifier_accepts_reads(name):
    """REQ-SRV-013: reads of Perspective 5.5.1 are allowed."""
    assert ps.is_read_request(frame(name))


@pytest.mark.parametrize("name", WRITES)
def test_classifier_rejects_writes(name):
    """REQ-SRV-014: writes are not reads; their names are known for logs."""
    assert not ps.is_read_request(frame(name))
    assert ps.request_variant(frame(name)) in ps.WRITE_VARIANT_NAMES


def test_classifier_rejects_smuggled_write():
    """REQ-SRV-014: a read followed by a write in one frame is rejected (A-01)."""
    assert ps.request_variant(SMUGGLED_WRITE) is None
    assert not ps.is_read_request(SMUGGLED_WRITE)


def test_classifier_rejects_unknown_variant():
    """REQ-SRV-014: a variant missing from the read table is rejected (Art. 5)."""
    assert ps.request_variant(UNKNOWN_VARIANT) == 99
    assert not ps.is_read_request(UNKNOWN_VARIANT)


@pytest.mark.parametrize("payload", MALFORMED.values(), ids=list(MALFORMED))
def test_classifier_rejects_malformed(payload):
    """REQ-SRV-014: unreadable protobuf has no variant and is not a read."""
    assert ps.request_variant(payload) is None
    assert not ps.is_read_request(payload)


def test_classifier_explicit_read_variants():
    """REQ-SRV-013: an explicit ``read_variants`` replaces the version table."""
    assert ps.is_read_request(frame("update"), read_variants={33})
    assert not ps.is_read_request(frame("size"), read_variants={33})


def test_read_variant_table_and_close_code():
    """REQ-SRV-013/014: published tables for 5.5.1 and the default close code."""
    reads = ps.READ_VARIANTS["5.5.1"]
    # delta-spec §2.2 (perspective.proto at tag v5.5.1)
    assert reads == {*range(3, 27), 29, 30, 34, 35, 36, 37, 39, 40}
    assert not reads & set(ps.WRITE_VARIANT_NAMES)
    assert set(ps.WRITE_VARIANT_NAMES) == {27, 28, 31, 32, 33, 38}
    assert ps.WRITE_CLOSE_CODE == 4409


# ------------------------------------------------------------ version contract
def test_variant_contract_matches_pinned_version():
    """REQ-VER-003: the official client of the pinned version matches the table."""
    assert importlib.metadata.version("perspective-python") == PERSPECTIVE_VERSION
    assert PERSPECTIVE_VERSION in ps.READ_VARIANTS
    reads = ps.READ_VARIANTS[PERSPECTIVE_VERSION]
    for name in READS:
        assert FRAMES[name][1] in reads, name
    for name in WRITES:
        variant = FRAMES[name][1]
        assert variant not in reads and variant in ps.WRITE_VARIANT_NAMES, name


# ------------------------------------------------------------------- authorize
class SpyServer:
    """Real ``perspective.Server`` that counts sessions created through it."""

    def __init__(self):
        self.real = perspective.Server()
        self.sessions = 0

    def new_session(self, send):
        self.sessions += 1
        return self.real.new_session(send)

    def __getattr__(self, name):
        return getattr(self.real, name)


def live_client(ws):
    """Official client speaking over a test WebSocket (responses on a thread)."""
    client = perspective.Client(lambda req: ws.send_bytes(bytes(req)))

    def reader():
        while True:
            try:
                client.handle_response(ws.receive_bytes())
            except Exception:  # noqa: BLE001 - socket closed
                return

    threading.Thread(target=reader, daemon=True).start()
    return client


def close_code(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_bytes()
    return exc.value.code


def test_authorize_rejects_before_session():
    """REQ-SRV-010/011: a refused socket is accepted, closed with the hook's
    code, and never gets a Perspective session."""
    hub = ps.PerspectiveHub(SpyServer())
    seen = []

    def deny(websocket):
        seen.append(websocket)
        return 4401

    app = hub.asgi_app("/perspective", authorize=deny)
    with TestClient(app) as client, client.websocket_connect("/perspective") as ws:
        assert close_code(ws) == 4401
    assert isinstance(seen[0], WebSocket)
    assert hub.server.sessions == 0


@pytest.mark.parametrize("asynchronous", [False, True], ids=["sync", "async"])
def test_authorize_async_and_sync(asynchronous):
    """REQ-SRV-010: sync and async hooks returning None let the session run."""

    def allow(websocket):
        return None

    async def allow_async(websocket):
        await asyncio.sleep(0)
        return None

    hub = ps.PerspectiveHub(SpyServer())
    hub.table([{"x": 1}, {"x": 2}], name="t")
    hook = allow_async if asynchronous else allow
    app = hub.asgi_app("/perspective", authorize=hook)
    with TestClient(app) as client, client.websocket_connect("/perspective") as ws:
        assert live_client(ws).open_table("t").size() == 2
    assert hub.server.sessions == 1


def test_authorize_accepts_policy_violation_code():
    """REQ-SRV-011: 1008 is a valid refusal code besides 4000-4999."""
    app = make_hub().asgi_app("/perspective", authorize=lambda ws: 1008)
    with TestClient(app) as client, client.websocket_connect("/perspective") as ws:
        assert close_code(ws) == 1008


def test_authorize_error_closes_1011(caplog):
    """REQ-SRV-012: a failing hook closes with 1011, is logged, no session."""

    def boom(websocket):
        raise RuntimeError("auth backend down")

    hub = ps.PerspectiveHub(SpyServer())
    app = hub.asgi_app("/perspective", authorize=boom)
    with (
        caplog.at_level(logging.ERROR, logger="reflex_perspective.server"),
        TestClient(app) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        assert close_code(ws) == 1011
    assert hub.server.sessions == 0
    assert any(r.exc_info for r in caplog.records)


@pytest.mark.parametrize("code", [1000, 3999, 5000, True, "4401"])
def test_authorize_invalid_code_closes_1011(code, caplog):
    """REQ-SRV-012: codes outside 4000-4999 (except 1008) close with 1011."""
    hub = ps.PerspectiveHub(SpyServer())
    app = hub.asgi_app("/perspective", authorize=lambda ws: code)
    with (
        caplog.at_level(logging.ERROR, logger="reflex_perspective.server"),
        TestClient(app) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        assert close_code(ws) == 1011
    assert hub.server.sessions == 0
    assert caplog.records


def test_origin_checked_before_authorize():
    """REQ-SRV-010 (DD-005): a foreign origin is refused before the hook runs."""
    calls = []
    app = make_hub().asgi_app(
        "/perspective",
        allowed_origins=["http://app.test"],
        authorize=lambda ws: calls.append(ws),
    )
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect(
            "/perspective", headers={"origin": "http://evil.test"}
        ),
    ):
        pass
    assert exc.value.code == 1008
    assert calls == []


# ------------------------------------------------------------------- read_only
def seeded_hub(server=None):
    """Hub with the tables the recorded frames point at (``t`` and ``o``)."""
    hub = ps.PerspectiveHub(server)
    hub.table([{"id": 1, "x": 1.0}], name="t", index="id")
    hub.table([{"id": 1}], name="o")
    hub.table([{"id": 1, "y": 2}], name="p")
    return hub


def snapshot(hub):
    names = sorted(hub.client.get_hosted_table_names())
    return names, hub.query("t", sort=[["id", "asc"]])


def read_only_app(hub, **kw):
    return hub.asgi_app("/perspective", read_only=True, **kw)


# A real read frame followed by a real write frame: protobuf merges them, the
# oneof keeps the last variant, so the engine would run the update (A-01).
SMUGGLED_REAL = frame("size") + frame("update")


def test_smuggled_frame_writes_without_read_only():
    """Control for REQ-SRV-014: the smuggled frame really is a write."""
    hub = seeded_hub()
    with (
        TestClient(hub.asgi_app("/perspective")) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        ws.send_bytes(SMUGGLED_REAL)
        ws.receive_bytes()
    assert hub.size("t") == 2


def test_read_only_allows_reads():
    """REQ-SRV-013: the official client reads, views and subscribes."""
    hub = seeded_hub(SpyServer())
    with (
        TestClient(read_only_app(hub)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        c = live_client(ws)
        assert sorted(c.get_hosted_table_names()) == ["o", "p", "t"]
        t = c.open_table("t")
        assert t.size() == 1
        assert t.schema() == {"id": "integer", "x": "float"}
        v = t.view(group_by=["id"])
        assert v.to_arrow()
        assert "x" in v.to_csv()
        v.expand(0)
        v.collapse(0)
        v.on_update(lambda *a: None)
        v.on_remove(lambda *a: None)
        v.delete()
        assert t.size() == 1  # still connected
    assert hub.server.sessions == 1


@pytest.mark.parametrize("name", WRITES)
def test_read_only_rejects_each_write(name):
    """REQ-SRV-014: every write closes with 4409 and changes nothing."""
    hub = seeded_hub()
    before = snapshot(hub)
    with (
        TestClient(read_only_app(hub)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        ws.send_bytes(frame(name))
        assert close_code(ws) == 4409
    assert snapshot(hub) == before


@pytest.mark.parametrize(
    "payload",
    [SMUGGLED_REAL, SMUGGLED_WRITE, UNKNOWN_VARIANT, *MALFORMED.values()],
    ids=["smuggled_real", "smuggled", "unknown", *MALFORMED],
)
def test_read_only_rejects_smuggled_unknown_and_malformed(payload):
    """REQ-SRV-014: anything that is not exactly one known read is refused."""
    hub = seeded_hub()
    before = snapshot(hub)
    with (
        TestClient(read_only_app(hub)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        ws.send_bytes(payload)
        assert close_code(ws) == 4409
    assert snapshot(hub) == before


def test_read_only_logs_variant_not_content(caplog):
    """REQ-SRV-014: the refusal is logged by number and name, never the frame."""
    hub = seeded_hub()
    payload = frame("update")
    with (
        caplog.at_level(logging.WARNING, logger="reflex_perspective.server"),
        TestClient(read_only_app(hub)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        ws.send_bytes(payload)
        close_code(ws)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "33" in text and "table_update_req" in text
    assert repr(payload) not in text and payload.hex() not in text


def test_read_only_custom_close_code():
    """REQ-SRV-014: ``write_close_code`` replaces 4409."""
    hub = seeded_hub()
    with (
        TestClient(read_only_app(hub, write_close_code=4403)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        ws.send_bytes(frame("update"))
        assert close_code(ws) == 4403


def test_read_only_unverified_version_fails(monkeypatch):
    """REQ-SRV-015: no verified read table -> RuntimeError before accepting."""
    monkeypatch.setattr(ps, "_installed_perspective_version", lambda: "9.9.9")
    untouched = object()  # any attribute access would raise AttributeError
    with pytest.raises(RuntimeError, match=r"9\.9\.9"):
        asyncio.run(make_hub().serve(untouched, read_only=True))


def test_read_only_unverified_version_with_read_variants_ok(monkeypatch):
    """REQ-SRV-015: an explicit ``read_variants`` allows an unverified version."""
    monkeypatch.setattr(ps, "_installed_perspective_version", lambda: "9.9.9")
    hub = seeded_hub()
    app = read_only_app(hub, read_variants=ps.READ_VARIANTS["5.5.1"])
    with TestClient(app) as client, client.websocket_connect("/perspective") as ws:
        assert live_client(ws).open_table("t").size() == 1


def test_read_only_python_writes_still_work():
    """REQ-SRV-016: read-only limits socket clients, not the backend."""
    hub = seeded_hub()
    with (
        TestClient(read_only_app(hub)) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        t = live_client(ws).open_table("t")
        hub.update("t", [{"id": 2, "x": 2.0}])
        assert t.size() == 2
        hub.clear("t")
        assert t.size() == 0


# ------------------------------------------------------------------ public API
class FakeApp:
    api_transformer = None


def test_params_pass_through_mount_and_api():
    """REQ-SRV-017: perspective_api() and mount() forward the new options."""
    hub = seeded_hub()
    api = ps.perspective_api(hub=hub, read_only=True, write_close_code=4403)
    with TestClient(api) as client, client.websocket_connect("/perspective") as ws:
        ws.send_bytes(frame("update"))
        assert close_code(ws) == 4403

    app = FakeApp()
    ps.mount(app, hub=hub, authorize=lambda ws: 4401)
    with (
        TestClient(app.api_transformer) as client,
        client.websocket_connect("/perspective") as ws,
    ):
        assert close_code(ws) == 4401
    assert hub.size("t") == 1


@pytest.mark.parametrize(
    "func",
    [
        ps.PerspectiveHub.serve,
        ps.PerspectiveHub.asgi_app,
        ps.perspective_api,
        ps.mount,
    ],
)
def test_defaults_unchanged(func):
    """REQ-SRV-017: new options are keyword-only with 0.1.0 behavior by default."""
    import inspect

    params = inspect.signature(func).parameters
    new = {
        "authorize": None,
        "read_only": False,
        "write_close_code": 4409,
        "read_variants": None,
    }
    for name, default in new.items():
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY, name
        assert params[name].default == default, name
    positional = [
        n for n, p in params.items() if p.kind is not inspect.Parameter.KEYWORD_ONLY
    ]
    assert positional[-2:] == ["executor", "allowed_origins"]


@pytest.mark.parametrize("code", [1000, 1008, 3999, 5000, True])
@pytest.mark.parametrize("build", ["asgi_app", "perspective_api", "mount"])
def test_invalid_write_close_code(build, code):
    """REQ-SRV-018: write_close_code outside 4000-4999 fails at build time."""
    hub = make_hub()
    builders = {
        "asgi_app": lambda: hub.asgi_app(read_only=True, write_close_code=code),
        "perspective_api": lambda: ps.perspective_api(
            hub=hub, read_only=True, write_close_code=code
        ),
        "mount": lambda: ps.mount(
            FakeApp(), hub=hub, read_only=True, write_close_code=code
        ),
    }
    with pytest.raises(ValueError, match="write_close_code"):
        builders[build]()


@pytest.mark.parametrize("build", ["asgi_app", "perspective_api", "mount"])
def test_read_only_unverified_version_fails_at_build(build, monkeypatch):
    """REQ-SRV-015: the version check runs when the app is built."""
    monkeypatch.setattr(ps, "_installed_perspective_version", lambda: "9.9.9")
    hub = make_hub()
    builders = {
        "asgi_app": lambda: hub.asgi_app(read_only=True),
        "perspective_api": lambda: ps.perspective_api(hub=hub, read_only=True),
        "mount": lambda: ps.mount(FakeApp(), hub=hub, read_only=True),
    }
    with pytest.raises(RuntimeError, match=r"9\.9\.9"):
        builders[build]()
    hub.asgi_app(read_only=True, read_variants={8})  # explicit table is fine


def test_classifier_is_public():
    """REQ-SRV-017: apps composing their own handler reuse the classifier."""
    for name in [
        "READ_VARIANTS",
        "WRITE_CLOSE_CODE",
        "WRITE_VARIANT_NAMES",
        "is_read_request",
        "request_variant",
    ]:
        assert name in ps.__all__
