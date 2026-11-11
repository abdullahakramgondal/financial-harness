"""MCP server. Run: python -m mcp_server.server  (stdio transport)
Inspect/test: mcp dev mcp_server/server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server import analysis, data  # noqa: E402
from sandbox import runner  # noqa: E402

mcp = FastMCP("market-data")


@mcp.tool()
def get_price(symbol: str) -> dict:
    """Get the latest price for a stock symbol (e.g. AAPL)."""
    return data.get_price(symbol)


@mcp.tool()
def get_candles(symbol: str, interval: str = "1d", period: str = "3mo") -> dict:
    """Get OHLCV candlestick data. interval: 1m,5m,1h,1d,1wk. period: 5d,1mo,3mo,6mo,1y."""
    return data.get_candles(symbol, interval, period)


@mcp.tool()
def get_news(symbol: str, limit: int = 5) -> dict:
    """Get the latest news headlines for a stock symbol."""
    return data.get_news(symbol, limit)


@mcp.tool()
def get_portfolio() -> dict:
    """Get the user's holdings with current value and P&L, plus 10-month/20-month/10-year goals."""
    return data.get_portfolio()


@mcp.tool()
def get_fundamentals(symbol: str) -> dict:
    """Get fundamental data: valuation ratios (P/E, P/B), margins, growth, and annual income statements."""
    return analysis.get_fundamentals(symbol)


@mcp.tool()
def get_indicators(symbol: str, period: str = "1y") -> dict:
    """Get technical indicators (SMA20, SMA50, RSI14, MACD, volume) and plain-language signals."""
    return analysis.get_indicators(symbol, period)


@mcp.tool()
def run_python(code: str) -> dict:
    """Run a short Python script in an isolated sandbox and return its stdout/stderr.
    Use print() to output results. Allowed modules: math, statistics, json, datetime, random,
    decimal, fractions, itertools, collections, functools, numpy, pandas.
    No file access, no network, 15 second timeout."""
    return runner.run_python(code)


if __name__ == "__main__":
    mcp.run()