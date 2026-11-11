"""Guardrails: validate and size an agent suggestion before it becomes a paper trade."""
import math

from schemas import Suggestion

ALLOWED_SYMBOLS = {"AAPL", "TSLA", "NVDA"}
MIN_CONFIDENCE = 0.6      # no trade below this confidence
MAX_TRADE_PCT = 0.25      # a single buy is at most 25% of total portfolio value
MAX_POSITION_PCT = 0.40   # one stock is at most 40% of total portfolio value
MAX_SELL_PCT = 0.5        # a single sell is at most 50% of the current holding


def to_side(action: str) -> str | None:
    """Map a suggestion action to a trade side. HOLD means no trade."""
    return {"BUY": "BUY", "ACCUMULATE": "BUY", "SELL": "SELL"}.get(action)


def check(s: Suggestion, side: str, state: dict, prices: dict, total_value: float):
    """Return (approved_qty, note). approved_qty == 0 means the trade is rejected."""
    price = prices.get(s.symbol)
    if s.symbol not in ALLOWED_SYMBOLS:
        return 0, "symbol is not in the allowed list"
    if price is None:
        return 0, "price not available"
    if s.confidence < MIN_CONFIDENCE:
        return 0, f"confidence {s.confidence} is below {MIN_CONFIDENCE}"
    if s.quantity <= 0:
        return 0, "quantity is 0"

    requested = math.floor(s.quantity)
    held = state["positions"].get(s.symbol, {}).get("quantity", 0)

    if side == "SELL":
        if math.floor(held) <= 0:
            return 0, "no holding to sell (short selling is disabled)"
        max_sell = max(1, math.floor(held * MAX_SELL_PCT))
        qty = min(requested, math.floor(held), max_sell)
        if qty < requested:
            return qty, (
                f"quantity reduced from {requested} to {qty} "
                f"(max {int(MAX_SELL_PCT * 100)}% of holding per sell)"
            )
        return qty, "ok"

    # BUY: reduce the quantity to fit all limits
    by_cash = math.floor(state["cash"] / price)
    by_trade = math.floor(total_value * MAX_TRADE_PCT / price)
    by_position = math.floor((total_value * MAX_POSITION_PCT - held * price) / price)
    qty = min(requested, by_cash, by_trade, by_position)
    if qty <= 0:
        return 0, f"blocked by limits (cash: {by_cash}, trade cap: {by_trade}, position cap: {by_position})"
    if qty < requested:
        return qty, f"quantity reduced from {requested} to {qty} (limits)"
    return qty, "ok"