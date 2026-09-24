"""reflex-perspective demo app.

Pages:
    /            Explorer          client-only table driven by state props
    /streaming   Client streaming  background task -> update_rows / rp.update
    /server      Python server     perspective-python tables over a WebSocket
    /workspace   Workspace         multi-panel layout with global filters
    /api         Actions & events  imperative API, callbacks, editable grid
    /gallery     Plugin gallery    every chart plugin with a different theme
"""

import reflex as rx

from reflex_perspective import server as ps

from .live import HUB, market_feed
from .pages.api import api_page
from .pages.explorer import explorer
from .pages.gallery import gallery_page
from .pages.server import ServerState, server_page
from .pages.streaming import streaming
from .pages.workspace import workspace_page

app = rx.App(
    # Serve perspective-python's WebSocket protocol at /perspective on the backend.
    api_transformer=ps.perspective_api(path="/perspective", hub=HUB),
)
app.register_lifespan_task(market_feed)

app.add_page(explorer, route="/", title="Explorer · reflex-perspective")
app.add_page(streaming, route="/streaming", title="Streaming · reflex-perspective")
app.add_page(
    server_page,
    route="/server",
    title="Python server · reflex-perspective",
    on_load=ServerState.refresh,
)
app.add_page(workspace_page, route="/workspace", title="Workspace · reflex-perspective")
app.add_page(api_page, route="/api", title="Actions & events · reflex-perspective")
app.add_page(gallery_page, route="/gallery", title="Gallery · reflex-perspective")
