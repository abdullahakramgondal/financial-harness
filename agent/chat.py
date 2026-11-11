"""Conversational analysis agent. Gemini + MCP tools -> a markdown answer.
Used by the Chat tab and by the background worker.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from agent.agent import _tool_text, generate_with_retry  # noqa: E402

CHAT_MAX_STEPS = 12

CHAT_SYSTEM = """You are an AI stock market assistant for an educational project.
Always fetch real data with the tools before answering. Never invent prices, ratios or news.

How to answer:
- Technical questions: call get_indicators (and get_candles if you need raw candles).
- Fundamental questions: call get_fundamentals.
- Comparisons: call the tools for every symbol and compare them side by side in a markdown table.
- Calculations, projections and what-if scenarios: NEVER do arithmetic yourself. Write a short
  Python script and run it with run_python, using print() to output the results. Fetch the
  current price first with get_price when the scenario depends on it. Put every assumption
  (growth rate, years, amounts) in variables at the top of the script, and label the result as
  hypothetical, not a prediction.
- If run_python reports a script error or a blocked import, fix the script and try again.
- If run_python times out or keeps failing after two attempts, STOP. Do not calculate the numbers
  yourself and do not hardcode results in a script. Tell the user plainly that the calculation
  sandbox failed and that you could not produce verified numbers.
- The user's own holdings and goals are available through get_portfolio.
- End every answer with a short "Sources and assumptions" line that names the data source
  and the data timestamp from the tool results.
- This is educational analysis, not financial advice. Do not tell the user to buy or sell;
  explain the evidence and the trade-offs instead.
- Keep answers concise and clear."""


def _notify(on_progress, pct: int, message: str) -> None:
    if on_progress:
        on_progress(pct, message)


async def run_chat(history: list[dict], on_progress=None) -> tuple[str, list[str]]:
    """history: list of {"role": "user" | "assistant", "content": str}, ending with a user message.
    on_progress: optional callback (percent: int, message: str) used for progress tracking.
    Returns (answer_markdown, tool_log)."""
    client = genai.Client()  # reads the key from the GEMINI_API_KEY environment variable
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT)
    )

    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
    ]
    tool_log: list[str] = []
    answer = ""

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            decls = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description or "",
                    parameters_json_schema=t.inputSchema,
                )
                for t in listed.tools
            ]
            config = types.GenerateContentConfig(
                system_instruction=CHAT_SYSTEM,
                tools=[types.Tool(function_declarations=decls)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            for step in range(CHAT_MAX_STEPS):
                _notify(on_progress, min(90, 8 + step * 8), f"Step {step + 1}: model is thinking")
                resp = generate_with_retry(client, contents=contents, config=config)
                model_content = resp.candidates[0].content
                contents.append(model_content)

                calls = [p.function_call for p in model_content.parts if p.function_call]
                if not calls:
                    answer = resp.text or ""
                    break

                response_parts = []
                for fc in calls:
                    args = dict(fc.args or {})
                    _notify(on_progress, min(90, 12 + step * 8), f"Calling tool: {fc.name}")
                    if fc.name == "run_python":
                        tool_log.append("run_python:\n" + str(args.get("code", "")))
                    else:
                        tool_log.append(f"{fc.name} {json.dumps(args)}")
                    try:
                        out = await session.call_tool(fc.name, args)
                        text = _tool_text(out)
                    except Exception as e:
                        text = f"Tool error: {e}"
                    if fc.name == "run_python":
                        tool_log.append("output:\n" + text)
                    response_parts.append(
                        types.Part.from_function_response(name=fc.name, response={"result": text})
                    )
                contents.append(types.Content(role="user", parts=response_parts))
            else:
                answer = "I could not finish the analysis within the step limit. Please try a narrower question."

    return answer, tool_log