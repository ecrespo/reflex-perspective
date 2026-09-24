"""Workspace: one <perspective-viewer> hosting several linked panels."""

from __future__ import annotations

import json

import reflex as rx

import reflex_perspective as rp

from ..data import SUPERSTORE_SCHEMA, superstore
from ..layout import card, code_json, page

VIEWER_ID = "dashboard"


def _split(orientation: str, sizes: list[float], *children: dict) -> dict:
    return {
        "type": "split-layout",
        "orientation": orientation,
        "sizes": sizes,
        "children": list(children),
    }


def _tabs(*ids: str) -> dict:
    return {"type": "tab-layout", "tabs": list(ids), "selected": 0}


SALES_DASHBOARD = {
    "active": "regions",
    "masters": ["regions"],
    "global_filters": None,
    "layout": _split(
        "horizontal",
        [0.36, 0.64],
        _tabs("regions"),
        _split(
            "vertical",
            [0.5, 0.5],
            _split("horizontal", [0.5, 0.5], _tabs("subcats"), _tabs("treemap")),
            _tabs("timeline", "orders"),
        ),
    ),
    "panels": {
        "regions": {
            "title": "Regions (master)",
            "plugin": "Datagrid",
            "group_by": ["Region", "State"],
            "columns": ["Sales", "Profit", "Quantity"],
            "sort": [["Sales", "desc"]],
            "columns_config": {
                "Profit": {"bg_mode": "gradient"},
                "Sales": {"fg_mode": "bar"},
            },
        },
        "subcats": {
            "title": "Sales by sub-category",
            "plugin": "X Bar",
            "group_by": ["Sub-Category"],
            "columns": ["Sales"],
            "sort": [["Sales", "asc"]],
        },
        "treemap": {
            "title": "Profit mix",
            "plugin": "Treemap",
            "group_by": ["Category", "Sub-Category"],
            "columns": ["Sales", "Profit"],
        },
        "timeline": {
            "title": "Monthly sales",
            "plugin": "Y Area",
            "group_by": ["month"],
            "split_by": ["Category"],
            "columns": ["Sales"],
            "expressions": {"month": "bucket(\"Order Date\", 'M')"},
        },
        "orders": {
            "title": "Orders",
            "plugin": "Datagrid",
            "columns": [
                "Order Date",
                "City",
                "Category",
                "Sub-Category",
                "Sales",
                "Profit",
            ],
            "sort": [["Order Date", "desc"]],
        },
    },
}

MAP_DASHBOARD = {
    "active": "map",
    "masters": ["segments"],
    "global_filters": None,
    "layout": _split(
        "horizontal",
        [0.3, 0.7],
        _tabs("segments"),
        _split("vertical", [0.6, 0.4], _tabs("map"), _tabs("heat")),
    ),
    "panels": {
        "segments": {
            "title": "Segments (master)",
            "plugin": "Y Bar",
            "group_by": ["Segment"],
            "columns": ["Profit"],
        },
        "map": {
            "title": "Orders on the map",
            "plugin": "Map Scatter",
            "columns": ["Longitude", "Latitude", "Profit", "Sales"],
        },
        "heat": {
            "title": "Region × Ship mode",
            "plugin": "Heatmap",
            "group_by": ["Region"],
            "split_by": ["Ship Mode"],
            "columns": ["Sales"],
        },
    },
}


class WorkspaceState(rx.State):
    rows: list[dict] = superstore(3000, seed=21)
    preset: str = "sales"
    global_filters: list = []
    panels: list = []
    active_panel: str = ""
    saved: dict = {}

    @rx.var
    def workspace(self) -> dict:
        return SALES_DASHBOARD if self.preset == "sales" else MAP_DASHBOARD

    @rx.var
    def filters_json(self) -> str:
        return json.dumps(self.global_filters, indent=2)

    @rx.var
    def saved_json(self) -> str:
        return json.dumps(self.saved, indent=2)[:6000]

    @rx.event
    def set_preset(self, value: str | list[str]):
        self.preset = value if isinstance(value, str) else value[0]
        self.global_filters = []

    @rx.event
    def on_global_filters(self, filters: list):
        self.global_filters = filters

    @rx.event
    def on_layout(self, panels: list):
        self.panels = panels

    @rx.event
    def on_active(self, panel: str):
        self.active_panel = panel or ""

    @rx.event
    def got_workspace(self, ws: dict):
        self.saved = ws or {}


def workspace_page() -> rx.Component:
    S = WorkspaceState
    return page(
        "Workspace",
        "Perspective 5 hosts multiple panels in one element (restoreWorkspace). Panels marked as masters "
        "publish their selection as global filters to every other panel — click a row in the master grid.",
        card(
            rx.flex(
                rx.segmented_control.root(
                    rx.segmented_control.item("Sales dashboard", value="sales"),
                    rx.segmented_control.item("Map dashboard", value="map"),
                    value=S.preset,
                    on_change=S.set_preset,
                ),
                rx.button(
                    rx.icon("filter-x", size=14),
                    "Clear global filters",
                    variant="soft",
                    on_click=rp.restore_workspace(VIEWER_ID, {"global_filters": None}),
                ),
                rx.button(
                    rx.icon("plus", size=14),
                    "Add panel",
                    variant="soft",
                    on_click=rp.add_panel(
                        VIEWER_ID,
                        {
                            "table": "dashboard_superstore",
                            "plugin": "Sunburst",
                            "group_by": ["Region", "Segment"],
                            "columns": ["Sales"],
                            "title": "New sunburst",
                        },
                    ),
                ),
                rx.button(
                    rx.icon("save", size=14),
                    "saveWorkspace()",
                    variant="outline",
                    on_click=rp.save_workspace(VIEWER_ID, S.got_workspace),
                ),
                rx.spacer(),
                rx.hstack(
                    rx.badge("panels: ", S.panels.length()),
                    rx.badge("active: ", S.active_panel),
                    rx.badge(
                        "global filters: ",
                        S.global_filters.length(),
                        color_scheme="orange",
                    ),
                ),
                gap="12px",
                wrap="wrap",
                align="center",
            ),
        ),
        rp.perspective_viewer(
            id=VIEWER_ID,
            data=S.rows,
            schema=SUPERSTORE_SCHEMA,
            table_name="dashboard_superstore",
            workspace=S.workspace,
            theme="Pro Light",
            settings=False,
            on_global_filter_update=S.on_global_filters,
            on_layout_update=S.on_layout,
            on_active_panel_update=S.on_active,
            height="720px",
            border_radius="12px",
            overflow="hidden",
            border=f"1px solid {rx.color('gray', 5)}",
        ),
        rx.grid(
            card(
                rx.text("on_global_filter_update", weight="bold", size="2"),
                code_json(S.filters_json),
            ),
            card(
                rx.text("saveWorkspace() → state", weight="bold", size="2"),
                code_json(S.saved_json),
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
    )
