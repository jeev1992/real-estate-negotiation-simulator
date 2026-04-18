"""
Demo 02 — Trace the model <-> host <-> server tool loop
========================================================
Shows the full MCP tool-calling loop end to end with timestamps and a
human-readable narration of every step. Uses the `mcp` SDK for the
session (so we don't reinvent the handshake from demo 01) and OpenAI
function calling for the model side.

Run:
    python m2_mcp/demos/02_tool_loop_trace.py

What you will see (in order):
    [t=0.00s] HOST: connecting to MCP server
    [t=0.05s] HOST: tools/list
    [t=0.05s] SERVER: returned 2 tools
    [t=0.06s] MODEL: receiving prompt + tool catalog
    [t=1.20s] MODEL: emitted tool_use(get_market_price)
    [t=1.20s] HOST: translating tool_use -> tools/call
    [t=1.25s] SERVER: returned CallToolResult
    [t=1.25s] HOST: injecting tool_result back into model context
    [t=2.40s] MODEL: emitted final assistant text
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

PRICING_SERVER = REPO_ROOT / "m2_mcp" / "pricing_server.py"


_t0 = time.monotonic()


def log(actor: str, msg: str) -> None:
    print(f"[t={time.monotonic() - _t0:5.2f}s] {actor:<7s} {msg}")


def _mcp_tool_to_openai(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object"},
        },
    }


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set"); return

    log("HOST", "connecting to MCP server (stdio subprocess)")
    server_params = StdioServerParameters(
        command=sys.executable, args=[str(PRICING_SERVER)]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            log("HOST", "tools/list")
            catalog = await session.list_tools()
            log("SERVER", f"returned {len(catalog.tools)} tools")

            openai_tools = [_mcp_tool_to_openai(t) for t in catalog.tools]
            messages = [
                {"role": "system", "content": "You are a real estate pricing analyst. Use tools to answer."},
                {"role": "user", "content": "What is the estimated value of 742 Evergreen Terrace, Austin, TX 78701?"},
            ]

            client = AsyncOpenAI()
            log("MODEL", "receiving prompt + tool catalog")

            for hop in range(4):
                resp = await client.chat.completions.create(
                    model="gpt-4o", messages=messages, tools=openai_tools
                )
                choice = resp.choices[0].message
                if choice.tool_calls:
                    for call in choice.tool_calls:
                        log("MODEL", f"emitted tool_use({call.function.name})")
                        log("HOST", "translating tool_use -> tools/call")
                        args = json.loads(call.function.arguments or "{}")
                        result = await session.call_tool(call.function.name, args)
                        result_text = result.content[0].text if result.content else "{}"
                        log("SERVER", "returned CallToolResult")
                        log("HOST", "injecting tool_result back into model context")
                        messages.append(choice.model_dump(exclude_none=True))
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result_text,
                        })
                else:
                    log("MODEL", "emitted final assistant text")
                    print("\n--- final answer ---")
                    print(choice.content)
                    return
            log("HOST", "max hops reached without final answer")


if __name__ == "__main__":
    asyncio.run(main())
