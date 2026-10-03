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
import importlib.metadata
import inspect
import logging
import threading
from collections.abc import (
    Awaitable,
    Callable,
    Collection,
    Iterable,
    Mapping,
    Sequence,
)
from concurrent.futures import Executor
from types import MappingProxyType
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
# WebSocket close code for "internal error" (RFC 6455 section 7.4.1).
_WS_INTERNAL_ERROR = 1011

Authorize = Callable[[WebSocket], Awaitable[int | None] | int | None]
"""Hook deciding whether a WebSocket may open a session.

Returns ``None`` to accept, or a close code (4000-4999, or 1008) to refuse.
"""

OnReject = Callable[[int, WebSocket], Awaitable[None] | None]
"""Hook called with the close code of every refusal (for metrics)."""

# Close code for "too many sessions, try again later" (max_sessions).
_WS_TOO_MANY_SESSIONS = 4429

WRITE_CLOSE_CODE = 4409
"""Default close code for a frame refused in read-only mode."""

# ``Request.client_req`` oneof variants that only read, per Perspective version
# (``rust/perspective-client/perspective.proto``). Indexed by exact version so
# an upgrade never runs read-only mode with another version's numbering.
READ_VARIANTS: Mapping[str, frozenset[int]] = MappingProxyType(
    {
        "5.5.1": frozenset(
            {
                3,  # get_features_req
                4,  # get_hosted_tables_req
                5,  # table_make_port_req (sent by the viewer on connect)
                6,  # table_make_view_req
                7,  # table_schema_req
                8,  # table_size_req
                9,  # table_validate_expr_req
                10,  # view_column_paths_req
                11,  # view_delete_req
                12,  # view_dimensions_req
                13,  # view_expression_schema_req
                14,  # view_get_config_req
                15,  # view_schema_req
                16,  # view_to_arrow_req
                17,  # server_system_info_req
                18,  # view_collapse_req
                19,  # view_expand_req
                20,  # view_get_min_max_req
                21,  # view_on_update_req
                22,  # view_remove_on_update_req
                23,  # view_set_depth_req
                24,  # view_to_columns_string_req
                25,  # view_to_csv_req
                26,  # view_to_rows_string_req
                29,  # table_on_delete_req
                30,  # table_remove_delete_req
                34,  # view_on_delete_req
                35,  # view_remove_delete_req
                36,  # view_to_ndjson_string_req
                37,  # remove_hosted_tables_update_req (sent on unmount)
                39,  # view_on_remove_req
                40,  # view_remove_on_remove_req
            }
        ),
    }
)

WRITE_VARIANT_NAMES: Mapping[int, str] = MappingProxyType(
    {
        27: "make_table_req",
        28: "table_delete_req",
        31: "table_remove_req",
        32: "table_replace_req",
        33: "table_update_req",
        38: "make_join_table_req",
    }
)
"""Known write variants, for logs."""

# ``Request`` envelope fields that are not part of the ``client_req`` oneof.
_ENVELOPE_FIELDS = frozenset({1, 2})  # msg_id, entity_id
_WIRE_VARINT, _WIRE_I64, _WIRE_LEN, _WIRE_I32 = 0, 1, 2, 5


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if pos >= len(buf) or shift > 63:
            msg = "truncated varint"
            raise ValueError(msg)
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


def request_variant(payload: bytes) -> int | None:
    """Field number of the single ``client_req`` variant of a ``Request`` frame.

    Walks every top-level protobuf tag instead of stopping at the first one:
    in a ``oneof`` the last field wins, so a read placed before a write would
    otherwise smuggle the write through. Anything that is not exactly one
    length-delimited variant besides ``msg_id``/``entity_id`` (a second field,
    an unknown wire type, a length past the end, truncation) returns ``None``.
    """
    variant: int | None = None
    pos = 0
    try:
        while pos < len(payload):
            key, pos = _read_varint(payload, pos)
            field, wire = key >> 3, key & 0x07
            if field == 0:
                return None
            if wire == _WIRE_VARINT:
                _, pos = _read_varint(payload, pos)
            elif wire == _WIRE_LEN:
                length, pos = _read_varint(payload, pos)
                pos += length
            elif wire == _WIRE_I64:
                pos += 8
            elif wire == _WIRE_I32:
                pos += 4
            else:
                return None
            if pos > len(payload):
                return None
            if field in _ENVELOPE_FIELDS:
                continue
            if variant is not None or wire != _WIRE_LEN:
                return None
            variant = field
    except ValueError:
        return None
    return variant


def _installed_perspective_version() -> str:
    return importlib.metadata.version("perspective-python")


def _verified_read_variants() -> frozenset[int]:
    """Read table of the installed ``perspective-python`` (fails closed)."""
    version = _installed_perspective_version()
    try:
        return READ_VARIANTS[version]
    except KeyError:
        msg = (
            f"read_only=True has no verified read table for perspective-python "
            f"{version} (known: {', '.join(sorted(READ_VARIANTS))}). Pass "
            "read_variants= explicitly or upgrade reflex-perspective."
        )
        raise RuntimeError(msg) from None


def _read_only_reads(
    read_only: bool, write_close_code: int, read_variants: Collection[int] | None
) -> frozenset[int] | None:
    """Validate the read-only options; the allowed reads, or ``None`` when off."""
    if not (type(write_close_code) is int and 4000 <= write_close_code <= 4999):
        msg = f"write_close_code must be in 4000-4999, got {write_close_code!r}"
        raise ValueError(msg)
    if not read_only:
        return None
    if read_variants is None:
        return _verified_read_variants()
    return frozenset(read_variants)


def is_read_request(
    payload: bytes, read_variants: Collection[int] | None = None
) -> bool:
    """Whether a ``Request`` frame is a known read (fails closed).

    Args:
        payload: A binary WebSocket frame from a Perspective client.
        read_variants: Allowed variant numbers. ``None`` uses
            :data:`READ_VARIANTS` for the installed ``perspective-python``.
    """
    allowed = _verified_read_variants() if read_variants is None else read_variants
    variant = request_variant(payload)
    return variant is not None and variant in allowed


def _valid_refusal_code(code: object) -> bool:
    return type(code) is int and (4000 <= code <= 4999 or code == _WS_POLICY_VIOLATION)


def _check_max_sessions(max_sessions: int | None) -> None:
    if max_sessions is not None and not (
        type(max_sessions) is int and max_sessions >= 1
    ):
        msg = f"max_sessions must be an int >= 1 or None, got {max_sessions!r}"
        raise ValueError(msg)


async def _notify_reject(
    on_reject: OnReject | None, code: int, websocket: WebSocket
) -> None:
    """Report a refusal; a failing hook is logged and never changes the close."""
    if on_reject is None:
        return
    try:
        result = on_reject(code, websocket)
        if inspect.isawaitable(result):
            await result
    except Exception:
        logger.exception("Perspective on_reject hook failed")


async def _run_authorize(authorize: Authorize, websocket: WebSocket) -> int | None:
    """``None`` to accept, else the close code to use (1011 if the hook fails)."""
    try:
        result = authorize(websocket)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        logger.exception("Perspective websocket authorize hook failed")
        return _WS_INTERNAL_ERROR
    if result is None:
        return None
    if not _valid_refusal_code(result):
        logger.error(
            "Perspective authorize hook returned invalid close code %r", result
        )
        return _WS_INTERNAL_ERROR
    return result


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
        self._sessions = 0

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
    @property
    def session_count(self) -> int:
        """WebSocket sessions currently open on this hub."""
        with self._lock:
            return self._sessions

    def _admit(self, max_sessions: int | None) -> bool:
        with self._lock:
            if max_sessions is not None and self._sessions >= max_sessions:
                return False
            self._sessions += 1
            return True

    def _release(self) -> None:
        with self._lock:
            self._sessions -= 1

    async def serve(
        self,
        websocket: WebSocket,
        executor: Executor | None = None,
        allowed_origins: Sequence[str] | None = None,
        *,
        authorize: Authorize | None = None,
        read_only: bool = False,
        write_close_code: int = WRITE_CLOSE_CODE,
        read_variants: Collection[int] | None = None,
        max_sessions: int | None = None,
        on_reject: OnReject | None = None,
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
            authorize: Called with the WebSocket after the ``Origin`` check and
                before any Perspective session exists (sync or async). Return
                ``None`` to accept or a close code (4000-4999, or 1008) to
                refuse: the socket is then accepted and closed with that code
                so the browser sees it (a pre-accept close becomes an HTTP 403
                and the code is lost). A hook that raises or returns another
                code closes with 1011.
            read_only: Forward only frames carrying exactly one known read
                request; anything else (writes, unknown or malformed frames)
                closes the socket with ``write_close_code``. Writes from
                Python (``hub.update``...) keep working.
            write_close_code: Close code for a refused frame (4000-4999).
            read_variants: Allowed ``Request`` variants in read-only mode.
                ``None`` uses :data:`READ_VARIANTS` for the installed
                ``perspective-python`` and raises ``RuntimeError`` if that
                version has no verified table.
            max_sessions: Cap on the sessions open on this hub (all its
                routes). Once reached, new sockets are accepted and closed
                with 4429 ("try again later") after ``authorize``.
            on_reject: Called as ``on_reject(code, websocket)`` (sync or
                async) before every refusal: 1008, ``authorize``'s code, 1011,
                ``write_close_code`` and 4429. Its errors are logged and never
                change the close.
        """
        allowed_reads = _read_only_reads(read_only, write_close_code, read_variants)
        _check_max_sessions(max_sessions)

        allowed = (
            _default_allowed_origins() if allowed_origins is None else allowed_origins
        )
        origin = websocket.headers.get("origin")
        if not origin_allowed(origin, allowed):
            logger.warning("Rejected Perspective websocket from origin %r", origin)
            await _notify_reject(on_reject, _WS_POLICY_VIOLATION, websocket)
            await websocket.close(code=_WS_POLICY_VIOLATION)
            return

        refusal = None
        if authorize is not None:
            refusal = await _run_authorize(authorize, websocket)
        if refusal is None and not self._admit(max_sessions):
            logger.warning(
                "Refused Perspective websocket: %s sessions open (max_sessions)",
                max_sessions,
            )
            refusal = _WS_TOO_MANY_SESSIONS
        if refusal is not None:
            await _notify_reject(on_reject, refusal, websocket)
            await websocket.accept()
            await websocket.close(code=refusal)
            return

        try:
            await self._run_session(
                websocket, executor, allowed_reads, write_close_code, on_reject
            )
        finally:
            self._release()

    async def _run_session(
        self,
        websocket: WebSocket,
        executor: Executor | None,
        allowed_reads: frozenset[int] | None,
        write_close_code: int,
        on_reject: OnReject | None,
    ) -> None:
        """Accept the socket and relay frames to a new Perspective session."""
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
                if allowed_reads is not None and not is_read_request(
                    payload, allowed_reads
                ):
                    variant = request_variant(payload)
                    logger.warning(
                        "Refused Perspective request in read-only mode: variant %s (%s)",
                        variant,
                        WRITE_VARIANT_NAMES.get(variant, "unknown")
                        if variant is not None
                        else "unreadable",
                    )
                    await _notify_reject(on_reject, write_close_code, websocket)
                    await websocket.close(code=write_close_code)
                    break
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
        *,
        authorize: Authorize | None = None,
        read_only: bool = False,
        write_close_code: int = WRITE_CLOSE_CODE,
        read_variants: Collection[int] | None = None,
        max_sessions: int | None = None,
        on_reject: OnReject | None = None,
    ) -> Starlette:
        """A Starlette app exposing this hub's WebSocket at ``path``.

        Pass it to ``rx.App(api_transformer=...)``; Reflex mounts itself below
        it, so all regular routes keep working. See :meth:`serve` for the
        options.

        Raises:
            ValueError: ``write_close_code`` outside 4000-4999, or
                ``max_sessions`` not an int >= 1.
            RuntimeError: ``read_only=True`` without ``read_variants`` on a
                ``perspective-python`` version with no verified read table.
        """
        _read_only_reads(read_only, write_close_code, read_variants)
        _check_max_sessions(max_sessions)

        async def endpoint(websocket: WebSocket) -> None:
            await self.serve(
                websocket,
                executor=executor,
                allowed_origins=allowed_origins,
                authorize=authorize,
                read_only=read_only,
                write_close_code=write_close_code,
                read_variants=read_variants,
                max_sessions=max_sessions,
                on_reject=on_reject,
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
    *,
    authorize: Authorize | None = None,
    read_only: bool = False,
    write_close_code: int = WRITE_CLOSE_CODE,
    read_variants: Collection[int] | None = None,
    max_sessions: int | None = None,
    on_reject: OnReject | None = None,
) -> Starlette:
    """Build the ``api_transformer`` that serves Perspective at ``path``.

    See :meth:`PerspectiveHub.serve` for the options.

    Example::

        app = rx.App(api_transformer=perspective_api(read_only=True))
    """
    return (hub or get_hub()).asgi_app(
        path=path,
        executor=executor,
        allowed_origins=allowed_origins,
        authorize=authorize,
        read_only=read_only,
        write_close_code=write_close_code,
        read_variants=read_variants,
        max_sessions=max_sessions,
        on_reject=on_reject,
    )


def mount(
    app: rx.App,
    path: str = DEFAULT_PATH,
    hub: PerspectiveHub | None = None,
    executor: Executor | None = None,
    allowed_origins: Sequence[str] | None = None,
    *,
    authorize: Authorize | None = None,
    read_only: bool = False,
    write_close_code: int = WRITE_CLOSE_CODE,
    read_variants: Collection[int] | None = None,
    max_sessions: int | None = None,
    on_reject: OnReject | None = None,
) -> PerspectiveHub:
    """Add the Perspective WebSocket to an existing ``rx.App``.

    Keeps any ``api_transformer`` already configured. See
    :meth:`PerspectiveHub.serve` for the options.

    Returns:
        The hub serving the endpoint.
    """
    the_hub = hub or get_hub()
    transformer = the_hub.asgi_app(
        path=path,
        executor=executor,
        allowed_origins=allowed_origins,
        authorize=authorize,
        read_only=read_only,
        write_close_code=write_close_code,
        read_variants=read_variants,
        max_sessions=max_sessions,
        on_reject=on_reject,
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
    "READ_VARIANTS",
    "WRITE_CLOSE_CODE",
    "WRITE_VARIANT_NAMES",
    "PerspectiveHub",
    "get_hub",
    "is_read_request",
    "mount",
    "origin_allowed",
    "perspective_api",
    "request_variant",
    "run_periodically",
]
