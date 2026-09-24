"""Reflex custom component for Perspective (https://perspective-dev.github.io).

Quick start::

    import reflex_perspective as rp

    rp.perspective_viewer(data=State.rows, plugin="Y Bar", group_by=["Region"])

Server-hosted tables live in :mod:`reflex_perspective.server` (optional
``server`` extra, imported lazily so the client-only component has no
dependency on ``perspective-python``).
"""

from . import viewer as actions
from .viewer import (
    AGGREGATES,
    EXPORT_METHODS,
    PERSPECTIVE_VERSION,
    PLUGINS,
    THEMES,
    PerspectiveViewer,
    add_panel,
    clear,
    copy,
    download,
    export,
    perspective_viewer,
    remove,
    replace,
    reset,
    resize,
    restore,
    restore_workspace,
    save,
    save_workspace,
    table_schema,
    table_size,
    toggle_config,
    update,
)

__all__ = [
    "AGGREGATES",
    "EXPORT_METHODS",
    "PERSPECTIVE_VERSION",
    "PLUGINS",
    "THEMES",
    "PerspectiveViewer",
    "actions",
    "add_panel",
    "clear",
    "copy",
    "download",
    "export",
    "perspective_viewer",
    "remove",
    "replace",
    "reset",
    "resize",
    "restore",
    "restore_workspace",
    "save",
    "save_workspace",
    "table_schema",
    "table_size",
    "toggle_config",
    "update",
]

__version__ = "0.1.0"
