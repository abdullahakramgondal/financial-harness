"""Fundamental and technical analysis helpers.
Plain Python, exposed as MCP tools in server.py.
"""
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(x):
    """Convert a value to a rounded float, or None if it is missing or NaN."""
    try:
        if x is None or pd.isna(x):
            return None
        return round(float(x), 4)
    except (TypeError, ValueError):
        return None


FUNDAMENTAL_KEYS = {
    "name": "shortName",
    "sector": "sector",
    "industry": "industry",
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "trailing_eps": "trailingEps",
    "profit_margin": "profitMargins",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "return_on_equity": "returnOnEquity",
    "debt_to_equity": "debtToEquity",
    "dividend_yield": "dividendYield",
    "fifty_two_week_high": "fiftyTwoWeekHigh",
    "fifty_two_week_low": "fiftyTwoWeekLow",
}

INCOME_ROWS = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Diluted EPS"]


def get_fundamentals(symbol: str) -> dict:
    """Valuation and company performance ratios plus the last annual income statements."""
    t = yf.Ticker(symbol.upper())
    try:
        info = t.info or {}
    except Exception:
        info = {}

    fundamentals = {}
    for out_key, src_key in FUNDAMENTAL_KEYS.items():
        value = info.get(src_key)
        fundamentals[out_key] = _num(value) if isinstance(value, (int, float)) else value

    income = {}
    try:
        stmt = t.income_stmt
        if stmt is not None and not stmt.empty:
            for col in list(stmt.columns)[:3]:
                year = str(col.date()) if hasattr(col, "date") else str(col)
                income[year] = {r: _num(stmt.loc[r, col]) for r in INCOME_ROWS if r in stmt.index}
    except Exception:
        income = {}

    return {
        "symbol": symbol.upper(),
        "fundamentals": fundamentals,
        "annual_income_statement": income,
        "timestamp": _now(),
        "source": "yfinance",
    }


def get_indicators(symbol: str, period: str = "1y") -> dict:
    """Technical indicators from daily candles: SMA20/50, RSI14, MACD, volume, plus plain signals."""
    hist = yf.Ticker(symbol.upper()).history(period=period, interval="1d")
    if hist.empty or len(hist) < 30:
        return {"symbol": symbol.upper(), "error": "not enough price history"}

    close = hist["Close"]
    volume = hist["Volume"]

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + avg_gain / avg_loss)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    last = _num(close.iloc[-1])
    v_sma20 = _num(sma20.iloc[-1])
    v_sma50 = _num(sma50.iloc[-1])
    v_rsi = _num(rsi.iloc[-1])
    v_macd = _num(macd.iloc[-1])
    v_macd_signal = _num(macd_signal.iloc[-1])
    avg_vol = _num(volume.tail(20).mean())
    last_vol = _num(volume.iloc[-1])
    change_1m = _num((close.iloc[-1] / close.iloc[-22] - 1) * 100) if len(close) > 22 else None

    signals = []
    if v_sma50 is not None:
        signals.append("price is above SMA50 (uptrend)" if last > v_sma50 else "price is below SMA50 (downtrend)")
    if v_sma20 is not None and v_sma50 is not None:
        signals.append("SMA20 is above SMA50 (bullish)" if v_sma20 > v_sma50 else "SMA20 is below SMA50 (bearish)")
    if v_rsi is not None:
        if v_rsi > 70:
            signals.append(f"RSI {v_rsi} is overbought (above 70)")
        elif v_rsi < 30:
            signals.append(f"RSI {v_rsi} is oversold (below 30)")
        else:
            signals.append(f"RSI {v_rsi} is neutral (30 to 70)")
    if v_macd is not None and v_macd_signal is not None:
        signals.append("MACD is above its signal line (bullish momentum)" if v_macd > v_macd_signal
                       else "MACD is below its signal line (bearish momentum)")
    if avg_vol and last_vol:
        signals.append(f"last volume is {round(last_vol / avg_vol, 2)}x the 20-day average")

    return {
        "symbol": symbol.upper(),
        "period": period,
        "last_close": last,
        "sma20": v_sma20,
        "sma50": v_sma50,
        "rsi14": v_rsi,
        "macd": v_macd,
        "macd_signal": v_macd_signal,
        "avg_volume_20d": avg_vol,
        "last_volume": last_vol,
        "change_1m_pct": change_1m,
        "signals": signals,
        "timestamp": _now(),
        "source": "yfinance",
    }