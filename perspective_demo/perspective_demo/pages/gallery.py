"""Plugin gallery: one viewer per chart type, each with its own theme."""

from __future__ import annotations

import reflex as rx

import reflex_perspective as rp

from ..data import SUPERSTORE_SCHEMA, ohlc, superstore
from ..layout import page

OHLC_SCHEMA = {
    "Date": "date",
    "Symbol": "string",
    "Open": "float",
    "High": "float",
    "Low": "float",
    "Close": "float",
}


class GalleryState(rx.State):
    rows: list[dict] = superstore(1500, seed=99)
    bars: list[dict] = ohlc()


TILES = [
    {
        "title": "Treemap",
        "theme": "Pro Light",
        "cfg": {
            "plugin": "Treemap",
            "group_by": ["Category", "Sub-Category"],
            "columns": ["Sales", "Profit"],
        },
    },
    {
        "title": "Sunburst",
        "theme": "Dracula",
        "cfg": {
            "plugin": "Sunburst",
            "group_by": ["Region", "Category", "Segment"],
            "columns": ["Sales"],
        },
    },
    {
        "title": "Heatmap",
        "theme": "Nord",
        "cfg": {
            "plugin": "Heatmap",
            "group_by": ["Sub-Category"],
            "split_by": ["Region"],
            "columns": ["Profit"],
        },
    },
    {
        "title": "X/Y Scatter",
        "theme": "Vaporwave",
        "cfg": {
            "plugin": "X/Y Scatter",
            "columns": ["Sales", "Profit", "Category", "Quantity"],
        },
    },
    {
        "title": "Y Line (monthly)",
        "theme": "Solarized",
        "cfg": {
            "plugin": "Y Line",
            "group_by": ["month"],
            "split_by": ["Region"],
            "columns": ["Sales"],
            "expressions": {"month": "bucket(\"Order Date\", 'M')"},
        },
    },
    {
        "title": "Density",
        "theme": "Gruvbox Dark",
        "cfg": {"plugin": "Density", "columns": ["Sales", "Profit"]},
    },
    {
        "title": "Map Scatter",
        "theme": "Phosphor",
        "cfg": {
            "plugin": "Map Scatter",
            "columns": ["Longitude", "Latitude", "Profit", "Sales"],
        },
    },
    {
        "title": "X Bar",
        "theme": "Botanical",
        "cfg": {
            "plugin": "X Bar",
            "group_by": ["State"],
            "columns": ["Profit"],
            "sort": [["Profit", "desc"]],
        },
    },
]


def tile(title: str, theme: str, viewer: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(title, weight="bold", size="2"),
            rx.spacer(),
            rx.badge(theme, variant="soft"),
        ),
        viewer,
        width="100%",
        spacing="2",
    )


def gallery_page() -> rx.Component:
    S = GalleryState
    tiles = [
        tile(
            t["title"],
            t["theme"],
            rp.perspective_viewer(
                id=f"gallery-{i}",
                data=S.rows,
                schema=SUPERSTORE_SCHEMA,
                table_name=f"gallery_{i}",
                config={**t["cfg"], "title": t["title"]},
                theme=t["theme"],
                height="340px",
                border_radius="10px",
                overflow="hidden",
            ),
        )
        for i, t in enumerate(TILES)
    ]
    tiles.append(
        tile(
            "Candlestick",
            "Monokai",
            rp.perspective_viewer(
                id="gallery-ohlc",
                data=S.bars,
                schema=OHLC_SCHEMA,
                table_name="gallery_ohlc",
                plugin="Candlestick",
                title="ACME daily bars",
                group_by=["Date"],
                columns=["Open", "Close", "High", "Low"],
                theme="Monokai",
                height="340px",
                border_radius="10px",
                overflow="hidden",
            ),
        )
    )
    return page(
        "Plugin gallery",
        "Every chart from @perspective-dev/viewer-charts (WebGL) plus the datagrid, each viewer with a different bundled theme.",
        rx.grid(
            *tiles,
            columns=rx.breakpoints(initial="1", md="2", xl="3"),
            spacing="5",
            width="100%",
        ),
    )
