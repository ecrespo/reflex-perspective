"""Actions & events: the imperative API exposed to Python + an editable grid."""

from __future__ import annotations

import json
import random
from datetime import datetime

import reflex as rx

import reflex_perspective as rp

from ..layout import card, code_json, page

VIEWER_ID = "inventory"

PRODUCTS = ["Widget", "Gadget", "Doohickey", "Sprocket", "Gizmo", "Thingamajig"]
WAREHOUSES = ["Caracas", "Madrid", "Barcelona", "Bogotá", "Lima"]

SCHEMA = {
    "sku": "string",
    "product": "string",
    "warehouse": "string",
    "stock": "integer",
    "unit_cost": "float",
    "reorder": "boolean",
    "updated": "date",
}


def inventory(n: int = 120, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        stock = rng.randint(0, 500)
        rows.append(
            {
                "sku": f"SKU-{i + 1:04d}",
                "product": rng.choice(PRODUCTS),
                "warehouse": rng.choice(WAREHOUSES),
                "stock": stock,
                "unit_cost": round(rng.uniform(1, 90), 2),
                "reorder": stock < 60,
                "updated": f"2026-0{rng.randint(1, 9)}-{rng.randint(10, 28)}",
            }
        )
    return rows


class ApiState(rx.State):
    rows: list[dict] = inventory()
    edit_mode: str = "EDIT"
    events: list[str] = []
    saved_config: dict = {}
    layouts: dict[str, dict] = {}
    layout_name: str = "my layout"
    exported: str = ""
    schema_text: str = ""
    size: int = 0
    next_sku: int = 121
    selected_sku: str = ""

    @rx.var
    def layout_names(self) -> list[str]:
        return list(self.layouts)

    @rx.var
    def saved_json(self) -> str:
        return json.dumps(self.saved_config, indent=2)

    def _log(self, kind: str, payload) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        text = json.dumps(payload, default=str)
        self.events = [f"{stamp}  {kind}  {text[:220]}", *self.events][:14]

    @rx.event
    def set_edit_mode(self, value: str):
        self.edit_mode = value

    @rx.event
    def set_layout_name(self, value: str):
        self.layout_name = value

    @rx.event
    def on_click(self, detail: dict):
        self.selected_sku = str((detail.get("row") or {}).get("sku") or "")
        self._log("on_click", detail.get("row"))

    @rx.event
    def on_select(self, detail: dict):
        self._log(
            "on_select", {k: detail.get(k) for k in ("selected", "insert_filters")}
        )

    @rx.event
    def on_config_update(self, config: dict):
        self._log(
            "on_config_update",
            {k: config.get(k) for k in ("plugin", "group_by", "sort", "filter")},
        )

    @rx.event
    def on_toggle_settings(self, value: bool):
        self._log("on_toggle_settings", value)

    @rx.event
    def got_config(self, config: dict):
        self.saved_config = config or {}
        if self.layout_name.strip():
            self.layouts = {**self.layouts, self.layout_name.strip(): self.saved_config}
        self._log("save()", {"plugin": self.saved_config.get("plugin")})

    @rx.event
    def apply_layout(self, name: str):
        cfg = dict(self.layouts.get(name) or {})
        cfg.pop("version", None)
        return rp.restore(VIEWER_ID, cfg)

    @rx.event
    def got_export(self, text: str):
        self.exported = (text or "")[:4000]

    @rx.event
    def got_schema(self, schema: dict):
        self.schema_text = json.dumps(schema, indent=2)

    @rx.event
    def on_loaded(self, info: dict):
        self.size = int(info.get("num_rows") or 0)
        self._log("on_load", info.get("schema"))

    @rx.event
    def got_size(self, n: int):
        self.size = int(n or 0)

    @rx.event
    def add_rows(self):
        rows = inventory(5, seed=self.next_sku)
        for r in rows:
            r["sku"] = f"SKU-{self.next_sku:04d}"
            self.next_sku += 1
        self._log("rp.update", [r["sku"] for r in rows])
        return rp.update(VIEWER_ID, rows)

    @rx.event
    def restock_selected(self):
        if not self.selected_sku:
            return rx.toast.warning("Click a row first")
        self._log("rp.update (upsert)", self.selected_sku)
        return rp.update(
            VIEWER_ID, [{"sku": self.selected_sku, "stock": 999, "reorder": False}]
        )

    @rx.event
    def remove_selected(self):
        if not self.selected_sku:
            return rx.toast.warning("Click a row first")
        sku, self.selected_sku = self.selected_sku, ""
        self._log("rp.remove", sku)
        return rp.remove(VIEWER_ID, [sku])

    @rx.event
    def reload_data(self):
        self.rows = inventory(seed=random.randint(2, 999))
        self._log("data prop → replace()", len(self.rows))


def _btn(icon: str, label: str, on_click, **kw) -> rx.Component:
    return rx.button(
        rx.icon(icon, size=14),
        label,
        size="1",
        variant=kw.pop("variant", "soft"),
        on_click=on_click,
        **kw,
    )


def actions_panel() -> rx.Component:
    S = ApiState
    return card(
        rx.vstack(
            rx.text(
                "Viewer actions (rx.call_function under the hood)",
                size="1",
                weight="bold",
                color=rx.color("gray", 11),
            ),
            rx.flex(
                _btn("panel-left", "Toggle settings", rp.toggle_config(VIEWER_ID)),
                _btn("rotate-ccw", "Reset", rp.reset(VIEWER_ID)),
                _btn("file-down", "Download CSV", rp.download(VIEWER_ID, "csv")),
                _btn("file-down", "Download Arrow", rp.download(VIEWER_ID, "arrow")),
                _btn("clipboard", "Copy CSV", rp.copy(VIEWER_ID, "csv")),
                _btn(
                    "braces", "Export JSON", rp.export(VIEWER_ID, S.got_export, "json")
                ),
                _btn(
                    "table-properties",
                    "Schema",
                    rp.table_schema(VIEWER_ID, S.got_schema),
                ),
                _btn("hash", "Row count", rp.table_size(VIEWER_ID, S.got_size)),
                _btn(
                    "sigma",
                    "Add expression",
                    rp.restore(
                        VIEWER_ID,
                        {
                            "expressions": {"value": '"stock" * "unit_cost"'},
                            "columns": [
                                "sku",
                                "product",
                                "warehouse",
                                "stock",
                                "unit_cost",
                                "value",
                                "reorder",
                            ],
                            "columns_config": {"value": {"fg_mode": "bar"}},
                        },
                    ),
                ),
                _btn(
                    "group",
                    "Pivot by warehouse",
                    rp.restore(
                        VIEWER_ID,
                        {
                            "group_by": ["warehouse"],
                            "split_by": ["product"],
                            "columns": ["stock"],
                        },
                    ),
                ),
                gap="8px",
                wrap="wrap",
            ),
            rx.text(
                "Table mutations",
                size="1",
                weight="bold",
                color=rx.color("gray", 11),
                margin_top="6px",
            ),
            rx.flex(
                _btn("plus", "Add 5 rows", S.add_rows),
                _btn("package-plus", "Restock clicked row", S.restock_selected),
                _btn(
                    "trash-2",
                    "Remove clicked row",
                    S.remove_selected,
                    color_scheme="red",
                ),
                _btn("refresh-cw", "New data (replace)", S.reload_data),
                rx.badge(
                    "clicked: ", rx.cond(S.selected_sku != "", S.selected_sku, "—")
                ),
                rx.badge("rows: ", S.size),
                gap="8px",
                wrap="wrap",
                align="center",
            ),
            rx.text(
                "Named layouts (save() → state → restore())",
                size="1",
                weight="bold",
                color=rx.color("gray", 11),
                margin_top="6px",
            ),
            rx.flex(
                rx.input(
                    value=S.layout_name,
                    on_change=S.set_layout_name,
                    size="1",
                    width="160px",
                ),
                _btn(
                    "save",
                    "Save current",
                    rp.save(VIEWER_ID, S.got_config),
                    variant="solid",
                ),
                rx.foreach(
                    S.layout_names,
                    lambda name: rx.button(
                        name, size="1", variant="outline", on_click=S.apply_layout(name)
                    ),
                ),
                gap="8px",
                wrap="wrap",
                align="center",
            ),
            rx.flex(
                rx.text("Datagrid edit_mode", size="1", weight="bold"),
                rx.select(
                    [
                        "READ_ONLY",
                        "EDIT",
                        "SELECT_ROW",
                        "SELECT_COLUMN",
                        "SELECT_REGION",
                    ],
                    value=S.edit_mode,
                    on_change=S.set_edit_mode,
                    size="1",
                ),
                rx.text(
                    "In EDIT mode double-click a cell to change it; the edit is written to the table.",
                    size="1",
                    color=rx.color("gray", 10),
                ),
                gap="8px",
                align="center",
                margin_top="6px",
            ),
            spacing="2",
            width="100%",
        )
    )


def api_page() -> rx.Component:
    S = ApiState
    return page(
        "Actions & events",
        "Every viewer method is available from Python as an EventSpec (rp.download, rp.save, rp.update, ...). "
        "Results come back through callbacks; the element's Custom Events arrive as regular Reflex events.",
        actions_panel(),
        rp.perspective_viewer(
            id=VIEWER_ID,
            data=S.rows,
            schema=SCHEMA,
            index="sku",
            table_name="inventory",
            plugin="Datagrid",
            edit_mode=S.edit_mode,
            columns_config={
                "stock": {"fg_mode": "bar"},
                "warehouse": {"fg_mode": "series"},
            },
            theme="Pro Light",
            on_click=S.on_click,
            on_select=S.on_select,
            on_config_update=S.on_config_update,
            on_toggle_settings=S.on_toggle_settings,
            on_load=S.on_loaded,
            height="460px",
            border_radius="12px",
            overflow="hidden",
            border=f"1px solid {rx.color('gray', 5)}",
        ),
        rx.grid(
            card(
                rx.text("Event log", weight="bold", size="2"),
                rx.vstack(
                    rx.foreach(
                        S.events, lambda e: rx.code(e, size="1", variant="ghost")
                    ),
                    spacing="1",
                    margin_top="8px",
                    max_height="320px",
                    overflow_y="auto",
                ),
            ),
            card(
                rx.tabs.root(
                    rx.tabs.list(
                        rx.tabs.trigger("save()", value="save"),
                        rx.tabs.trigger("export(json)", value="export"),
                        rx.tabs.trigger("schema()", value="schema"),
                    ),
                    rx.tabs.content(
                        code_json(S.saved_json), value="save", padding_top="8px"
                    ),
                    rx.tabs.content(
                        code_json(S.exported), value="export", padding_top="8px"
                    ),
                    rx.tabs.content(
                        code_json(S.schema_text), value="schema", padding_top="8px"
                    ),
                    default_value="save",
                ),
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
    )
