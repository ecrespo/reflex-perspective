"""perspective-python tables hosted inside the Reflex backend."""

from __future__ import annotations

import asyncio
import logging

from reflex_perspective import server as ps

from .data import (
    MARKET_SCHEMA,
    SUPERSTORE_SCHEMA,
    TRADES_SCHEMA,
    Market,
    superstore_columns,
)

log = logging.getLogger(__name__)

HUB = ps.get_hub()
MARKET = Market()
BIG_ROWS = 250_000


class Feed:
    """Mutable switches the UI flips through event handlers."""

    running: bool = True
    trades_per_tick: int = 25
    interval: float = 0.25


def ensure_tables() -> None:
    """Create every hosted table once (idempotent)."""
    # Small live tables first so their viewers connect immediately.
    if not HUB.has_table("quotes"):
        HUB.table(MARKET_SCHEMA, name="quotes", index="symbol")
    if not HUB.has_table("trades"):
        HUB.table(TRADES_SCHEMA, name="trades", limit=20_000)
    quotes, trades = MARKET.tick(200)
    HUB.update("quotes", quotes)
    HUB.update("trades", trades)
    if not HUB.has_table("orders"):
        HUB.table(SUPERSTORE_SCHEMA, name="orders", index="Row ID")
        HUB.update("orders", superstore_columns(BIG_ROWS))


async def market_feed() -> None:
    """Lifespan task: build the tables, then stream ticks forever."""
    await asyncio.to_thread(ensure_tables)
    log.info("perspective tables ready: %s", HUB.table_names())
    while True:
        if Feed.running:
            quotes, trades = MARKET.tick(Feed.trades_per_tick)
            HUB.update("quotes", quotes)
            HUB.update("trades", trades)
        await asyncio.sleep(Feed.interval)
