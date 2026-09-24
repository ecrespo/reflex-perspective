"""Python server: tables hosted by perspective-python inside the Reflex backend."""

from __future__ import annotations

import reflex as rx

import reflex_perspective as rp

from ..layout import card, page
from ..live import BIG_ROWS, HUB, MARKET, Feed


class ServerState(rx.State):
    running: bool = True
    trades_per_tick: int = 25
    tables: list[str] = []
    sizes: dict[str, int] = {}
    sector_rows: list[dict] = []
    trades_mode: str = "replicated"

    @rx.event
    def refresh(self):
        self.running = Feed.running
        self.trades_per_tick = Feed.trades_per_tick
        try:
            self.tables = HUB.table_names()
            self.sizes = {name: HUB.size(name) for name in self.tables}
        except Exception:  # noqa: BLE001 - tables not built yet
            self.tables, self.sizes = [], {}

    @rx.event
    def toggle_feed(self, value: bool):
        Feed.running = value
        self.running = value

    @rx.event
    def set_rate(self, value: list[int | float]):
        Feed.trades_per_tick = int(value[0])
        self.trades_per_tick = int(value[0])

    @rx.event
    def set_trades_mode(self, value: str):
        self.trades_mode = value

    @rx.event
    def burst(self):
        quotes, trades = MARKET.tick(5000)
        HUB.update("quotes", quotes)
        HUB.update("trades", trades)
        self.refresh()

    @rx.event
    def clear_trades(self):
        HUB.clear("trades")
        self.refresh()

    @rx.event
    def python_query(self):
        """Aggregate in Python with a perspective View (no browser involved)."""
        rows = HUB.query(
            "trades",
            group_by=["sector"],
            columns=["qty", "notional", "price"],
            aggregates={"qty": "sum", "notional": "sum", "price": "avg"},
            sort=[["notional", "desc"]],
        )
        out = []
        for r in rows:
            path = r.get("__ROW_PATH__") or []
            out.append(
                {
                    "sector": path[0] if path else "TOTAL",
                    "qty": int(r.get("qty") or 0),
                    "notional": f"{(r.get('notional') or 0):,.0f}",
                    "avg price": f"{(r.get('price') or 0):,.2f}",
                }
            )
        self.sector_rows = out
        self.refresh()


def _sizes_badges() -> rx.Component:
    return rx.hstack(
        rx.foreach(
            ServerState.tables,
            lambda name: rx.badge(
                rx.icon("database", size=12),
                name,
                " · ",
                ServerState.sizes[name].to(str),
                " rows",
                variant="soft",
            ),
        ),
        wrap="wrap",
    )


def _query_table() -> rx.Component:
    return rx.cond(
        ServerState.sector_rows.length() > 0,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("sector"),
                    rx.table.column_header_cell("qty"),
                    rx.table.column_header_cell("notional"),
                    rx.table.column_header_cell("avg price"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    ServerState.sector_rows,
                    lambda r: rx.table.row(
                        rx.table.cell(r["sector"]),
                        rx.table.cell(r["qty"]),
                        rx.table.cell(r["notional"]),
                        rx.table.cell(r["avg price"]),
                    ),
                )
            ),
            size="1",
            width="100%",
        ),
        rx.text(
            "Run the query to aggregate the trades table in Python.",
            size="2",
            color=rx.color("gray", 10),
        ),
    )


def server_page() -> rx.Component:
    S = ServerState
    return page(
        "Python server",
        "Tables live in perspective-python inside the Reflex backend and are served over a WebSocket "
        "mounted with api_transformer. A lifespan task streams market ticks; event handlers mutate the "
        "same tables. Nothing here goes through Reflex state.",
        card(
            rx.flex(
                rx.hstack(
                    rx.switch(checked=S.running, on_change=S.toggle_feed),
                    rx.text("Market feed", size="2"),
                ),
                rx.vstack(
                    rx.text("Trades per tick: ", S.trades_per_tick, size="1"),
                    rx.slider(
                        default_value=[25],
                        min=1,
                        max=500,
                        on_value_commit=S.set_rate,
                        width="180px",
                    ),
                    spacing="1",
                ),
                rx.button(
                    rx.icon("zap", size=14),
                    "Burst 5,000 trades",
                    variant="soft",
                    on_click=S.burst,
                ),
                rx.button(
                    rx.icon("eraser", size=14),
                    "Clear trades",
                    variant="soft",
                    color_scheme="gray",
                    on_click=S.clear_trades,
                ),
                rx.button(
                    rx.icon("refresh-cw", size=14),
                    "Refresh sizes",
                    variant="outline",
                    on_click=S.refresh,
                ),
                gap="16px",
                wrap="wrap",
                align="center",
            ),
            rx.box(_sizes_badges(), margin_top="12px"),
        ),
        rx.grid(
            rx.vstack(
                rx.hstack(
                    rx.heading("quotes", size="3"),
                    rx.badge("server-only · index=symbol"),
                    align="center",
                ),
                rp.perspective_viewer(
                    id="quotes",
                    server_url="/perspective",
                    server_table="quotes",
                    plugin="Datagrid",
                    columns=[
                        "symbol",
                        "sector",
                        "price",
                        "change",
                        "change_pct",
                        "bid",
                        "ask",
                        "volume",
                    ],
                    sort=[["change_pct", "desc"]],
                    columns_config={
                        "change_pct": {"bg_mode": "gradient"},
                        "volume": {"fg_mode": "bar"},
                        "sector": {"fg_mode": "series"},
                    },
                    theme="Pro Dark",
                    height="420px",
                ),
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.heading("trades", size="3"),
                    rx.select(
                        ["replicated", "server"],
                        value=S.trades_mode,
                        on_change=S.set_trades_mode,
                        size="1",
                    ),
                    rx.badge("limit=20,000"),
                    align="center",
                ),
                rp.perspective_viewer(
                    id="trades",
                    server_url="/perspective",
                    server_table="trades",
                    server_mode=S.trades_mode,
                    plugin="Y Bar",
                    group_by=["sector"],
                    split_by=["side"],
                    columns=["notional"],
                    theme="Pro Dark",
                    height="420px",
                ),
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
        rx.vstack(
            rx.hstack(
                rx.heading("orders", size="3"),
                rx.badge(f"{BIG_ROWS:,} rows · virtual table"),
                align="center",
            ),
            rx.text(
                "A quarter-million-row table that never leaves Python: pivots, sorts and filters run on the "
                "server and only the visible cells are sent to the browser.",
                size="2",
                color=rx.color("gray", 11),
            ),
            rp.perspective_viewer(
                id="orders",
                server_url="/perspective",
                server_table="orders",
                plugin="Datagrid",
                group_by=["Region", "Category"],
                split_by=["Segment"],
                columns=["Sales", "Profit", "Quantity"],
                settings=True,
                height="520px",
            ),
            width="100%",
        ),
        card(
            rx.hstack(
                rx.heading("Query from Python", size="3"),
                rx.spacer(),
                rx.button(
                    rx.icon("play", size=14),
                    "Aggregate trades by sector",
                    on_click=S.python_query,
                ),
            ),
            rx.box(_query_table(), margin_top="12px"),
        ),
    )
