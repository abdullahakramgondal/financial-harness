"""Agent chalao -> guardrails -> paper trades. Run: python run_paper.py   (reset: python run_paper.py --reset)"""
import asyncio
import sys

from agent.agent import run_agent
from sandbox import guardrails, paper


def main():
    if "--reset" in sys.argv:
        paper.reset_state()
        print("Paper state reset ho gaya.")
        return

    suggestions = asyncio.run(run_agent())
    state = paper.load_state()
    symbols = set(state["positions"]) | {s.symbol for s in suggestions}
    prices = paper.get_prices(symbols)
    total = paper.total_value(state, prices)
    print(f"\nShuru: cash={state['cash']}, total value={round(total, 2)}\n")

    for s in suggestions:
        side = guardrails.to_side(s.action)
        if side is None:
            print(f"{s.symbol}: {s.action} -> koi trade nahi")
            continue
        qty, note = guardrails.check(s, side, state, prices, total)
        if qty <= 0:
            print(f"{s.symbol}: {side} REJECTED -> {note}")
            continue
        paper.execute(state, s.symbol, side, qty, prices[s.symbol], s.reason)
        print(f"{s.symbol}: {side} {qty} @ {prices[s.symbol]} EXECUTED ({note})")
        total = paper.total_value(state, prices)

    print(f"\nAkhir: cash={state['cash']}, total value={round(total, 2)}")
    print("Positions:", state["positions"])


if __name__ == "__main__":
    main()