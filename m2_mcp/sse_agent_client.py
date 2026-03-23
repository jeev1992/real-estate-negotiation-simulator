"""
SSE MCP Agent Client
====================
An LLM-powered agent that connects to our real estate MCP servers running
in SSE (HTTP) mode and lets GPT-4o decide which tools to call based on
your natural language query.

WHY SSE?
  stdio:  Server runs as a child process (1:1 coupling).
  SSE:    Server runs as an HTTP endpoint — multiple clients can connect
          at once, and the server can live on another machine or container.

  This script uses the SAME agentic pattern as github_agent_client.py,
  but connects over HTTP instead of stdio — proving the transport is
  irrelevant to the agent. Same protocol, same tool loop, different wire.

PREREQUISITES:
  Start the MCP servers in SSE mode first (in separate terminals):
    python m2_mcp/pricing_server.py --sse --port 8001
    python m2_mcp/inventory_server.py --sse --port 8002

HOW TO RUN:
  python m2_mcp/sse_agent_client.py

  # With a custom query:
  python m2_mcp/sse_agent_client.py "Is this property overpriced?"

  # Connect to both pricing + inventory servers:
  python m2_mcp/sse_agent_client.py --both "What is the seller's minimum price and how does it compare to market?"

SAMPLE QUERIES:
  python m2_mcp/sse_agent_client.py "What is the market price for 742 Evergreen Terrace?"
  python m2_mcp/sse_agent_client.py "Calculate a discount for a $485K property in a balanced market"
  python m2_mcp/sse_agent_client.py --both "What's the inventory in 78701 and the seller's minimum price?"
  python m2_mcp/sse_agent_client.py --both "Should I offer below asking? Use all available data to decide"
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from openai import AsyncOpenAI

from mcp import ClientSession
from mcp.client.sse import sse_client


# ─── Env loading ──────────────────────────────────────────────────────────────

def _load_env_file_if_present(env_path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file. Existing env vars take priority."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_env_file_if_present()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
    print("ERROR: OPENAI_API_KEY not set (or is a placeholder).")
    sys.exit(1)

OPENAI_MODEL = "gpt-4o"

SAMPLE_QUERIES_PRICING = [
    "What is the market price for 742 Evergreen Terrace, Austin, TX 78701? It's a single-family home.",
    "Calculate a discount for a $485K single-family property in a balanced market, listed 30 days, good condition.",
]

SAMPLE_QUERIES_BOTH = [
    "What's the inventory level in zip code 78701? Based on that, is it a buyer's or seller's market?",
    "I'm looking at 742 Evergreen Terrace, Austin TX 78701 listed at $485K. Get the market price, inventory for 78701, and the seller's minimum. Should I offer below asking?",
]


# ─── MCP Tool Schema -> OpenAI Function Schema ───────────────────────────────

def mcp_tools_to_openai_functions(mcp_tools: list) -> list[dict]:
    """Convert MCP tool schemas into OpenAI function-calling format."""
    functions = []
    for tool in mcp_tools:
        input_schema = (
            tool.inputSchema.model_dump()
            if hasattr(tool.inputSchema, "model_dump")
            else tool.inputSchema
        )
        if not isinstance(input_schema, dict):
            input_schema = {"type": "object", "properties": {}}
        if "type" not in input_schema:
            input_schema["type"] = "object"

        functions.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": (tool.description or "")[:1024],
                "parameters": input_schema,
            },
        })
    return functions


# ─── Result parsing ──────────────────────────────────────────────────────────

def _parse_tool_result(result: Any) -> str:
    """Extract text from MCP tool result content blocks."""
    if result.content and len(result.content) > 0:
        return result.content[0].text
    return "{}"


# ─── Agent loop for a single SSE server ───────────────────────────────────────

async def run_agent_on_server(
    url: str, label: str, query: str, messages: list[dict], openai_tools: list[dict],
    tools_by_name: dict, client: AsyncOpenAI,
) -> list[dict]:
    """
    Run the agentic tool-calling loop against one SSE-connected MCP server.
    Returns the updated messages list.
    """
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Discover tools on this server
            tools_response = await session.list_tools()
            server_tools = tools_response.tools

            print(f"[Agent] Connected to {label} ({url})")
            print(f"[Agent] Discovered {len(server_tools)} tools:")
            for t in server_tools:
                print(f"         - {t.name}")
            print()

            # Merge this server's tools into the shared collections
            for t in server_tools:
                tools_by_name[t.name] = (t, session)
            openai_tools.extend(mcp_tools_to_openai_functions(server_tools))

    return messages


async def run_agent(
    query: str,
    pricing_url: str | None,
    inventory_url: str | None,
) -> str:
    """
    Agentic loop: connect to real estate MCP servers via SSE,
    let GPT-4o decide which tools to call, execute them, produce an answer.
    """
    print()
    print("=" * 65)
    print("SSE MCP AGENT")
    print("An LLM that decides which real estate tools to call over HTTP")
    print("=" * 65)
    print()
    print(f"[Agent] Query: {query}")
    print()

    openai_tools: list[dict] = []
    # Map tool_name -> MCP tool object (for schema reference)
    all_mcp_tools: dict[str, Any] = {}

    # ── Discover tools from each server ───────────────────────────────
    server_sessions: dict[str, tuple[str, str]] = {}  # tool_name -> (url, label)

    if pricing_url:
        async with sse_client(pricing_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                print(f"[Agent] Connected to Pricing Server ({pricing_url})")
                print(f"[Agent] Discovered {len(tools_response.tools)} tools:")
                for t in tools_response.tools:
                    print(f"         - {t.name}")
                    all_mcp_tools[t.name] = t
                    server_sessions[t.name] = (pricing_url, "Pricing")
                openai_tools.extend(mcp_tools_to_openai_functions(tools_response.tools))
                print()

    if inventory_url:
        async with sse_client(inventory_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                print(f"[Agent] Connected to Inventory Server ({inventory_url})")
                print(f"[Agent] Discovered {len(tools_response.tools)} tools:")
                for t in tools_response.tools:
                    print(f"         - {t.name}")
                    all_mcp_tools[t.name] = t
                    server_sessions[t.name] = (inventory_url, "Inventory")
                openai_tools.extend(mcp_tools_to_openai_functions(tools_response.tools))
                print()

    if not openai_tools:
        print("ERROR: No MCP servers connected. Start servers first:")
        print("  python m2_mcp/pricing_server.py --sse --port 8001")
        print("  python m2_mcp/inventory_server.py --sse --port 8002")
        return ""

    # ── Agent loop ────────────────────────────────────────────────────
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "You are a real estate market analyst. "
                "You have access to MCP tools for pricing, discounts, and inventory data. "
                "Use the tools to answer the user's question with specific data. "
                "After gathering data, provide a clear, actionable summary."
            ),
        },
        {"role": "user", "content": query},
    ]

    max_iterations = 5
    for iteration in range(1, max_iterations + 1):
        print(f"[Agent] Iteration {iteration}: calling GPT-4o...")

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=openai_tools,
            temperature=0.2,
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"[Agent]   -> Calling: {fn_name}({json.dumps(fn_args)})")

                if fn_name in server_sessions:
                    url, label = server_sessions[fn_name]
                    try:
                        async with sse_client(url) as (rs, ws):
                            async with ClientSession(rs, ws) as sess:
                                await sess.initialize()
                                mcp_result = await sess.call_tool(fn_name, fn_args)
                                result_text = _parse_tool_result(mcp_result)
                    except Exception as e:
                        result_text = json.dumps({"error": str(e)})
                else:
                    result_text = json.dumps({"error": f"Unknown tool: {fn_name}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text,
                })

            print()
        else:
            final_answer = choice.message.content or "(no response)"
            print()
            print("=" * 65)
            print("AGENT ANSWER")
            print("=" * 65)
            print()
            print(final_answer)
            print()
            return final_answer

    # Exhausted iterations — request summary
    print("[Agent] Max iterations reached, requesting final summary...")
    messages.append({
        "role": "user",
        "content": "Please summarize your findings based on the data you've gathered so far.",
    })
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.2,
    )
    final_answer = response.choices[0].message.content or "(no response)"
    print()
    print("=" * 65)
    print("AGENT ANSWER")
    print("=" * 65)
    print()
    print(final_answer)
    print()
    return final_answer


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_all_samples(pricing_url: str | None, inventory_url: str | None) -> None:
    """Run the agent against sample queries appropriate for the connected servers."""
    queries = list(SAMPLE_QUERIES_PRICING)
    if inventory_url:
        queries.extend(SAMPLE_QUERIES_BOTH)

    for i, query in enumerate(queries, 1):
        print(f"\n{'#' * 65}")
        print(f"  SAMPLE QUERY {i}/{len(queries)}")
        print(f"{'#' * 65}")
        await run_agent(query, pricing_url, inventory_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SSE MCP Agent Client")
    parser.add_argument(
        "query",
        nargs="*",
        help="Natural language query (default: runs all sample queries)",
    )
    parser.add_argument(
        "--pricing-url",
        default="http://localhost:8001/sse",
        help="SSE URL for the pricing server (default: http://localhost:8001/sse)",
    )
    parser.add_argument(
        "--inventory-url",
        default=None,
        help="SSE URL for the inventory server (default: http://localhost:8002/sse)",
    )
    parser.add_argument(
        "--both",
        action="store_true",
        help="Connect to both pricing and inventory servers (default ports)",
    )

    args = parser.parse_args()

    pricing = args.pricing_url
    inventory = args.inventory_url

    if args.both:
        pricing = pricing or "http://localhost:8001/sse"
        inventory = inventory or "http://localhost:8002/sse"

    if args.query:
        asyncio.run(run_agent(" ".join(args.query), pricing, inventory))
    else:
        asyncio.run(run_all_samples(pricing, inventory))
