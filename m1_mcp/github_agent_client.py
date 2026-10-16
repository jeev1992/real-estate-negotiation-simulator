"""
GitHub MCP Agent Client
========================
An LLM-powered agent that connects to GitHub's official MCP server and lets
the model decide which tools to call based on your natural language query.
It also shows the two primitives the model does NOT drive — resources and
prompts — so you can see all three on a server every engineer knows.

WHY THIS EXISTS:
  This demonstrates the SAME agentic pattern used by our buyer and seller
  agents in Module 2 — but against GitHub's real MCP server:

  1. Connect to an MCP server and discover its primitives
     (tools/list, resources/templates/list, prompts/list)
  2. HOST step: optionally read a RESOURCE (e.g. a repo's README) and attach
     it to the conversation as context. The model never "calls" a resource.
  3. Give the LLM the tool schemas so it knows what's available
  4. Let the LLM DECIDE which tools to call based on the task
  5. Execute the tool calls via MCP and feed results back to the LLM
  6. LLM either calls more tools or produces a final answer

  The key insight: tools are model-controlled (the agent picks them), while
  resources are application-controlled (the host decides what to attach).

THE SERVER:
  GitHub hosts its official MCP server at https://api.githubcopilot.com/mcp/
  (Streamable HTTP, authenticated with your token as a Bearer header). We use
  the /readonly endpoint so a demo can never modify anything on GitHub.
  No Node.js or Docker needed.

PREREQUISITES:
  1. GITHUB_TOKEN — a real GitHub Personal Access Token (read access to
     public repositories is enough)
  2. OPENAI_API_KEY — OpenAI API key

HOW TO RUN:
  python m1_mcp/github_agent_client.py               # runs the sample queries

  # Custom query (tools only):
  python m1_mcp/github_agent_client.py "What are the top Python MCP repos?"

  # Custom query with a resource attached by the host:
  python m1_mcp/github_agent_client.py \\
      --attach repo://modelcontextprotocol/python-sdk/contents/README.md \\
      "Summarize what this SDK provides"
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx
from openai import AsyncOpenAI

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


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


OPENAI_MODEL = "gpt-4o-mini"

# GitHub's hosted MCP server, read-only endpoint (no write tools exposed).
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/readonly"

# Resources can be large; cap what the host attaches to the conversation.
MAX_RESOURCE_CHARS = 8_000

# ─── Sample queries ───────────────────────────────────────────────────────────
# (query, resource URI the host attaches first — or None for tools only)

SAMPLE_QUERIES: list[tuple[str, str | None]] = [
    ("Find popular real estate Python projects on GitHub", None),
    (
        "Using the attached README, explain in two sentences what the MCP Python SDK "
        "provides. Then use your tools to list 3 open issues in "
        "modelcontextprotocol/python-sdk that mention resources.",
        "repo://modelcontextprotocol/python-sdk/contents/README.md",
    ),
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


# ─── Primitive discovery (tools, resources, prompts) ─────────────────────────

async def discover_primitives(session: ClientSession, capabilities: Any) -> list:
    """List all three MCP primitives the server offers and return its tools."""
    tools = (await session.list_tools()).tools
    print(f"[Agent] TOOLS ({len(tools)}) — model-controlled: the LLM decides when to call them")
    print(f"        e.g. {', '.join(t.name for t in tools[:6])}, ...")

    if capabilities.resources:
        templates = (await session.list_resource_templates()).resourceTemplates
        print(f"[Agent] RESOURCE TEMPLATES ({len(templates)}) — application-controlled: the host reads them")
        for template in templates:
            print(f"        {template.uriTemplate}")

    if capabilities.prompts:
        prompts = (await session.list_prompts()).prompts
        print(f"[Agent] PROMPTS ({len(prompts)}) — user-controlled: picked by a person, not the model")
        print(f"        {', '.join(p.name for p in prompts)}")

    print()
    return tools


async def read_resource_text(session: ClientSession, uri: str) -> str:
    """HOST step: read a resource and return its text (truncated for the prompt)."""
    result = await session.read_resource(uri)
    text = "\n".join(c.text for c in result.contents if getattr(c, "text", None))
    if len(text) > MAX_RESOURCE_CHARS:
        text = text[:MAX_RESOURCE_CHARS] + "\n...[truncated by host]"
    return text


# ─── Agent loop ───────────────────────────────────────────────────────────────

async def run_agent(query: str, attach_uri: str | None = None) -> str:
    """
    Agentic loop: connect to GitHub's MCP server, optionally attach a resource,
    let the LLM decide which tools to call, execute them, and answer.

    This follows a ReAct-style tool-use loop:
      1. Discover primitives (tools/list, resources/templates/list, prompts/list)
      2. (Host) read a resource and add it to the conversation as context
      3. Give tool schemas to the LLM
      4. LLM returns tool_calls -> we execute them via MCP
      5. Feed results back -> LLM either calls more tools or responds
      6. Return the final text answer
    """
    print("=" * 65)
    print("GITHUB MCP AGENT")
    print("An LLM that decides which GitHub tools to call")
    print("=" * 65)
    print()

    # ── 1. Connect to GitHub's hosted MCP server (Streamable HTTP) ────────
    print(f"[Agent] Connecting to {GITHUB_MCP_URL} ...")
    print(f"[Agent] Query: {query}")
    print()

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with streamablehttp_client(GITHUB_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()

            # ── 2. Discover all three primitives ──────────────────────────
            mcp_tools = await discover_primitives(session, init.capabilities)
            openai_tools = mcp_tools_to_openai_functions(mcp_tools)
            tools_by_name = {t.name for t in mcp_tools}

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
            ]

            # ── 3. HOST step: attach a resource as context ────────────────
            # The model never calls resources/read — the host (this script)
            # decides what to read and puts the content in the conversation.
            if attach_uri:
                print(f"[Host]  resources/read {attach_uri}")
                resource_text = await read_resource_text(session, attach_uri)
                print(f"[Host]  attached {len(resource_text):,} chars as context for the LLM")
                print()
                messages.append({
                    "role": "user",
                    "content": f"Context attached from MCP resource {attach_uri}:\n\n{resource_text}",
                })

            messages.append({"role": "user", "content": query})

            # ── 4. Start the agent loop ───────────────────────────────────
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)

            # Agent loop — up to 5 iterations of tool calling
            max_iterations = 5
            for iteration in range(1, max_iterations + 1):
                print(f"[Agent] Iteration {iteration}: calling {OPENAI_MODEL}...")

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
                    _print_answer(final_answer)
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
            _print_answer(final_answer)
            return final_answer


def _print_answer(answer: str) -> None:
    print()
    print("=" * 65)
    print("AGENT ANSWER")
    print("=" * 65)
    print()
    print(answer)
    print()


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_all_samples() -> None:
    """Run the agent against every sample query in SAMPLE_QUERIES."""
    for i, (query, attach_uri) in enumerate(SAMPLE_QUERIES, 1):
        print(f"\n{'#' * 65}")
        print(f"  SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)}")
        print(f"{'#' * 65}")
        await run_agent(query, attach_uri)


def _http_status(exc: BaseException) -> int | None:
    """Find an HTTP status code inside an (exception-group-wrapped) error."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    for inner in getattr(exc, "exceptions", ()):
        code = _http_status(inner)
        if code:
            return code
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub MCP agent (tools + host-attached resources).")
    parser.add_argument("query", nargs="*", help="Question for the agent. Omit to run the sample queries.")
    parser.add_argument("--attach", metavar="URI", help="Resource URI the host reads and attaches first, "
                        "e.g. repo://owner/repo/contents/README.md")
    args = parser.parse_args()

    try:
        if args.query:
            asyncio.run(run_agent(" ".join(args.query), args.attach))
        else:
            asyncio.run(run_all_samples())
    except Exception as error:
        if _http_status(error) == 401:
            print("ERROR: GitHub rejected GITHUB_TOKEN (401 Unauthorized). Check that it is a valid, unexpired token.")
            sys.exit(1)
        raise
