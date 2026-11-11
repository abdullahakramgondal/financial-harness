"""FH-20/21/33: Agent loop. Gemini + MCP tools -> list[Suggestion].
Run: python -m agent.agent
Phase 1: model tools call karke data jama karta hai.
Phase 2: structured output (JSON schema) se Suggestion list banti hai.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google import genai  # noqa: E402
from google.genai import errors, types  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from schemas import Suggestion  # noqa: E402

# Pehla model try hota hai, busy ho to agla. Comma se alag karke env se badal sakte ho:
# $env:AGENT_MODELS="gemini-3.1-flash-lite,gemini-3.8-flash"
MODELS = [
    m.strip()
    for m in os.getenv("AGENT_MODELS", "gemini-3.1-flash-lite,gemini-3.8-flash").split(",")
    if m.strip()
]
MAX_STEPS = 10
RETRIES_PER_MODEL = 3

SYSTEM = """You are a cautious portfolio-analysis assistant for an educational project.
Use the tools to fetch the portfolio, prices, candles and news before deciding.
Goals: 10 months, 20 months, 10 years. Respect each goal's risk level.
Never invent prices or news.
Never decide from news alone: for EACH holding also call get_candles (interval 1d, period 3mo)
to check the trend, and compare the current price with the holding's buy_price (P&L).
Mention the trend and P&L in your reasoning. A single negative headline is not enough
reason to SELL; prefer HOLD unless trend, P&L and news all point the same way.
When you have enough data, write a short analysis per holding
(HOLD, ACCUMULATE, BUY or SELL, with reasons and risks)."""


def generate_with_retry(client, **kwargs):
    """503/429/500 par retry, model band (404) ho ya bohat busy ho to agla model."""
    last_err = None
    for model in MODELS:
        for attempt in range(RETRIES_PER_MODEL):
            try:
                return client.models.generate_content(model=model, **kwargs)
            except (errors.ServerError, errors.ClientError) as e:
                last_err = e
                code = getattr(e, "code", None)
                if code == 404:
                    print(f"Model {model} available nahi (404), agla try...")
                    break
                if code not in (429, 500, 503):
                    raise
                wait = 5 * (attempt + 1)
                print(f"{model} busy ({code}), {wait}s baad retry {attempt+1}/{RETRIES_PER_MODEL}...")
                time.sleep(wait)
        else:
            print(f"{model} par retries khatam, agla model try...")
    raise RuntimeError(f"Saare models fail: {last_err}")


def _tool_text(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


async def run_agent(user_prompt: str | None = None) -> list[Suggestion]:
    prompt = user_prompt or (
        "Analyse my portfolio against my goals and give a suggestion for each holding."
    )
    client = genai.Client()  # GEMINI_API_KEY env var se key leta hai
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT)
    )

    gathered: list[str] = []  # tool outputs, phase 2 ke liye
    analysis = ""

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
                system_instruction=SYSTEM,
                tools=[types.Tool(function_declarations=decls)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

            for step in range(MAX_STEPS):
                resp = generate_with_retry(client, contents=contents, config=config)
                model_content = resp.candidates[0].content
                contents.append(model_content)

                calls = [p.function_call for p in model_content.parts if p.function_call]
                if not calls:
                    analysis = resp.text or ""
                    break

                response_parts = []
                for fc in calls:
                    args = dict(fc.args or {})
                    print(f"[step {step+1}] tool: {fc.name} {json.dumps(args)}")
                    try:
                        out = await session.call_tool(fc.name, args)
                        text = _tool_text(out)
                    except Exception as e:
                        text = f"Tool error: {e}"
                    gathered.append(f"## {fc.name}({json.dumps(args)})\n{text}")
                    response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name, response={"result": text}
                        )
                    )
                contents.append(types.Content(role="user", parts=response_parts))
            else:
                raise RuntimeError("MAX_STEPS khatam, analysis nahi mili")

    # Phase 2: structured output
    final_prompt = (
        f"User request: {prompt}\n\n"
        "Tool data:\n" + "\n\n".join(gathered) + f"\n\nAnalysis:\n{analysis}\n\n"
        "Ab har holding ke liye ek Suggestion do. data_timestamp tool data ke "
        "timestamp se copy karo. confidence 0 se 1 ke beech."
    )
    final = generate_with_retry(
        client,
        contents=final_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[Suggestion],
        ),
    )
    return [Suggestion(**s) for s in json.loads(final.text)]


if __name__ == "__main__":
    suggestions = asyncio.run(run_agent())
    for s in suggestions:
        print(s.model_dump_json(indent=2))