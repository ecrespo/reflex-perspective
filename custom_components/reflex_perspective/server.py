"""Host ``perspective-python`` tables inside the Reflex backend.

Server modes keep the data in Python and stream only what the viewer needs
over a WebSocket, which is how Perspective scales to datasets far larger than
what fits comfortably in a browser (or in Reflex state).

Requires the ``server`` extra::

    pip install "reflex-perspective[server]"

Usage::

    import reflex as rx
    import reflex_perspective as rp
    from reflex_perspective import server as ps

    hub = ps.get_hub()
    hub.table(rows, name="trades", index="id")

    app = rx.App(api_transformer=ps.perspective_api())  # ws at /perspective

    # in a page
    rp.perspective_viewer(server_url="/perspective", server_table="trades")

    # anywhere in the backend (event handlers, background tasks, lifespan tasks)
    hub.get_table("trades").update(new_rows)
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Executor
from typing import TYPE_CHECKING, Any

try:
    import perspective
except ImportError as err:  # pragma: no cover - import guard
    msg = (
        "reflex_perspective.server requires perspective-python. "
        'Install it with: pip install "reflex-perspective[server]"'
    )
    raise ImportError(msg) from err

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    import reflex as rx

logger = logging.getLogger("reflex_perspective.server")

DEFAULT_PATH = "/perspective"

# WebSocket close code for "policy violation" (RFC 6455 section 7.4.1).
_WS_POLICY_VIOLATION = 1008


def _default_allowed_origins() -> Sequence[str]:
    """Origins allowed by the Reflex config (``cors_allowed_origins``)."""
    try:
        from reflex.config import get_config

        return tuple(get_config().cors_allowed_origins or ("*",))
    except Exception:  # noqa: BLE001 - no rxconfig.py (tests, scripts)
        return ("*",)


def origin_allowed(origin: str | None, allowed: Sequence[str]) -> bool:
    """Whether a WebSocket handshake ``Origin`` header is acceptable.

    Browsers do not apply CORS to WebSockets, so without this check any page
    a user visits could open the endpoint and read/write hosted tables
    (cross-site WebSocket hijacking). Requests without an ``Origin`` header
    come from non-browser clients and are allowed.
    """
    if origin is None or "*" in allowed:
        return True
    return origin.rstrip("/") in {o.rstrip("/") for o in allowed}


class PerspectiveHub:
    """A ``perspective.Server`` plus a local client and helpers.

    Every table created through the hub is visible to all connected viewers
    by name. The hub is thread-safe (Perspective releases the GIL and guards
    its own state), so tables can be updated from event handlers, background
    tasks, lifespan tasks or plain threads.
    """

    def __init__(self, server: perspective.Server | None = None) -> None:
        """Create a hub.

        Args:
            server: An existing ``perspective.Server`` (a new one by default).
        """
        self.server = server if server is not None else perspective.Server()
        self.client = self.server.new_local_client()
        self._lock = threading.RLock()
        self._tables: dict[str, Any] = {}

    # ------------------------------------------------------------------ tables
    def table(
        self,
        data: Any,
        name: str,
        *,
        index: str | None = None,
        limit: int | None = None,
        replace: bool = False,
    ) -> Any:
        """Create (or get) a hosted table.

        Args:
            data: Anything ``perspective-python`` accepts: a schema dict
                (``{"col": "float"}``), row dicts, a dict of columns, CSV text,
                Arrow bytes, a pandas/polars DataFrame...
            name: Name used by viewers (``server_table=``) to open it.
            index: Optional primary-key column.
            limit: Optional rolling row limit.
            replace: If a table with this name exists, replace its rows with
                ``data`` instead of returning it untouched.

        Returns:
            The ``perspective.Table``.
        """
        with self._lock:
            existing = self._cached(name)
            if existing is not None:
                if replace:
                    existing.replace(data)
                return existing
            kwargs: dict[str, Any] = {"name": name}
            if index is not None:
                kwargs["index"] = index
            if limit is not None:
                kwargs["limit"] = limit
            tbl = self.client.table(data, **kwargs)
            self._tables[name] = tbl
            return tbl

    def get_table(self, name: str) -> Any:
        """Return a hosted table by name.

        Raises:
            KeyError: if no such table exists.
        """
        with self._lock:
            cached = self._cached(name)
            if cached is not None:
                return cached
        if name in self.client.get_hosted_table_names():
            tbl = self.client.open_table(name)
            with self._lock:
                self._tables[name] = tbl
            return tbl
        raise KeyError(name)

    def _cached(self, name: str) -> Any:
        """Cached handle for ``name``, dropped if the table was deleted remotely.

        Must be called with ``self._lock`` held.
        """
        tbl = self._tables.get(name)
        if tbl is not None and name not in self.client.get_hosted_table_names():
            del self._tables[name]
            return None
        return tbl

    def has_table(self, name: str) -> bool:
        """Whether a table with ``name`` is hosted."""
        return name in self.table_names()

    def table_names(self) -> list[str]:
        """Names of every hosted table."""
        return list(self.client.get_hosted_table_names())

    def delete_table(self, name: str) -> None:
        """Delete a hosted table (viewers bound to it will show an error)."""
        with self._lock:
            tbl = self._tables.pop(name, None)
        if tbl is None and name in self.table_names():
            tbl = self.client.open_table(name)
        if tbl is not None:
            tbl.delete(lazy=True)

    def update(self, name: str, data: Any, **kwargs: Any) -> None:
        """Shortcut for ``hub.get_table(name).update(data)``."""
        self.get_table(name).update(data, **kwargs)

    def remove(self, name: str, keys: Iterable[Any]) -> None:
        """Shortcut for ``hub.get_table(name).remove(keys)``."""
        self.get_table(name).remove(list(keys))

    def clear(self, name: str) -> None:
        """Remove every row of a hosted table."""
        self.get_table(name).clear()

    def size(self, name: str) -> int:
        """Row count of a hosted table."""
        return int(self.get_table(name).size())

    def query(self, name: str, **view_config: Any) -> list[dict[str, Any]]:
        """Run a one-off query and return records.

        Example::

            hub.query("trades", group_by=["symbol"], columns=["qty"])
        """
        view = self.get_table(name).view(**view_config)
        try:
            return view.to_json()
        finally:
            view.delete()

    # --------------------------------------------------------------- websocket
    async def serve(
        self,
        websocket: WebSocket,
        executor: Executor | None = None,
        allowed_origins: Sequence[str] | None = None,
    ) -> None:
        """Run a Perspective session over a Starlette WebSocket.

        Unlike the stock ``PerspectiveStarletteHandler`` this handler is safe
        when tables are updated from other threads: outgoing messages are
        always scheduled on the event loop that owns the socket.

        Args:
            websocket: The (not yet accepted) WebSocket.
            executor: Where engine requests run. ``None`` uses the event
                loop's default thread pool, so large queries never block the
                Reflex event loop.
            allowed_origins: Browser origins allowed to connect. ``None``
                reuses Reflex's ``cors_allowed_origins``; ``"*"`` allows any.
        """
        allowed = (
            _default_allowed_origins() if allowed_origins is None else allowed_origins
        )
        origin = websocket.headers.get("origin")
        if not origin_allowed(origin, allowed):
            logger.warning("Rejected Perspective websocket from origin %r", origin)
            await websocket.close(code=_WS_POLICY_VIOLATION)
            return

        loop = asyncio.get_running_loop()
        outbox: asyncio.Queue[bytes | None] = asyncio.Queue()

        def send(msg: bytes) -> None:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                outbox.put_nowait(msg)
            else:
                loop.call_soon_threadsafe(outbox.put_nowait, msg)

        await websocket.accept()
        session = self.server.new_session(send)

        async def writer() -> None:
            while True:
                msg = await outbox.get()
                if msg is None:
                    return
                await websocket.send_bytes(msg)

        writer_task = asyncio.create_task(writer())
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                payload = message.get("bytes")
                if not payload:
                    # Only binary protocol frames are meaningful; the engine
                    # aborts the process on empty input, so never forward it.
                    continue
                # Requests are awaited one at a time, so ordering is preserved.
                await loop.run_in_executor(executor, session.handle_request, payload)
        except WebSocketDisconnect:
            pass
        except Exception:  # pragma: no cover - defensive
            logger.exception("Perspective websocket session failed")
        finally:
            session.close()
            outbox.put_nowait(None)
            writer_task.cancel()

    def asgi_app(
        self,
        path: str = DEFAULT_PATH,
        executor: Executor | None = None,
        allowed_origins: Sequence[str] | None = None,
    ) -> Starlette:
        """A Starlette app exposing this hub's WebSocket at ``path``.

        Pass it to ``rx.App(api_transformer=...)``; Reflex mounts itself below
        it, so all regular routes keep working. See :meth:`serve` for
        ``executor`` and ``allowed_origins``.
        """

        async def endpoint(websocket: WebSocket) -> None:
            await self.serve(
                websocket, executor=executor, allowed_origins=allowed_origins
            )

        return Starlette(routes=[WebSocketRoute(path, endpoint)])


_DEFAULT_HUB: PerspectiveHub | None = None
_DEFAULT_LOCK = threading.Lock()


def get_hub() -> PerspectiveHub:
    """The process-wide default hub (created on first use)."""
    global _DEFAULT_HUB
    with _DEFAULT_LOCK:
        if _DEFAULT_HUB is None:
            _DEFAULT_HUB = PerspectiveHub()
        return _DEFAULT_HUB


def perspective_api(
    path: str = DEFAULT_PATH,
    hub: PerspectiveHub | None = None,
    executor: Executor | None = None,
    allowed_origins: Sequence[str] | None = None,
) -> Starlette:
    """Build the ``api_transformer`` that serves Perspective at ``path``.

    Example::

        app = rx.App(api_transformer=perspective_api())
    """
    return (hub or get_hub()).asgi_app(
        path=path, executor=executor, allowed_origins=allowed_origins
    )


def mount(
    app: rx.App,
    path: str = DEFAULT_PATH,
    hub: PerspectiveHub | None = None,
    executor: Executor | None = None,
    allowed_origins: Sequence[str] | None = None,
) -> PerspectiveHub:
    """Add the Perspective WebSocket to an existing ``rx.App``.

    Keeps any ``api_transformer`` already configured.

    Returns:
        The hub serving the endpoint.
    """
    the_hub = hub or get_hub()
    transformer = the_hub.asgi_app(
        path=path, executor=executor, allowed_origins=allowed_origins
    )
    current = app.api_transformer
    if current is None:
        app.api_transformer = transformer
    elif isinstance(current, (list, tuple)):
        app.api_transformer = [*current, transformer]
    else:
        app.api_transformer = [current, transformer]
    return the_hub


def run_periodically(
    func: Callable[[], Any],
    interval: float,
) -> Callable[[], Any]:
    """Wrap ``func`` as a Reflex lifespan task that runs every ``interval`` s.

    Handy for feeding a hosted table::

        app.register_lifespan_task(run_periodically(tick, 0.25))
    """

    async def _task() -> None:
        while True:
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("periodic perspective task failed")
            await asyncio.sleep(interval)

    _task.__name__ = getattr(func, "__name__", "perspective_periodic_task")
    return _task


__all__ = [
    "DEFAULT_PATH",
    "PerspectiveHub",
    "get_hub",
    "mount",
    "origin_allowed",
    "perspective_api",
    "run_periodically",
]
