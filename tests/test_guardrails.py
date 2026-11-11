"""Guardrail unit tests. No network and no LLM needed."""
from sandbox import guardrails
from schemas import Suggestion

STATE = {
    "cash": 5000.0,
    "positions": {
        "AAPL": {"quantity": 10, "avg_price": 170.0},
        "TSLA": {"quantity": 5, "avg_price": 220.0},
        "NVDA": {"quantity": 8, "avg_price": 120.0},
    },
}
PRICES = {"AAPL": 348.0, "TSLA": 377.0, "NVDA": 167.0, "MSFT": 400.0}
TOTAL = 11700.0


def make(symbol, action, quantity, confidence=0.9):
    return Suggestion(
        symbol=symbol, action=action, horizon="short_term",
        quantity=quantity, reason="test", confidence=confidence,
    )


def test_hold_means_no_trade():
    assert guardrails.to_side("HOLD") is None
    assert guardrails.to_side("ACCUMULATE") == "BUY"
    assert guardrails.to_side("SELL") == "SELL"


def test_symbol_not_allowed():
    qty, note = guardrails.check(make("MSFT", "BUY", 1), "BUY", STATE, PRICES, TOTAL)
    assert qty == 0 and "allowed" in note


def test_low_confidence_rejected():
    qty, note = guardrails.check(make("TSLA", "BUY", 2, confidence=0.3), "BUY", STATE, PRICES, TOTAL)
    assert qty == 0 and "confidence" in note


def test_sell_capped_at_half_of_holding():
    qty, note = guardrails.check(make("AAPL", "SELL", 50), "SELL", STATE, PRICES, TOTAL)
    assert qty == 5 and "50%" in note


def test_sell_without_holding_rejected():
    state = {"cash": 100.0, "positions": {}}
    qty, _ = guardrails.check(make("AAPL", "SELL", 1), "SELL", state, PRICES, TOTAL)
    assert qty == 0


def test_buy_reduced_by_trade_cap():
    qty, note = guardrails.check(make("NVDA", "BUY", 100), "BUY", STATE, PRICES, TOTAL)
    assert qty == 17 and "limits" in note