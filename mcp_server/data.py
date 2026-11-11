"""FH-26..30: market data functions. Plain Python, MCP server aur agent dono import kar sakte hain.
Provider: yfinance (free, no key). Baad mein Nasdaq/Finnhub se badalna ho to sirf yeh file badlo.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

PORTFOLIO_PATH = Path(__file__).resolve().parent.parent / "portfolio.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_price(symbol: str) -> dict:
    """Latest price. Returns dict with price, currency, timestamp, source."""
    t = yf.Ticker(symbol.upper())
    price = None
    try:
        price = t.fast_info["last_price"]
    except Exception:
        hist = t.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
    if price is None:
        return {"symbol": symbol.upper(), "error": "price not available"}
    return {
        "symbol": symbol.upper(),
        "price": round(float(price), 4),
        "currency": "USD",
        "timestamp": _now(),
        "source": "yfinance",
    }


def get_candles(symbol: str, interval: str = "1d", period: str = "3mo") -> dict:
    """OHLCV candles. interval: 1m,5m,15m,1h,1d,1wk. period: 5d,1mo,3mo,6mo,1y,5y."""
    hist = yf.Ticker(symbol.upper()).history(period=period, interval=interval)
    candles = [
        {
            "time": idx.isoformat(),
            "open": round(float(r["Open"]), 4),
            "high": round(float(r["High"]), 4),
            "low": round(float(r["Low"]), 4),
            "close": round(float(r["Close"]), 4),
            "volume": int(r["Volume"]),
        }
        for idx, r in hist.iterrows()
    ]
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "period": period,
        "candles": candles,
        "timestamp": _now(),
        "source": "yfinance",
    }


def get_news(symbol: str, limit: int = 5) -> dict:
    """Latest headlines. yfinance ka news format badalta rehta hai, isliye dono shapes handle hain."""
    items = []
    try:
        raw = yf.Ticker(symbol.upper()).news or []
    except Exception:
        raw = []
    for n in raw[:limit]:
        c = n.get("content", n)  # naya format: n["content"]["title"]
        title = c.get("title")
        if not title:
            continue
        link = (c.get("canonicalUrl") or {}).get("url") or c.get("link")
        publisher = (c.get("provider") or {}).get("displayName") or c.get("publisher")
        items.append(
            {
                "title": title,
                "publisher": publisher,
                "link": link,
                "published": c.get("pubDate") or c.get("providerPublishTime"),
            }
        )
    return {"symbol": symbol.upper(), "news": items, "timestamp": _now(), "source": "yfinance"}


def get_portfolio() -> dict:
    """FH-31: portfolio.json se holdings + current value + P&L."""
    p = json.loads(PORTFOLIO_PATH.read_text())
    rows, total_value, total_cost = [], 0.0, 0.0
    for h in p["holdings"]:
        info = get_price(h["symbol"])
        price = info.get("price")
        if price is None:
            rows.append({**h, "error": info.get("error")})
            continue
        value = price * h["quantity"]
        cost = h["buy_price"] * h["quantity"]
        total_value += value
        total_cost += cost
        rows.append(
            {
                **h,
                "current_price": price,
                "value": round(value, 2),
                "pnl": round(value - cost, 2),
                "pnl_pct": round((value - cost) / cost * 100, 2),
            }
        )
    return {
        "cash": p["cash"],
        "holdings": rows,
        "goals": p["goals"],
        "total_value": round(total_value, 2),
        "total_pnl": round(total_value - total_cost, 2),
        "timestamp": _now(),
    }
