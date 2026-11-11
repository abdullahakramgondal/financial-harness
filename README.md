# Financial Agent Harness (starter)

## Aaj raat
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python check_data.py                                   # real price print hona chahiye
mcp dev mcp_server/server.py                           # MCP Inspector mein 4 tools dikhenge
```

## Structure
```
schemas.py          FH-19  shared JSON formats (Holding, Goal, Portfolio, Suggestion)
portfolio.json      FH-22  hardcoded AAPL/TSLA/NVDA + 3 goals
mcp_server/data.py  FH-26..31  get_price / get_candles / get_news / get_portfolio
mcp_server/server.py FH-27..32 MCP server (inko tools banata hai)
check_data.py       quick test
```

## Aglay steps
3. agent/  -> agent loop + MCP tool calling (FH-20, 21, 33)
4. sandbox/ -> Docker runner (FH-36), PTC (FH-34, 37)
5. sandbox/paper.py -> paper trading + guardrails (FH-40..44)
6. dashboard/app.py -> Streamlit (FH-50..53)
