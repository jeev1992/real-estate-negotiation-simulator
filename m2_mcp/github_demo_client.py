"""
GitHub MCP Demo Client
======================
This script demonstrates connecting to GitHub's official MCP server
and calling its tools — the same pattern used by our real estate agents.

WHY THIS DEMO EXISTS:
  GitHub is a tool every engineer knows. By seeing MCP work with GitHub
  first, you understand the protocol before we introduce our custom servers.
  The pattern is IDENTICAL for our pricing_server.py and inventory_server.py.

PREREQUISITES:
  1. Node.js 18+ installed (for npx)
  2. GitHub Personal Access Token
     - Go to: GitHub → Settings → Developer Settings → Personal Access Tokens → Classic
     - Scopes needed: repo, read:org (or just public_repo for public repos)
  3. Set environment variable: GITHUB_TOKEN=ghp_your_token_here

HOW TO RUN:
  export GITHUB_TOKEN=ghp_your_token_here
  python m2_mcp/github_demo_client.py

WHAT THIS DEMONSTRATES:
  1. Connecting to an MCP server via stdio transport
  2. Listing available tools (auto-discovery)
  3. Calling tools with structured arguments
  4. Parsing structured results
  5. How the LLM "sees" MCP tools (as function schemas)
"""

import asyncio
import json
import os
import sys
from typing import Any

# MCP Python SDK
# Install: pip install mcp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ─── Configuration ────────────────────────────────────────────────────────────

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# Catch: unset, empty string, or still set to the placeholder value
_PLACEHOLDER_PREFIXES = ("your_token", "ghp_your", "<your", "TOKEN_HERE")
if not GITHUB_TOKEN or any(GITHUB_TOKEN.lower().startswith(p) for p in _PLACEHOLDER_PREFIXES):
    print("ERROR: GITHUB_TOKEN environment variable is not set (or is still a placeholder).")
    print("   Get a token at: GitHub -> Settings -> Developer Settings -> Personal Access Tokens")
    print("   Then run: export GITHUB_TOKEN=ghp_your_token")
    sys.exit(1)


# ─── Demo Sections ────────────────────────────────────────────────────────────

async def demo_section_1_connection(session: ClientSession) -> None:
    """
    DEMO SECTION 1: Connecting and Initializing
    =============================================
    Shows how a client establishes a connection with an MCP server.
    Under the hood, this sends:
        {"jsonrpc": "2.0", "method": "initialize", "params": {...}}
    """
    print("=" * 60)
    print("SECTION 1: Connection & Initialization")
    print("=" * 60)
    print()
    print("Connected to GitHub MCP server via stdio transport")
    print()
    print("What just happened under the hood:")
    print("   1. Our Python process spawned a child process:")
    print("      npx -y @modelcontextprotocol/server-github")
    print("   2. We communicate via stdin/stdout pipes")
    print("   3. Sent initialize request over the pipe")
    print("   4. Server responded with its capabilities")
    print()


async def demo_section_2_tool_discovery(session: ClientSession) -> list:
    """
    DEMO SECTION 2: Tool Discovery (list_tools)
    =============================================
    This is the key MCP feature — auto-discovery of available tools.
    When an LLM agent calls list_tools(), it gets back complete JSON schemas
    for every available function. The LLM then knows EXACTLY how to call each tool.

    Compare to:
    - REST APIs: You must read documentation manually
    - OpenAPI: You write a spec, then generate code
    - MCP: Tools self-describe their schemas automatically
    """
    print("=" * 60)
    print("SECTION 2: Tool Discovery (list_tools)")
    print("=" * 60)
    print()

    tools_response = await session.list_tools()
    tools = tools_response.tools

    print(f"GitHub MCP server exposes {len(tools)} tools:")
    print()

    for i, tool in enumerate(tools, 1):
        print(f"  {i:2}. {tool.name}")
        print(f"       {tool.description[:70]}...")
        print()

    print("This is what an LLM agent sees when it connects to any MCP server.")
    print("   The agent doesn't need to be told how to use GitHub's API --")
    print("   it learns from the schemas provided by the MCP server.")
    print()

    # Show the full schema for one tool
    print("Full schema for 'search_repositories' (what the LLM receives):")
    print()
    for tool in tools:
        if tool.name == "search_repositories":
            print(json.dumps({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema.model_dump() if hasattr(tool.inputSchema, 'model_dump') else tool.inputSchema
            }, indent=2))
            break
    print()

    return tools


async def demo_section_3_tool_calls(session: ClientSession) -> None:
    """
    DEMO SECTION 3: Calling Tools
    ==============================
    Shows how to call an MCP tool with structured arguments.
    This is IDENTICAL to how our buyer agent calls get_market_price().
    """
    print("=" * 60)
    print("SECTION 3: Calling Tools (tools/call)")
    print("=" * 60)
    print()

    # ── Tool Call 1: Get current user ────────────────────────────────────────
    print("Tool Call 1: get_me()")
    print("   Purpose: Get the authenticated user's info")
    print("   Arguments: none")
    print()

    try:
        me_result = await session.call_tool("get_me", {})
        me_data = _parse_tool_result(me_result)

        print(f"   Result:")
        print(f"      Username: {me_data.get('login', 'N/A')}")
        print(f"      Name:     {me_data.get('name', 'N/A')}")
        print(f"      Public repos: {me_data.get('public_repos', 'N/A')}")
        print()
    except Exception as e:
        print(f"   get_me failed: {e}")
        print()

    # ── Tool Call 2: Search repositories ─────────────────────────────────────
    print("Tool Call 2: search_repositories(query='real estate python mcp')")
    print("   Purpose: Search GitHub for relevant repositories")
    print("   This simulates how an agent might research the domain")
    print()

    try:
        search_result = await session.call_tool(
            "search_repositories",
            {
                "query": "real estate pricing python",
                "perPage": 5
            }
        )
        search_data = _parse_tool_result(search_result)

        repos = search_data.get("items", [])
        total = search_data.get("total_count", 0)

        print(f"   Found {total} repositories. Top {len(repos)}:")
        print()
        for repo in repos:
            print(f"      stars={repo.get('stargazers_count', 0):5} | {repo.get('full_name', 'N/A')}")
            print(f"             {(repo.get('description') or 'No description')[:60]}")
            print()

    except Exception as e:
        print(f"   search_repositories failed: {e}")
        print()

    # ── Tool Call 3: Get file contents ────────────────────────────────────────
    print("Tool Call 3: search_code(query='def negotiate')")
    print("   Purpose: Search code across GitHub")
    print()

    try:
        code_result = await session.call_tool(
            "search_code",
            {
                "query": "def negotiate real estate python",
                "perPage": 3
            }
        )
        code_data = _parse_tool_result(code_result)
        items = code_data.get("items", [])

        print(f"   Found {code_data.get('total_count', 0)} code matches. Top {len(items)}:")
        for item in items[:3]:
            print(f"      {item.get('repository', {}).get('full_name', 'N/A')} -> {item.get('name', 'N/A')}")
        print()

    except Exception as e:
        print(f"   search_code failed: {e}")
        print()


async def demo_section_4_comparison(session: ClientSession) -> None:
    """
    DEMO SECTION 4: MCP vs Direct API Comparison
    =============================================
    Shows the difference between calling GitHub via MCP vs direct REST API.
    """
    print("=" * 60)
    print("SECTION 4: MCP vs Direct GitHub API -- Side by Side")
    print("=" * 60)
    print()

    print("WITHOUT MCP (direct API call):")
    print("-" * 40)
    print("""
  import requests

  headers = {
      "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
      "Accept": "application/vnd.github+json"
  }
  response = requests.get(
      "https://api.github.com/search/repositories",
      headers=headers,
      params={"q": "real estate python", "per_page": 5}
  )
  repos = response.json()["items"]
  # You wrote auth, URL construction, params, response parsing manually.
  # Every agent that needs GitHub must duplicate this code.
""")

    print("WITH MCP (our demo above):")
    print("-" * 40)
    print("""
  result = await session.call_tool(
      "search_repositories",
      {"query": "real estate python", "perPage": 5}
  )
  repos = parse_result(result)
  # Auth is handled by the MCP server (via GITHUB_TOKEN env var)
  # Schema is auto-discovered (no docs needed)
  # Every agent reuses the same server
  # Switching from GitHub to GitLab? Swap server, same client code.
""")

    print("KEY INSIGHT:")
    print("   Our real estate pricing server works EXACTLY the same way.")
    print("   Instead of GitHub's API, it wraps pricing/inventory data.")
    print("   Our buyer and seller agents call it with the SAME pattern.")
    print()


async def demo_section_5_connection_to_our_project(session: ClientSession) -> None:
    """
    DEMO SECTION 5: Connecting This to Our Workshop
    ================================================
    Shows how everything learned here applies to our negotiation simulator.
    """
    print("=" * 60)
    print("SECTION 5: How This Connects to Our Workshop")
    print("=" * 60)
    print()

    print("GitHub MCP Server            ->  Our Real Estate MCP Servers")
    print("-" * 60)
    print()
    print("  npx @modelcontextprotocol/   ->  python m2_mcp/pricing_server.py")
    print("       server-github")
    print()
    print("  search_repositories()        ->  get_market_price()")
    print("  get_file_contents()          ->  calculate_discount()")
    print("  create_issue()               ->  get_inventory_level()")
    print("  list_pull_requests()         ->  get_minimum_acceptable_price()")
    print()
    print("  GITHUB_TOKEN env var         ->  (no auth needed for our server)")
    print()
    print("  stdio transport              ->  stdio transport (simple version)")
    print("                               ->  SSE transport (python --sse flag)")
    print()
    print("The buyer and seller agents connect to our MCP servers")
    print("using the EXACT same MCPClientSession pattern you just saw.")
    print()
    print("Next steps:")
    print("  1. Run the pricing server:  python m2_mcp/pricing_server.py")
    print("  2. See our buyer agent:     cat m3_langgraph_multiagents/buyer_simple.py")
    print("  3. Run the full demo:       python m3_langgraph_multiagents/main_langgraph_multiagent.py")
    print()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_tool_result(result: Any) -> dict:
    """Parse MCP tool result content blocks into Python dict."""
    if result.content and len(result.content) > 0:
        text = result.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    return {}


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    """
    Main function — runs all demo sections sequentially.

    This function demonstrates the complete MCP client lifecycle:
    1. Create server parameters (how to spawn/connect to the server)
    2. Open the transport connection (stdio pipe)
    3. Create a client session
    4. Initialize the session (MCP handshake)
    5. Use the session to call tools
    6. Clean up when done (context managers handle this)
    """
    print()
    print("=" * 65)
    print("GITHUB MCP SERVER -- LIVE DEMO")
    print("Understanding MCP through a tool you already know")
    print("=" * 65)
    print()

    # Define how to connect to GitHub's MCP server
    # The MCP server is spawned as a subprocess via `npx`
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,  # inherit all system environment variables
            "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
        }
    )

    print(f"Connecting to GitHub MCP server...")
    print(f"   Command: npx -y @modelcontextprotocol/server-github")
    print(f"   Transport: stdio (subprocess pipes)")
    print(f"   Token: {GITHUB_TOKEN[:8]}..." if len(GITHUB_TOKEN) > 8 else "   Token: (set)")
    print()

    # The stdio_client context manager:
    # - Spawns the npx subprocess
    # - Sets up stdin/stdout pipes
    # - Returns (read_stream, write_stream) for the session
    # - Cleans up the subprocess on exit
    async with stdio_client(server_params) as (read, write):

        # ClientSession context manager:
        # - Wraps the streams in MCP protocol
        # - Handles JSON-RPC message framing
        # - Provides high-level methods: list_tools, call_tool, etc.
        async with ClientSession(read, write) as session:

            # CRITICAL: Must initialize before any other calls
            # This performs the MCP handshake (exchange capabilities)
            await session.initialize()

            # Run all demo sections
            await demo_section_1_connection(session)
            tools = await demo_section_2_tool_discovery(session)
            await demo_section_3_tool_calls(session)
            await demo_section_4_comparison(session)
            await demo_section_5_connection_to_our_project(session)

    print("=" * 60)
    print("Demo complete. GitHub MCP connection closed (subprocess terminated).")
    print()
    print("You now understand:")
    print("  - How MCP stdio transport works (subprocess + pipes)")
    print("  - How tool discovery works (list_tools)")
    print("  - How tool calls work (call_tool with JSON args)")
    print("  - How results are returned (content blocks)")
    print()
    print("This EXACT pattern powers our real estate negotiation agents.")
    print("See m2_mcp/pricing_server.py for our custom MCP server.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
