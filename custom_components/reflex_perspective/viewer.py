"""Reflex wrapper for Perspective's ``<perspective-viewer>`` Custom Element.

Perspective (https://perspective-dev.github.io) is a WebAssembly-powered
analytics engine plus an interactive viewer (datagrid + WebGL charts) that is
especially well suited to large and streaming datasets.

The component supports the three data architectures described in the
Perspective docs:

* **Client-only** - the data lives in a WebWorker ``Table`` in the browser.
  Feed it with ``data=`` (rows, columns or CSV text), ``schema=`` and/or
  ``url=`` (CSV / JSON / NDJSON / Arrow). Stream with ``update_rows=`` or the
  :func:`update` action.
* **Server-only ("virtual")** - the ``Table`` lives in ``perspective-python``
  inside the Reflex backend and only the visible viewport crosses the wire.
  Use ``server_url="/perspective"`` + ``server_table="name"`` together with
  :mod:`reflex_perspective.server`.
* **Client/server replicated** - same as above with
  ``server_mode="replicated"``: the browser keeps a synced copy of the server
  table and computes views locally.
"""

from __future__ import annotations

from typing import Any, Literal

import reflex as rx
from reflex.vars import LiteralVar, Var, VarData

PERSPECTIVE_VERSION = "5.5.1"
"""npm version of the ``@perspective-dev/*`` packages bundled by this component.

Keep it aligned with the ``perspective-python`` version when using server
modes: the WebSocket protocol is versioned together.
"""

PluginName = Literal[
    "Datagrid",
    "X Bar",
    "Y Bar",
    "Y Line",
    "Y Scatter",
    "Y Area",
    "X/Y Scatter",
    "X/Y Line",
    "Density",
    "Treemap",
    "Sunburst",
    "Heatmap",
    "Candlestick",
    "OHLC",
    "Map Scatter",
    "Map Line",
    "Map Density",
]

PLUGINS: list[str] = list(PluginName.__args__)  # type: ignore[attr-defined]
"""Plugins registered by ``@perspective-dev/viewer-datagrid`` and ``-charts``."""

THEMES: list[str] = [
    "Pro Light",
    "Pro Dark",
    "Blueprint",
    "Botanical",
    "Dracula",
    "Eggplant",
    "Gruvbox Light",
    "Gruvbox Dark",
    "Ledger",
    "Monokai",
    "Nord",
    "Phosphor",
    "Solarized",
    "Solarized Dark",
    "Vaporwave",
    "Velvet",
]
"""Theme names bundled in ``@perspective-dev/viewer/dist/css/themes.css``."""

AGGREGATES: list[str] = [
    "sum",
    "sum abs",
    "sum not null",
    "abs sum",
    "avg",
    "mean",
    "mean by count",
    "weighted mean",
    "median",
    "q1",
    "q3",
    "count",
    "distinct count",
    "distinct leaf",
    "dominant",
    "unique",
    "any",
    "first",
    "last",
    "first by index",
    "last by index",
    "last minus first",
    "high",
    "low",
    "high minus low",
    "max",
    "min",
    "and",
    "or",
    "join",
    "var",
    "stddev",
    "pct sum parent",
    "pct sum total",
    "pct sum grand total",
]
"""Common aggregate names accepted in ``aggregates={column: aggregate}``."""

EXPORT_METHODS: list[str] = [
    "csv",
    "csv-all",
    "csv-selected",
    "json",
    "json-all",
    "json-selected",
    "ndjson",
    "ndjson-all",
    "ndjson-selected",
    "arrow",
    "arrow-all",
    "arrow-selected",
    "arrow-lz4",
    "arrow-lz4-all",
    "arrow-lz4-selected",
    "arrow-zstd",
    "arrow-zstd-all",
    "arrow-zstd-selected",
    "html",
    "plugin",
    "json-config",
]

EditMode = Literal[
    "READ_ONLY",
    "EDIT",
    "SELECT_COLUMN",
    "SELECT_ROW",
    "SELECT_REGION",
    "SELECT_ROW_TREE",
]


# The React bridge lives next to this file and is published as a shared asset.
_BRIDGE = rx.asset("perspective_viewer.jsx", shared=True)


def _dict_spec(detail: Var[dict[str, Any]]) -> tuple[Var[dict[str, Any]]]:
    return (detail,)


def _list_spec(items: Var[list[Any]]) -> tuple[Var[list[Any]]]:
    return (items,)


def _str_spec(value: Var[str]) -> tuple[Var[str]]:
    return (value,)


def _bool_spec(value: Var[bool]) -> tuple[Var[bool]]:
    return (value,)


class PerspectiveViewer(rx.Component):
    """A ``<perspective-viewer>`` bound to a Perspective ``Table``."""

    library = _BRIDGE.importable_path
    tag = "ReflexPerspectiveViewer"

    lib_dependencies: list[str] = [
        f"@perspective-dev/client@{PERSPECTIVE_VERSION}",
        f"@perspective-dev/server@{PERSPECTIVE_VERSION}",
        f"@perspective-dev/viewer@{PERSPECTIVE_VERSION}",
        f"@perspective-dev/viewer-datagrid@{PERSPECTIVE_VERSION}",
        f"@perspective-dev/viewer-charts@{PERSPECTIVE_VERSION}",
    ]

    # ------------------------------------------------------------ data source
    # Inline data: a list of row dicts, a dict of column lists, or CSV text.
    # Changing it calls ``table.replace()`` (the view config is preserved).
    data: Var[list[dict[str, Any]] | dict[str, list[Any]] | str]

    # Column types ("string", "integer", "float", "boolean", "date",
    # "datetime"). With ``data`` the table is created from the schema first,
    # so types are enforced instead of inferred.
    schema: Var[dict[str, str]]

    # Primary-key column. Updates with an existing key replace the row.
    index: Var[str]

    # Rolling window: keep at most this many rows (mutually exclusive with index).
    limit: Var[int]

    # Name of the table (defaults to the component id). Saved configs refer
    # to tables by name, so set it when persisting layouts.
    table_name: Var[str]

    # Fetch the data from a URL (CSV, JSON, NDJSON or Apache Arrow).
    url: Var[str]

    # Force the URL format instead of inferring it from the extension.
    url_format: Var[Literal["csv", "json", "ndjson", "arrow"]]

    # WebSocket of a perspective-python server. A path such as
    # "/perspective" is resolved against the Reflex backend URL.
    server_url: Var[str]

    # Name of the hosted table to open (defaults to the first hosted table).
    server_table: Var[str]

    # "server": virtual table, queries run in Python (default).
    # "replicated": browser keeps a synced copy and computes views locally.
    server_mode: Var[Literal["server", "replicated"]]

    # Streaming: every time this prop changes the rows are applied with
    # ``table.update()`` (upsert when ``index`` is set, append otherwise).
    update_rows: Var[list[dict[str, Any]] | dict[str, list[Any]]]

    # Streaming: every time this prop changes these primary keys are removed.
    remove_keys: Var[list[Any]]

    # ------------------------------------------------------ declarative state
    # Full ``ViewerConfigUpdate`` applied with ``restore()``. The shortcut
    # props below are merged on top of it.
    config: Var[dict[str, Any]]

    # Multi-panel workspace (``WorkspaceConfigUpdate``) applied with
    # ``restoreWorkspace()``: ``{"panels": {...}, "layout": {...}, ...}``.
    workspace: Var[dict[str, Any]]

    plugin: Var[str]
    columns: Var[list[str | None]]
    group_by: Var[list[str]]
    split_by: Var[list[str]]
    # e.g. [["Sales", ">", 100], ["Region", "in", ["East", "West"]]]
    filter: Var[list[list[Any]]]
    filter_op: Var[Literal["and", "or"]]
    # e.g. [["Profit", "desc"]]
    sort: Var[list[list[str]]]
    # {"Margin": '"Profit" / "Sales"'}
    expressions: Var[dict[str, str]]
    # {"Sales": "avg"}
    aggregates: Var[dict[str, Any]]
    group_by_depth: Var[int]
    group_rollup_mode: Var[Literal["rollup", "flat", "total"]]
    split_rollup_mode: Var[Literal["rollup", "flat"]]
    plugin_config: Var[dict[str, Any]]
    columns_config: Var[dict[str, dict[str, Any]]]
    theme: Var[str]
    title: Var[str]
    # Whether the settings sidebar is open.
    settings: Var[bool]

    # Datagrid interaction mode ("EDIT" makes cells editable).
    edit_mode: Var[EditMode]

    # ---------------------------------------------------------- render policy
    auto_size: Var[bool]
    auto_pause: Var[bool]
    # Minimum milliseconds between renders while streaming.
    throttle: Var[int]
    # {"Treemap": {"max_cells": 1_000_000, "max_columns": 1000}}
    plugin_limits: Var[dict[str, dict[str, int]]]

    # ----------------------------------------------------------------- events
    # Table loaded: {"table", "schema", "num_rows", "source"}.
    on_load: rx.EventHandler[_dict_spec]
    # The user changed the view; receives the full saved config.
    on_config_update: rx.EventHandler[_dict_spec]
    # A datapoint/cell was clicked: {"row", "column_names", "config", "panel"}.
    on_click: rx.EventHandler[_dict_spec]
    # Selection changed: {"selected", "row", "column_names",
    # "insert_filters", "remove_filters", "panel"}.
    on_select: rx.EventHandler[_dict_spec]
    # Global (cross-panel) filters changed in a multi-panel viewer.
    on_global_filter_update: rx.EventHandler[_list_spec]
    # Panels were added/removed in a multi-panel viewer.
    on_layout_update: rx.EventHandler[_list_spec]
    on_active_panel_update: rx.EventHandler[_str_spec]
    on_toggle_settings: rx.EventHandler[_bool_spec]
    # The WebSocket connection to the server was lost (auto-reconnects).
    on_disconnect: rx.EventHandler[_str_spec]
    on_error: rx.EventHandler[_str_spec]

    @classmethod
    def create(cls, *children, **props) -> PerspectiveViewer:
        """Create a Perspective viewer.

        Args:
            *children: Not supported (the viewer renders its own UI).
            **props: Component props, see the class attributes.

        Returns:
            The component.
        """
        if children:
            msg = "perspective_viewer does not accept children"
            raise ValueError(msg)
        return super().create(**props)


perspective_viewer = PerspectiveViewer.create


# --------------------------------------------------------------------------
# Imperative actions (return EventSpecs; use them in event triggers or
# return/yield them from event handlers).
# --------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """Unwrap state proxies (``MutableProxy``) into plain Python containers."""
    value = getattr(value, "__wrapped__", value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def _call(method: str, *args: Any, callback: Any = None) -> rx.event.EventSpec:
    arg_vars = [a if isinstance(a, Var) else LiteralVar.create(_plain(a)) for a in args]
    joined = ", ".join(str(v) for v in arg_vars)
    expr = f"(() => window.reflexPerspective.{method}({joined}))"
    var_data = VarData.merge(*(v._get_all_var_data() for v in arg_vars))
    return rx.call_function(Var(_js_expr=expr, _var_data=var_data), callback=callback)


def save(viewer_id: str | Var[str], callback: Any) -> rx.event.EventSpec:
    """Serialize the active panel's config and send it to ``callback``."""
    return _call("save", viewer_id, callback=callback)


def restore(viewer_id: str | Var[str], config: dict | Var) -> rx.event.EventSpec:
    """Apply a (partial) ``ViewerConfigUpdate`` to the viewer."""
    return _call("restore", viewer_id, config)


def save_workspace(viewer_id: str | Var[str], callback: Any) -> rx.event.EventSpec:
    """Serialize every panel + layout and send it to ``callback``."""
    return _call("saveWorkspace", viewer_id, callback=callback)


def restore_workspace(
    viewer_id: str | Var[str], workspace: dict | Var
) -> rx.event.EventSpec:
    """Apply a ``WorkspaceConfigUpdate`` (panels, layout, global filters...)."""
    return _call("restoreWorkspace", viewer_id, workspace)


def reset(viewer_id: str | Var[str], all: bool = False) -> rx.event.EventSpec:
    """Reset the view config (``all=True`` also drops expressions)."""
    return _call("reset", viewer_id, all)


def toggle_config(
    viewer_id: str | Var[str], force: bool | None = None
) -> rx.event.EventSpec:
    """Open/close the settings sidebar."""
    return _call("toggleConfig", viewer_id, force)


def download(viewer_id: str | Var[str], method: str = "csv") -> rx.event.EventSpec:
    """Download the current view (see ``EXPORT_METHODS``)."""
    return _call("download", viewer_id, method)


def copy(viewer_id: str | Var[str], method: str = "csv") -> rx.event.EventSpec:
    """Copy the current view to the clipboard."""
    return _call("copy", viewer_id, method)


def export(
    viewer_id: str | Var[str], callback: Any, method: str = "csv"
) -> rx.event.EventSpec:
    """Export the current view and send it to ``callback``.

    Text methods (``csv``, ``json``, ``ndjson``, ``html``, ``json-config``)
    deliver the text itself; binary ones (``arrow*``, ``plugin``) deliver a
    base64 ``data:`` URL.
    """
    return _call("export", viewer_id, method, callback=callback)


def update(viewer_id: str | Var[str], rows: list | dict | Var) -> rx.event.EventSpec:
    """Push rows straight into the viewer's table (no state round-trip)."""
    return _call("update", viewer_id, rows)


def remove(viewer_id: str | Var[str], keys: list | Var) -> rx.event.EventSpec:
    """Remove rows by primary key (the table needs an ``index``)."""
    return _call("remove", viewer_id, keys)


def replace(
    viewer_id: str | Var[str], data: list | dict | str | Var
) -> rx.event.EventSpec:
    """Replace every row of the viewer's table, keeping the schema."""
    return _call("replace", viewer_id, data)


def clear(viewer_id: str | Var[str]) -> rx.event.EventSpec:
    """Remove every row of the viewer's table."""
    return _call("clear", viewer_id)


def table_size(viewer_id: str | Var[str], callback: Any) -> rx.event.EventSpec:
    """Send the table's row count to ``callback``."""
    return _call("size", viewer_id, callback=callback)


def table_schema(viewer_id: str | Var[str], callback: Any) -> rx.event.EventSpec:
    """Send the table's schema to ``callback``."""
    return _call("schema", viewer_id, callback=callback)


def add_panel(viewer_id: str | Var[str], config: dict | Var) -> rx.event.EventSpec:
    """Add a panel to a multi-panel viewer."""
    return _call("addPanel", viewer_id, config)


def resize(viewer_id: str | Var[str]) -> rx.event.EventSpec:
    """Force a redraw (e.g. after the container was resized)."""
    return _call("resize", viewer_id)
