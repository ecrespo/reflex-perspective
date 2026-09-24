import reflex as rx

config = rx.Config(
    app_name="perspective_demo",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="light", accent_color="indigo", radius="medium"),
        ),
    ],
)
