"""
GitHub MCP Agent Client
========================
An LLM-powered agent that connects to GitHub's MCP server and uses
GPT-4o to decide which tools to call based on your natural language query.

WHY THIS EXISTS:
  This demonstrates the SAME agentic pattern used by our buyer and seller
  agents in Module 3 — but against GitHub's real MCP server, a tool every
  engineer already knows:

  1. Connect to an MCP server and discover tools (list_tools)
  2. Give the LLM the tool schemas so it knows what's available
  3. Let the LLM DECIDE which tools to call based on the task
  4. Execute the tool calls via MCP and feed results back to the LLM
  5. LLM either calls more tools or produces a final answer

  The key insight: the agent is NOT scripted. It reads the query, sees the
  available tools, and decides its own action plan — just like our buyer
  agent decides whether to call get_market_price or calculate_discount.

PREREQUISITES:
  1. Node.js 18+ installed (for npx)
  2. GITHUB_TOKEN — GitHub Personal Access Token
  3. OPENAI_API_KEY — OpenAI API key

HOW TO RUN:
  export GITHUB_TOKEN=ghp_your_token_here
  export OPENAI_API_KEY=sk-your_key_here
  python m2_mcp/github_agent_client.py

  # Or with a custom query:
  python m2_mcp/github_agent_client.py "What are the top Python MCP repos?"

SAMPLE QUERIES TO TRY:
  python m2_mcp/github_agent_client.py "Find popular real estate Python projects"
  python m2_mcp/github_agent_client.py "What repos implement MCP servers? Show the top 5 by stars"
  python m2_mcp/github_agent_client.py "Search for LangGraph multi-agent examples and summarize them"
  python m2_mcp/github_agent_client.py "Find open issues about MCP in the modelcontextprotocol/python-sdk repo"
  python m2_mcp/github_agent_client.py "What is the latest release of openai/openai-python?"
"""

import asyncio
import json
import os
import sys
from typing import Any

from openai import AsyncOpenAI

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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


# ─── Validation ───────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

_PLACEHOLDER_PREFIXES = ("your_token", "ghp_your", "<your", "TOKEN_HERE")
if not GITHUB_TOKEN or any(GITHUB_TOKEN.lower().startswith(p) for p in _PLACEHOLDER_PREFIXES):
    print("ERROR: GITHUB_TOKEN not set (or is a placeholder).")
    print("   Get one at: GitHub -> Settings -> Developer Settings -> Personal Access Tokens")
    sys.exit(1)

if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
    print("ERROR: OPENAI_API_KEY not set (or is a placeholder).")
    sys.exit(1)


OPENAI_MODEL = "gpt-4o"

# ─── Sample queries ───────────────────────────────────────────────────────────
# Each query exercises a different set of GitHub MCP tools.
# The agent reads the query, sees the available tools, and decides its own plan.

SAMPLE_QUERIES = [
    "Find popular real estate Python projects on GitHub",
    "What repos implement MCP servers? Show the top 5 by stars",
    "Search for LangGraph multi-agent examples and summarize them",
    "Find open issues about MCP in the modelcontextprotocol/python-sdk repo",
    "What is the latest release of openai/openai-python?",
]


# ─── MCP Tool Schema -> OpenAI Function Schema ───────────────────────────────

def mcp_tools_to_openai_functions(mcp_tools: list) -> list[dict]:
    """
    Convert MCP tool schemas into OpenAI function-calling format.

    MCP tools describe themselves with JSON Schema (inputSchema).
    OpenAI expects the same schemas under a slightly different wrapper.
    This bridge lets the LLM see MCP tools as callable functions.
    """
    functions = []
    for tool in mcp_tools:
        input_schema = (
            tool.inputSchema.model_dump()
            if hasattr(tool.inputSchema, "model_dump")
            else tool.inputSchema
        )
        # Ensure it's a valid object schema for OpenAI
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


# ─── Agent loop ───────────────────────────────────────────────────────────────

async def run_agent(query: str) -> str:
    """
    Agentic loop: connect to GitHub MCP server, let GPT-4o decide
    which tools to call, execute them, and produce a final answer.

    This follows a ReAct-style tool-use loop:
      1. Discover tools (list_tools)
      2. Give tool schemas to the LLM
      3. LLM returns tool_calls -> we execute them via MCP
      4. Feed results back -> LLM either calls more tools or responds
      5. Return the final text answer
    """
    print("=" * 65)
    print("GITHUB MCP AGENT")
    print("An LLM that decides which GitHub tools to call")
    print("=" * 65)
    print()

    # ── 1. Connect to GitHub MCP server ───────────────────────────────────
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,
            "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
        },
    )

    print(f"[Agent] Connecting to GitHub MCP server...")
    print(f"[Agent] Query: {query}")
    print()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 2. Discover tools ─────────────────────────────────────────
            tools_response = await session.list_tools()
            mcp_tools = tools_response.tools
            openai_tools = mcp_tools_to_openai_functions(mcp_tools)

            print(f"[Agent] Discovered {len(mcp_tools)} GitHub MCP tools")
            print()

            # Build a name->tool lookup for execution
            tools_by_name = {t.name: t for t in mcp_tools}

            # ── 3. Start the agent loop ───────────────────────────────────
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            messages: list[dict] = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful GitHub research assistant. "
                        "You have access to GitHub MCP tools to search repos, "
                        "read code, list issues, and more. "
                        "Use the tools to answer the user's question thoroughly. "
                        "After gathering data, provide a clear summary."
                    ),
                },
                {"role": "user", "content": query},
            ]

            # Agent loop — up to 5 iterations of tool calling
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

                # If the LLM wants to call tools, execute them
                if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Add the assistant message (with tool_calls) to history
                    messages.append(choice.message.model_dump())

                    for tool_call in choice.message.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)

                        print(f"[Agent]   -> Calling: {fn_name}({json.dumps(fn_args)})")

                        # Execute via MCP
                        if fn_name in tools_by_name:
                            try:
                                mcp_result = await session.call_tool(fn_name, fn_args)
                                result_text = _parse_tool_result(mcp_result)
                            except Exception as e:
                                result_text = json.dumps({"error": str(e)})
                        else:
                            result_text = json.dumps({"error": f"Unknown tool: {fn_name}"})

                        # Feed the tool result back to the LLM
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        })

                    print()
                else:
                    # LLM is done — it produced a final text response
                    final_answer = choice.message.content or "(no response)"
                    print()
                    print("=" * 65)
                    print("AGENT ANSWER")
                    print("=" * 65)
                    print()
                    print(final_answer)
                    print()
                    return final_answer

            # If we exhausted iterations, ask for a summary with no tools
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

async def run_all_samples() -> None:
    """Run the agent against every sample query in SAMPLE_QUERIES."""
    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print(f"\n{'#' * 65}")
        print(f"  SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)}")
        print(f"{'#' * 65}")
        await run_agent(query)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Custom query from the command line
        asyncio.run(run_agent(" ".join(sys.argv[1:])))
    else:
        # No args — loop through all sample queries
        asyncio.run(run_all_samples())
