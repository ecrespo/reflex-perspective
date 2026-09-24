"""Client streaming: a Reflex background task pushes batches into the browser."""

from __future__ import annotations

import asyncio
import time

import reflex as rx

import reflex_perspective as rp

from ..data import SENSOR_SCHEMA, sensors_batch
from ..layout import card, page

VIEWER_ID = "sensors"


class StreamingState(rx.State):
    running: bool = False
    step: int = 0
    interval_ms: int = 300
    window: int = 3000
    batch: list[dict] = []
    total_rows: int = 0
    plugin: str = "Y Line"
    t0: float = 0.0
    table_rows: int = -1

    @rx.event
    def set_plugin(self, value: str):
        self.plugin = value

    @rx.event
    def set_interval(self, value: list[int | float]):
        self.interval_ms = int(value[0])

    @rx.event
    def stop(self):
        self.running = False

    @rx.event(background=True)
    async def start(self):
        async with self:
            if self.running:
                return
            self.running = True
            if not self.t0:
                self.t0 = time.time()
        while True:
            async with self:
                if not self.running:
                    return
                # update_rows: every new list instance is applied with table.update()
                self.batch = sensors_batch(self.t0, self.step)
                self.step += 1
                self.total_rows += len(self.batch)
                delay = self.interval_ms / 1000
            await asyncio.sleep(delay)

    @rx.event
    def burst(self):
        """Push 200 steps at once *without* touching state (rp.update action)."""
        rows = []
        for _ in range(200):
            rows.extend(sensors_batch(self.t0 or time.time(), self.step))
            self.step += 1
        self.total_rows += len(rows)
        return rp.update(VIEWER_ID, rows)

    @rx.event
    def clear(self):
        self.total_rows = 0
        return rp.clear(VIEWER_ID)

    @rx.event
    def set_table_rows(self, n: int):
        self.table_rows = int(n or 0)


def streaming() -> rx.Component:
    S = StreamingState
    return page(
        "Client streaming",
        "A Reflex background task emits a new batch every few hundred milliseconds. "
        "The viewer applies each batch with table.update() via the update_rows prop; "
        "limit keeps a rolling window of rows inside the WebWorker.",
        card(
            rx.flex(
                rx.cond(
                    S.running,
                    rx.button(
                        rx.icon("pause", size=14),
                        "Stop",
                        color_scheme="red",
                        on_click=S.stop,
                    ),
                    rx.button(
                        rx.icon("play", size=14), "Start stream", on_click=S.start
                    ),
                ),
                rx.button(
                    rx.icon("zap", size=14),
                    "Burst 1,200 rows (rp.update)",
                    variant="soft",
                    on_click=S.burst,
                ),
                rx.button(
                    rx.icon("eraser", size=14),
                    "Clear",
                    variant="soft",
                    color_scheme="gray",
                    on_click=S.clear,
                ),
                rx.button(
                    rx.icon("hash", size=14),
                    "Count rows (callback)",
                    variant="outline",
                    on_click=rp.table_size(VIEWER_ID, S.set_table_rows),
                ),
                rx.select(
                    ["Y Line", "Y Area", "Y Scatter", "Heatmap", "Datagrid"],
                    value=S.plugin,
                    on_change=S.set_plugin,
                ),
                rx.vstack(
                    rx.text("Interval: ", S.interval_ms, " ms", size="1"),
                    rx.slider(
                        default_value=[300],
                        min=50,
                        max=1500,
                        step=50,
                        on_value_commit=S.set_interval,
                        width="180px",
                    ),
                    spacing="1",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.badge(
                        rx.cond(S.running, "live", "idle"),
                        color_scheme=rx.cond(S.running, "green", "gray"),
                    ),
                    rx.badge("step ", S.step),
                    rx.badge("rows sent ", S.total_rows),
                    rx.cond(
                        S.table_rows >= 0,
                        rx.badge("rows in table ", S.table_rows, color_scheme="violet"),
                    ),
                ),
                gap="14px",
                wrap="wrap",
                align="center",
            ),
        ),
        rp.perspective_viewer(
            id=VIEWER_ID,
            schema=SENSOR_SCHEMA,
            limit=S.window,
            update_rows=S.batch,
            plugin=S.plugin,
            columns=["value"],
            group_by=rx.cond(S.plugin == "Heatmap", ["step"], ["time"]),
            split_by=["sensor"],
            aggregates={"value": "avg"},
            theme="Pro Dark",
            throttle=100,
            height="560px",
            border_radius="12px",
            overflow="hidden",
        ),
        rx.callout(
            "Two paths are shown: update_rows (state → prop → table.update) for small, frequent batches, "
            "and rp.update(viewer_id, rows) which sends the rows once to the browser without storing them in state.",
            icon="info",
            size="1",
        ),
    )
