"""Shared page chrome: sidebar navigation + header."""

from __future__ import annotations

import reflex as rx

NAV: list[tuple[str, str, str]] = [
    ("/", "Explorer", "table-2"),
    ("/streaming", "Client streaming", "activity"),
    ("/server", "Python server", "server"),
    ("/workspace", "Workspace", "layout-dashboard"),
    ("/api", "Actions & events", "terminal"),
    ("/gallery", "Plugin gallery", "chart-pie"),
]


def _nav_item(href: str, label: str, icon: str) -> rx.Component:
    active = rx.State.router.page.path == href
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=16),
            rx.text(label, size="2", weight="medium"),
            spacing="2",
            align="center",
            padding_x="10px",
            padding_y="7px",
            border_radius="8px",
            width="100%",
            background=rx.cond(active, rx.color("accent", 4), "transparent"),
            color=rx.cond(active, rx.color("accent", 12), rx.color("gray", 11)),
            _hover={"background": rx.color("accent", 3)},
        ),
        href=href,
        underline="none",
        width="100%",
    )


def sidebar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.icon("sparkles", size=20, color=rx.color("accent", 10)),
            rx.heading("reflex-perspective", size="4"),
            align="center",
            spacing="2",
        ),
        rx.text(
            "Perspective 5.5 inside Reflex",
            size="1",
            color=rx.color("gray", 10),
        ),
        rx.divider(margin_y="8px"),
        *[_nav_item(*item) for item in NAV],
        rx.spacer(),
        rx.link(
            rx.hstack(
                rx.icon("book-open", size=14), rx.text("Perspective docs", size="1")
            ),
            href="https://perspective-dev.github.io",
            is_external=True,
            color=rx.color("gray", 10),
        ),
        rx.color_mode.button(size="1", variant="ghost"),
        width="230px",
        min_width="230px",
        height="100vh",
        position="sticky",
        top="0",
        padding="18px 14px",
        border_right=f"1px solid {rx.color('gray', 5)}",
        background=rx.color("gray", 2),
        spacing="1",
        align="start",
    )


def page(title: str, subtitle: str, *children: rx.Component) -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.vstack(
            rx.vstack(
                rx.heading(title, size="7"),
                rx.text(subtitle, color=rx.color("gray", 11), size="3"),
                spacing="1",
                width="100%",
            ),
            *children,
            width="100%",
            min_width="0",
            padding="24px 28px 48px",
            spacing="5",
        ),
        spacing="0",
        align="start",
        width="100%",
        min_height="100vh",
    )


def card(*children: rx.Component, **props) -> rx.Component:
    return rx.box(
        *children,
        padding="16px",
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius="12px",
        background=rx.color("gray", 1),
        width="100%",
        **props,
    )


def code_json(value) -> rx.Component:
    return rx.code_block(
        value,
        language="json",
        wrap_long_lines=True,
        custom_style={
            "fontSize": "12px",
            "maxHeight": "320px",
            "overflow": "auto",
            "margin": 0,
        },
        width="100%",
    )
