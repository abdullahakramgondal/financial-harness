"""Pehla test: python check_data.py
Agar price print ho jaye to data layer kaam kar rahi hai (aaj raat ka goal)."""
import json
from mcp_server import data

print("PRICE :", json.dumps(data.get_price("AAPL"), indent=2))
c = data.get_candles("AAPL", "1d", "5d")
print("CANDLES:", len(c["candles"]), "rows, last =", c["candles"][-1] if c["candles"] else None)
print("NEWS  :", json.dumps(data.get_news("AAPL", 3), indent=2)[:600])
print("PORTFOLIO:", json.dumps(data.get_portfolio(), indent=2)[:900])
