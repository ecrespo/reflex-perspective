"""Tests for reflex_perspective.server (requires perspective-python)."""

import pytest

perspective = pytest.importorskip("perspective")

from starlette.testclient import TestClient  # noqa: E402

from reflex_perspective import server as ps  # noqa: E402


def make_hub():
    return ps.PerspectiveHub()


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
    from starlette.websockets import WebSocketDisconnect

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
