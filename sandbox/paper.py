"""FH-40..44: Paper trading. Asli paisa nahi, sirf paper_state.json mein virtual trades."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp_server import data  # noqa: E402

STATE_PATH = ROOT / "paper_state.json"
PORTFOLIO_PATH = ROOT / "portfolio.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    p = json.loads(PORTFOLIO_PATH.read_text())
    state = {
        "cash": p["cash"],
        "positions": {
            h["symbol"]: {"quantity": h["quantity"], "avg_price": h["buy_price"]}
            for h in p["holdings"]
        },
        "trades": [],
    }
    save_state(state)
    return state


def reset_state() -> dict:
    STATE_PATH.unlink(missing_ok=True)
    return load_state()


def get_prices(symbols) -> dict:
    return {s: data.get_price(s).get("price") for s in symbols}


def total_value(state: dict, prices: dict) -> float:
    v = state["cash"]
    for sym, pos in state["positions"].items():
        v += pos["quantity"] * (prices.get(sym) or pos["avg_price"])
    return v


def execute(state: dict, symbol: str, side: str, qty: int, price: float, reason: str) -> None:
    pos = state["positions"].get(symbol, {"quantity": 0, "avg_price": 0.0})
    if side == "BUY":
        cost = qty * price
        new_q = pos["quantity"] + qty
        pos["avg_price"] = round((pos["quantity"] * pos["avg_price"] + cost) / new_q, 4)
        pos["quantity"] = new_q
        state["cash"] = round(state["cash"] - cost, 2)
        state["positions"][symbol] = pos
    else:  # SELL
        pos["quantity"] -= qty
        state["cash"] = round(state["cash"] + qty * price, 2)
        if pos["quantity"] <= 0:
            state["positions"].pop(symbol, None)
        else:
            state["positions"][symbol] = pos
    state["trades"].append(
        {"time": _now(), "symbol": symbol, "side": side, "qty": qty,
         "price": price, "reason": reason}
    )
    save_state(state)