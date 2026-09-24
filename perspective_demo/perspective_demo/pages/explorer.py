"""Explorer: client-only table driven by Reflex state (declarative props)."""

from __future__ import annotations

import json

import reflex as rx

import reflex_perspective as rp

from ..data import SUPERSTORE_SCHEMA, superstore
from ..layout import card, code_json, page

DIMENSIONS = [
    "Region",
    "Category",
    "Sub-Category",
    "Segment",
    "Ship Mode",
    "State",
    "City",
]
MEASURES = ["Sales", "Profit", "Quantity", "Discount"]
NONE = "(none)"


class ExplorerState(rx.State):
    rows: list[dict] = superstore(3000)
    plugin: str = "Y Bar"
    theme: str = "Pro Light"
    group_by: list[str] = ["Region"]
    split_by: str = "Category"
    columns: list[str] = ["Sales"]
    aggregate: str = "sum"
    region: str = "All"
    min_sales: int = 0
    settings: bool = False

    last_event: str = "—"
    event_payload: dict = {}
    viewer_config: dict = {}
    loaded: dict = {}

    @rx.var
    def split_list(self) -> list[str]:
        return [] if self.split_by == NONE else [self.split_by]

    @rx.var
    def filters(self) -> list[list]:
        out: list[list] = []
        if self.region != "All":
            out.append(["Region", "==", self.region])
        if self.min_sales > 0:
            out.append(["Sales", ">=", self.min_sales])
        return out

    @rx.var
    def aggregates(self) -> dict[str, str]:
        return dict.fromkeys(self.columns, self.aggregate)

    @rx.var
    def payload_json(self) -> str:
        return json.dumps(self.event_payload, indent=2, default=str)

    @rx.var
    def config_json(self) -> str:
        return json.dumps(self.viewer_config, indent=2, default=str)

    @rx.event
    def set_plugin(self, value: str):
        self.plugin = value

    @rx.event
    def set_theme(self, value: str):
        self.theme = value

    @rx.event
    def set_split_by(self, value: str):
        self.split_by = value

    @rx.event
    def set_aggregate(self, value: str):
        self.aggregate = value

    @rx.event
    def set_region(self, value: str):
        self.region = value

    @rx.event
    def set_settings(self, value: bool):
        self.settings = value

    def toggle_group(self, dim: str, checked: bool):
        if checked and dim not in self.group_by:
            self.group_by = [*self.group_by, dim]
        elif not checked:
            self.group_by = [d for d in self.group_by if d != dim]

    def toggle_column(self, col: str, checked: bool):
        if checked and col not in self.columns:
            self.columns = [*self.columns, col]
        elif not checked and len(self.columns) > 1:
            self.columns = [c for c in self.columns if c != col]

    def set_min_sales_list(self, value: list[int | float]):
        self.min_sales = int(value[0])

    def on_load(self, info: dict):
        self.loaded = info

    def on_click(self, detail: dict):
        self.last_event = "on_click"
        self.event_payload = detail

    def on_select(self, detail: dict):
        self.last_event = "on_select"
        self.event_payload = detail

    def on_config_update(self, config: dict):
        self.viewer_config = config

    def reshuffle(self):
        import random

        self.rows = superstore(3000, seed=random.randint(1, 10_000))

    def reset_controls(self):
        self.plugin = "Y Bar"
        self.group_by = ["Region"]
        self.split_by = "Category"
        self.columns = ["Sales"]
        self.aggregate = "sum"
        self.region = "All"
        self.min_sales = 0


def _labeled(label, control: rx.Component) -> rx.Component:
    head = (
        label
        if isinstance(label, rx.Component)
        else rx.text(label, size="1", weight="bold", color=rx.color("gray", 11))
    )
    return rx.vstack(head, control, spacing="1")


def controls() -> rx.Component:
    S = ExplorerState
    return card(
        rx.flex(
            _labeled(
                "Plugin",
                rx.select(
                    rp.PLUGINS[:14], value=S.plugin, on_change=S.set_plugin, size="2"
                ),
            ),
            _labeled(
                "Theme",
                rx.select(rp.THEMES, value=S.theme, on_change=S.set_theme, size="2"),
            ),
            _labeled(
                "Split by",
                rx.select(
                    [NONE, *DIMENSIONS],
                    value=S.split_by,
                    on_change=S.set_split_by,
                    size="2",
                ),
            ),
            _labeled(
                "Aggregate",
                rx.select(
                    [
                        "sum",
                        "avg",
                        "count",
                        "median",
                        "max",
                        "min",
                        "stddev",
                        "distinct count",
                    ],
                    value=S.aggregate,
                    on_change=S.set_aggregate,
                    size="2",
                ),
            ),
            _labeled(
                "Region filter",
                rx.select(
                    ["All", "East", "West", "Central", "South"],
                    value=S.region,
                    on_change=S.set_region,
                    size="2",
                ),
            ),
            _labeled(
                rx.text(
                    "Sales ≥ ",
                    S.min_sales,
                    size="1",
                    weight="bold",
                    color=rx.color("gray", 11),
                ),
                rx.slider(
                    default_value=[0],
                    min=0,
                    max=2000,
                    step=50,
                    on_value_commit=S.set_min_sales_list,
                    width="160px",
                ),
            ),
            _labeled(
                "Settings panel",
                rx.switch(checked=S.settings, on_change=S.set_settings),
            ),
            gap="18px",
            wrap="wrap",
            align="end",
        ),
        rx.flex(
            rx.text("Group by", size="1", weight="bold", color=rx.color("gray", 11)),
            *[
                rx.checkbox(
                    d,
                    checked=S.group_by.contains(d),
                    on_change=lambda c, d=d: S.toggle_group(d, c),
                )
                for d in DIMENSIONS
            ],
            rx.separator(orientation="vertical"),
            rx.text("Columns", size="1", weight="bold", color=rx.color("gray", 11)),
            *[
                rx.checkbox(
                    m,
                    checked=S.columns.contains(m),
                    on_change=lambda c, m=m: S.toggle_column(m, c),
                )
                for m in MEASURES
            ],
            rx.spacer(),
            rx.button(
                rx.icon("shuffle", size=14),
                "New data",
                size="1",
                variant="soft",
                on_click=S.reshuffle,
            ),
            rx.button(
                rx.icon("rotate-ccw", size=14),
                "Reset",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=S.reset_controls,
            ),
            gap="14px",
            wrap="wrap",
            align="center",
            margin_top="14px",
        ),
    )


def explorer() -> rx.Component:
    S = ExplorerState
    return page(
        "Explorer",
        "Client-only mode: 3,000 rows from Reflex state loaded into a WebWorker table. "
        "Every control is a plain Reflex prop mapped to restore(); interact with the chart to fire events.",
        controls(),
        rp.perspective_viewer(
            id="explorer",
            data=S.rows,
            schema=SUPERSTORE_SCHEMA,
            index="Row ID",
            table_name="explorer_superstore",
            plugin=S.plugin,
            theme=S.theme,
            group_by=S.group_by,
            split_by=S.split_list,
            columns=S.columns,
            aggregates=S.aggregates,
            filter=S.filters,
            sort=[["Sales", "desc"]],
            settings=S.settings,
            on_load=S.on_load,
            on_click=S.on_click,
            on_select=S.on_select,
            on_config_update=S.on_config_update,
            on_toggle_settings=S.set_settings,
            height="560px",
            border_radius="12px",
            overflow="hidden",
            border=f"1px solid {rx.color('gray', 5)}",
        ),
        rx.grid(
            card(
                rx.hstack(
                    rx.icon("mouse-pointer-click", size=16),
                    rx.text(
                        "Last event: ", rx.code(S.last_event), size="2", weight="bold"
                    ),
                ),
                rx.text(
                    "Click a bar or a grid cell.",
                    size="1",
                    color=rx.color("gray", 10),
                    margin_bottom="8px",
                ),
                code_json(S.payload_json),
            ),
            card(
                rx.hstack(
                    rx.icon("settings-2", size=16),
                    rx.text("on_config_update → state", size="2", weight="bold"),
                    rx.spacer(),
                    rx.badge(
                        S.loaded["num_rows"].to(str),
                        " rows · ",
                        S.loaded["source"].to(str),
                    ),
                ),
                rx.text(
                    "The viewer's full saved config after every change.",
                    size="1",
                    color=rx.color("gray", 10),
                    margin_bottom="8px",
                ),
                code_json(S.config_json),
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
    )
