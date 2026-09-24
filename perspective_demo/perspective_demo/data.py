"""Deterministic synthetic datasets for the demo (stdlib only)."""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta, timezone

# City -> (state, region, lat, lon)
CITIES: dict[str, tuple[str, str, float, float]] = {
    "New York": ("New York", "East", 40.7128, -74.0060),
    "Boston": ("Massachusetts", "East", 42.3601, -71.0589),
    "Philadelphia": ("Pennsylvania", "East", 39.9526, -75.1652),
    "Washington": ("District of Columbia", "East", 38.9072, -77.0369),
    "Miami": ("Florida", "South", 25.7617, -80.1918),
    "Atlanta": ("Georgia", "South", 33.7490, -84.3880),
    "Houston": ("Texas", "Central", 29.7604, -95.3698),
    "Dallas": ("Texas", "Central", 32.7767, -96.7970),
    "Chicago": ("Illinois", "Central", 41.8781, -87.6298),
    "Minneapolis": ("Minnesota", "Central", 44.9778, -93.2650),
    "Detroit": ("Michigan", "Central", 42.3314, -83.0458),
    "Nashville": ("Tennessee", "South", 36.1627, -86.7816),
    "New Orleans": ("Louisiana", "South", 29.9511, -90.0715),
    "Denver": ("Colorado", "West", 39.7392, -104.9903),
    "Phoenix": ("Arizona", "West", 33.4484, -112.0740),
    "Las Vegas": ("Nevada", "West", 36.1699, -115.1398),
    "Los Angeles": ("California", "West", 34.0522, -118.2437),
    "San Francisco": ("California", "West", 37.7749, -122.4194),
    "San Diego": ("California", "West", 32.7157, -117.1611),
    "Seattle": ("Washington", "West", 47.6062, -122.3321),
    "Portland": ("Oregon", "West", 45.5152, -122.6784),
}

CATEGORIES: dict[str, list[tuple[str, float]]] = {
    "Furniture": [
        ("Chairs", 180),
        ("Tables", 320),
        ("Bookcases", 250),
        ("Furnishings", 60),
    ],
    "Office Supplies": [
        ("Paper", 18),
        ("Binders", 25),
        ("Storage", 90),
        ("Art", 12),
        ("Appliances", 140),
        ("Labels", 8),
    ],
    "Technology": [
        ("Phones", 380),
        ("Machines", 900),
        ("Accessories", 120),
        ("Copiers", 1500),
    ],
}

SEGMENTS = ["Consumer", "Corporate", "Home Office"]
SHIP_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]

SUPERSTORE_SCHEMA: dict[str, str] = {
    "Row ID": "integer",
    "Order Date": "date",
    "Ship Mode": "string",
    "Segment": "string",
    "City": "string",
    "State": "string",
    "Region": "string",
    "Category": "string",
    "Sub-Category": "string",
    "Sales": "float",
    "Quantity": "integer",
    "Discount": "float",
    "Profit": "float",
    "Latitude": "float",
    "Longitude": "float",
}


def superstore(n: int = 4000, seed: int = 7) -> list[dict]:
    """A Superstore-like order table."""
    rng = random.Random(seed)
    start = date(2023, 1, 1)
    cities = list(CITIES)
    weights = [3 if c in ("New York", "Los Angeles", "Chicago") else 1 for c in cities]
    rows = []
    for i in range(n):
        city = rng.choices(cities, weights)[0]
        state, region, lat, lon = CITIES[city]
        category = rng.choice(list(CATEGORIES))
        sub, base = rng.choice(CATEGORIES[category])
        qty = rng.randint(1, 9)
        discount = rng.choice([0, 0, 0, 0.1, 0.2, 0.3, 0.5])
        sales = round(base * qty * rng.uniform(0.6, 1.4) * (1 - discount), 2)
        margin = rng.uniform(-0.15, 0.35) - discount * 0.6
        day = start + timedelta(days=int(730 * (i / n)) + rng.randint(0, 6))
        rows.append(
            {
                "Row ID": i + 1,
                "Order Date": day.isoformat(),
                "Ship Mode": rng.choice(SHIP_MODES),
                "Segment": rng.choice(SEGMENTS),
                "City": city,
                "State": state,
                "Region": region,
                "Category": category,
                "Sub-Category": sub,
                "Sales": sales,
                "Quantity": qty,
                "Discount": discount,
                "Profit": round(sales * margin, 2),
                "Latitude": round(lat + rng.uniform(-0.25, 0.25), 4),
                "Longitude": round(lon + rng.uniform(-0.25, 0.25), 4),
            }
        )
    return rows


def superstore_columns(n: int, seed: int = 11) -> dict[str, list]:
    """Column-oriented Superstore (cheaper to build for large ``n``)."""
    rows = superstore(min(n, 5000), seed)
    rng = random.Random(seed)
    cols: dict[str, list] = {k: [] for k in SUPERSTORE_SCHEMA}
    for i in range(n):
        r = rows[i % len(rows)]
        jitter = rng.uniform(0.8, 1.2)
        for k in SUPERSTORE_SCHEMA:
            cols[k].append(r[k])
        cols["Row ID"][-1] = i + 1
        cols["Sales"][-1] = round(r["Sales"] * jitter, 2)
        cols["Profit"][-1] = round(r["Profit"] * jitter, 2)
    return cols


SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOG",
    "META",
    "TSLA",
    "AMD",
    "INTC",
    "ORCL",
    "IBM",
    "CRM",
]
SECTORS = {
    "AAPL": "Hardware",
    "MSFT": "Software",
    "NVDA": "Semis",
    "AMZN": "Retail",
    "GOOG": "Media",
    "META": "Media",
    "TSLA": "Auto",
    "AMD": "Semis",
    "INTC": "Semis",
    "ORCL": "Software",
    "IBM": "Hardware",
    "CRM": "Software",
}

MARKET_SCHEMA = {
    "symbol": "string",
    "sector": "string",
    "price": "float",
    "change": "float",
    "change_pct": "float",
    "bid": "float",
    "ask": "float",
    "volume": "integer",
    "updated": "datetime",
}

TRADES_SCHEMA = {
    "id": "integer",
    "time": "datetime",
    "symbol": "string",
    "sector": "string",
    "side": "string",
    "price": "float",
    "qty": "integer",
    "notional": "float",
}


class Market:
    """A tiny random-walk market used by the streaming demos."""

    def __init__(self, seed: int = 3) -> None:
        self.rng = random.Random(seed)
        self.open = {s: self.rng.uniform(50, 600) for s in SYMBOLS}
        self.price = dict(self.open)
        self.volume = dict.fromkeys(SYMBOLS, 0)
        self.trade_id = 0

    def tick(self, n_trades: int = 20) -> tuple[list[dict], list[dict]]:
        now = datetime.now(timezone.utc).isoformat()
        trades = []
        for _ in range(n_trades):
            s = self.rng.choice(SYMBOLS)
            self.price[s] = max(1.0, self.price[s] * math.exp(self.rng.gauss(0, 0.002)))
            qty = self.rng.randint(1, 50) * 10
            self.volume[s] += qty
            self.trade_id += 1
            px = round(self.price[s], 2)
            trades.append(
                {
                    "id": self.trade_id,
                    "time": now,
                    "symbol": s,
                    "sector": SECTORS[s],
                    "side": self.rng.choice(["buy", "sell"]),
                    "price": px,
                    "qty": qty,
                    "notional": round(px * qty, 2),
                }
            )
        quotes = []
        for s in SYMBOLS:
            px = self.price[s]
            spread = px * 0.0005
            quotes.append(
                {
                    "symbol": s,
                    "sector": SECTORS[s],
                    "price": round(px, 2),
                    "change": round(px - self.open[s], 2),
                    "change_pct": round((px / self.open[s] - 1) * 100, 3),
                    "bid": round(px - spread, 2),
                    "ask": round(px + spread, 2),
                    "volume": self.volume[s],
                    "updated": now,
                }
            )
        return quotes, trades


def ohlc(symbol: str = "ACME", days: int = 180, seed: int = 5) -> list[dict]:
    """Daily OHLC bars for the candlestick chart."""
    rng = random.Random(seed)
    px = 100.0
    out = []
    start = date(2025, 1, 1)
    for d in range(days):
        o = px
        c = max(1.0, o * math.exp(rng.gauss(0.0005, 0.018)))
        h = max(o, c) * (1 + abs(rng.gauss(0, 0.008)))
        low = min(o, c) * (1 - abs(rng.gauss(0, 0.008)))
        out.append(
            {
                "Date": (start + timedelta(days=d)).isoformat(),
                "Symbol": symbol,
                "Open": round(o, 2),
                "High": round(h, 2),
                "Low": round(low, 2),
                "Close": round(c, 2),
            }
        )
        px = c
    return out


def sensors_batch(
    t0: float, step: int, n_sensors: int = 6, seed: int = 0
) -> list[dict]:
    """One reading per sensor at logical time ``step``."""
    rng = random.Random(seed + step)
    ts = datetime.fromtimestamp(t0 + step * 0.5, tz=timezone.utc).isoformat()
    rows = []
    for k in range(n_sensors):
        phase = k * 0.9
        value = 20 + 8 * math.sin(step / 12 + phase) + rng.gauss(0, 0.8) + k * 3
        rows.append(
            {
                "time": ts,
                "sensor": f"sensor-{k + 1}",
                "zone": "north" if k % 2 == 0 else "south",
                "value": round(value, 3),
                "step": step,
            }
        )
    return rows


SENSOR_SCHEMA = {
    "time": "datetime",
    "sensor": "string",
    "zone": "string",
    "value": "float",
    "step": "integer",
}
