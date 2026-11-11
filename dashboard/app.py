"""Streamlit dashboard. Run from the project root: streamlit run dashboard/app.py"""
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from agent.agent import run_agent  # noqa: E402
from agent.chat import run_chat  # noqa: E402
from mcp_server import data  # noqa: E402
from sandbox import guardrails, paper  # noqa: E402
from worker import store  # noqa: E402
from worker.tasks import deep_analysis  # noqa: E402

st.set_page_config(page_title="Financial Agent Harness", layout="wide")
st.title("Financial Agent Harness")
st.caption("Educational demo with paper trading only. Not financial advice.")

UP_COLOR = "#26a69a"
DOWN_COLOR = "#ef5350"
ACTIVE_STATUSES = ("QUEUED", "RUNNING", "RETRYING")


@st.cache_data(ttl=60)
def load_portfolio():
    return data.get_portfolio()


@st.cache_data(ttl=300)
def load_candles(symbol: str, period: str):
    return data.get_candles(symbol, "1d", period)


def candlestick_charts(df: pd.DataFrame):
    """Return (price_chart, volume_chart): candlesticks with SMA20/SMA50, and a volume bar chart."""
    color = alt.condition("datum.open <= datum.close", alt.value(UP_COLOR), alt.value(DOWN_COLOR))
    price_scale = alt.Scale(zero=False)
    base = alt.Chart(df).encode(x=alt.X("time:T", title=None))

    wick = base.mark_rule().encode(
        y=alt.Y("low:Q", scale=price_scale, title="Price (USD)"), y2="high:Q", color=color
    )
    body = base.mark_bar().encode(y=alt.Y("open:Q", scale=price_scale), y2="close:Q", color=color)
    sma20 = (
        base.transform_window(sma20="mean(close)", frame=[-19, 0])
        .mark_line(color="#ffa726")
        .encode(y=alt.Y("sma20:Q", scale=price_scale))
    )
    sma50 = (
        base.transform_window(sma50="mean(close)", frame=[-49, 0])
        .mark_line(color="#42a5f5")
        .encode(y=alt.Y("sma50:Q", scale=price_scale))
    )
    price_chart = (wick + body + sma20 + sma50).properties(height=320)
    volume_chart = base.mark_bar().encode(y=alt.Y("volume:Q", title="Volume"), color=color).properties(height=110)
    return price_chart, volume_chart


def review_suggestions(suggestions, execute: bool):
    """Run every suggestion through the guardrails. Optionally execute approved trades."""
    state = paper.load_state()
    symbols = set(state["positions"]) | {s.symbol for s in suggestions}
    prices = paper.get_prices(symbols)
    total = paper.total_value(state, prices)
    rows = []
    for s in suggestions:
        side = guardrails.to_side(s.action)
        price = prices.get(s.symbol)
        row = {
            "symbol": s.symbol,
            "action": s.action,
            "horizon": s.horizon,
            "confidence": s.confidence,
            "price": price,
            "reason": s.reason,
            "risk_note": s.risk_note,
        }
        if side is None:
            row.update(status="NO TRADE", qty=0, note="HOLD")
        else:
            qty, note = guardrails.check(s, side, state, prices, total)
            if qty <= 0:
                row.update(status="REJECTED", qty=0, note=note)
            elif execute:
                paper.execute(state, s.symbol, side, qty, price, s.reason)
                total = paper.total_value(state, prices)
                row.update(status="EXECUTED", qty=qty, note=note)
            else:
                row.update(status="APPROVED", qty=qty, note=note)
        rows.append(row)
    return rows


def render_record(rec: dict):
    """Show the answer and tool log of a finished background task."""
    if rec.get("answer"):
        st.markdown(rec["answer"])
    if rec.get("error"):
        st.error(rec["error"])
    if rec.get("tools"):
        with st.expander("Tools used"):
            st.code("\n".join(rec["tools"]))


@st.fragment(run_every=2)
def show_task_status():
    """Poll the saved status of the current background task every 2 seconds."""
    task_id = st.session_state.get("bg_task")
    if not task_id:
        st.info("No background task submitted yet.")
        return
    rec = store.read(task_id)
    if not rec:
        st.info("Waiting for the task record...")
        return

    status = rec.get("status", "?")
    st.write(f"**Task** `{task_id}`  |  **Status:** {status}  |  **Attempt:** {rec.get('attempt', '-')}")
    st.progress(min(int(rec.get("progress", 0)), 100) / 100, text=rec.get("message", ""))
    if status == "QUEUED":
        st.caption("Still queued? Check that the Celery worker is running in another terminal.")
    if status in ("DONE", "FAILED"):
        render_record(rec)


tab_chat, tab_portfolio, tab_agent, tab_paper, tab_bg = st.tabs(
    ["Chat", "Portfolio", "Agent suggestions", "Paper account", "Background analysis"]
)

# --------------------------------------------------------------------- Chat
with tab_chat:
    st.write(
        "Ask about any stock: technical analysis, fundamentals, comparisons, or what-if scenarios. "
        "Example: *Compare AAPL and NVDA on valuation and trend.*"
    )
    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    if st.button("Clear chat"):
        st.session_state["chat"] = []
        st.rerun()

    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("tools"):
                with st.expander("Tools used"):
                    st.code("\n".join(m["tools"]))

    prompt = st.chat_input("Ask about a stock...")
    if prompt:
        st.session_state["chat"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analysing..."):
                try:
                    history = [
                        {"role": m["role"], "content": m["content"]} for m in st.session_state["chat"]
                    ]
                    answer, tools = asyncio.run(run_chat(history))
                except Exception as e:
                    answer, tools = f"Analysis failed: {e}", []
            st.markdown(answer)
            if tools:
                with st.expander("Tools used"):
                    st.code("\n".join(tools))
        st.session_state["chat"].append({"role": "assistant", "content": answer, "tools": tools})

# ---------------------------------------------------------------- Portfolio
with tab_portfolio:
    p = load_portfolio()
    c1, c2, c3 = st.columns(3)
    c1.metric("Holdings value", f"${p['total_value']:,.2f}")
    c2.metric("Total P&L", f"${p['total_pnl']:,.2f}")
    c3.metric("Cash", f"${p['cash']:,.2f}")

    st.subheader("Holdings")
    st.dataframe(pd.DataFrame(p["holdings"]), width="stretch")

    st.subheader("Goals")
    st.dataframe(pd.DataFrame(p["goals"]), width="stretch")

    st.subheader("Price history")
    left, right = st.columns(2)
    symbol = left.selectbox("Symbol", [h["symbol"] for h in p["holdings"]])
    period = right.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=1)
    candles = load_candles(symbol, period)["candles"]
    if candles:
        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        price_chart, volume_chart = candlestick_charts(df)
        st.altair_chart(price_chart, width="stretch")
        st.altair_chart(volume_chart, width="stretch")
        st.caption("Candlesticks with SMA20 (orange) and SMA50 (blue). Green = close above open.")
    else:
        st.info("No candle data available.")
    st.caption(f"Data timestamp: {p['timestamp']} (source: yfinance)")

# ------------------------------------------------------------------- Agent
with tab_agent:
    st.write("The agent reads portfolio, candles and news, then suggests an action per holding.")
    if st.button("Run agent", type="primary"):
        with st.spinner("Agent is working (this can take a minute)..."):
            try:
                st.session_state["suggestions"] = asyncio.run(run_agent())
            except Exception as e:
                st.error(f"Agent failed: {e}")

    suggestions = st.session_state.get("suggestions")
    if suggestions:
        rows = review_suggestions(suggestions, execute=False)
        st.subheader("Suggestions and guardrail review")
        st.dataframe(pd.DataFrame(rows), width="stretch")

        if any(r["status"] == "APPROVED" for r in rows):
            if st.button("Execute approved trades on the paper account"):
                done = review_suggestions(suggestions, execute=True)
                st.success("Paper trades executed.")
                st.dataframe(pd.DataFrame(done), width="stretch")
        else:
            st.info("No trades to execute (all HOLD or rejected by guardrails).")

# ------------------------------------------------------------------- Paper
with tab_paper:
    state = paper.load_state()
    prices = paper.get_prices(state["positions"].keys())
    total = paper.total_value(state, prices)

    c1, c2 = st.columns(2)
    c1.metric("Paper cash", f"${state['cash']:,.2f}")
    c2.metric("Paper total value", f"${total:,.2f}")

    st.subheader("Positions")
    pos_rows = []
    for sym, pos in state["positions"].items():
        price = prices.get(sym)
        value = pos["quantity"] * price if price else None
        pnl = (price - pos["avg_price"]) * pos["quantity"] if price else None
        pos_rows.append(
            {"symbol": sym, "quantity": pos["quantity"], "avg_price": pos["avg_price"],
             "price": price, "value": value, "pnl": pnl}
        )
    st.dataframe(pd.DataFrame(pos_rows), width="stretch")

    st.subheader("Trade history")
    if state["trades"]:
        st.dataframe(pd.DataFrame(state["trades"]), width="stretch")
    else:
        st.info("No paper trades yet.")

    if st.button("Reset paper account"):
        paper.reset_state()
        st.rerun()

# -------------------------------------------------------------- Background
with tab_bg:
    st.write(
        "Submit a long analysis to the background worker (Celery). It runs in a separate process "
        "with progress tracking, automatic retries and saved results."
    )
    question = st.text_area(
        "Analysis request",
        value=(
            "Write a full analysis report for NVDA: technical indicators, fundamentals, "
            "and a what-if projection of $2000 growing 10% a year for 5 years."
        ),
        height=100,
    )
    if st.button("Submit to background worker", type="primary"):
        task_id = uuid.uuid4().hex[:12]
        store.write(
            task_id, status="QUEUED", progress=0, message="Waiting for a worker", question=question
        )
        deep_analysis.apply_async(args=[task_id, question], task_id=task_id)
        st.session_state["bg_task"] = task_id

    show_task_status()

    st.subheader("Saved results")
    recent = store.list_recent()
    if recent:
        labels = [
            f"{r.get('updated', '')} | {r.get('status', '?')} | {str(r.get('question', ''))[:60]}"
            for r in recent
        ]
        choice = st.selectbox("Past analyses", range(len(recent)), format_func=lambda i: labels[i])
        picked = recent[choice]
        st.caption(f"Question: {picked.get('question', '')}")
        render_record(picked)
    else:
        st.info("No saved results yet.")