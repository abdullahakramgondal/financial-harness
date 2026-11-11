"""Guardrails + paper trading test, bina agent/LLM ke. Run: python test_guardrails.py"""
from sandbox import guardrails, paper
from schemas import Suggestion

paper.reset_state()  # saaf state se shuru
state = paper.load_state()
prices = paper.get_prices(set(state["positions"]) | {"NVDA", "TSLA", "AAPL"})
total = paper.total_value(state, prices)
print(f"Shuru: cash={state['cash']}, total={round(total, 2)}\n")

tests = [
    Suggestion(symbol="NVDA", action="BUY", horizon="short_term", quantity=100, reason="test: bohat zyada qty", confidence=0.9),
    Suggestion(symbol="TSLA", action="BUY", horizon="short_term", quantity=2, reason="test: kam confidence", confidence=0.3),
    Suggestion(symbol="AAPL", action="SELL", horizon="short_term", quantity=3, reason="test: normal sell", confidence=0.8),
    Suggestion(symbol="TSLA", action="SELL", horizon="short_term", quantity=50, reason="test: holding se zyada", confidence=0.8),
    Suggestion(symbol="MSFT", action="BUY", horizon="long_term", quantity=1, reason="test: allowed list mein nahi", confidence=0.9),
]

for s in tests:
    side = guardrails.to_side(s.action)
    qty, note = guardrails.check(s, side, state, prices, total)
    if qty <= 0:
        print(f"{s.symbol} {side} {s.quantity}: REJECTED -> {note}")
        continue
    paper.execute(state, s.symbol, side, qty, prices[s.symbol], s.reason)
    total = paper.total_value(state, prices)
    print(f"{s.symbol} {side} {s.quantity}: EXECUTED {qty} @ {prices[s.symbol]} ({note})")

print(f"\nAkhir: cash={state['cash']}, total={round(total, 2)}")
print("Positions:", state["positions"])