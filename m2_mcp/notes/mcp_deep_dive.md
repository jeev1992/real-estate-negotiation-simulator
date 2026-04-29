# MCP Deep Dive
## Model Context Protocol: How Agents Connect to the World

---

## Table of Contents

1. [The Problem MCP Solves](#1-the-problem-mcp-solves)
2. [What MCP Actually Is](#2-what-mcp-actually-is)
3. [MCP Architecture](#3-mcp-architecture)
4. [MCP vs Direct API Integration](#4-mcp-vs-direct-api-integration)
5. [GitHub MCP — A Familiar Example](#5-github-mcp--a-familiar-example)
6. [Connecting to GitHub's MCP Server](#6-connecting-to-githubs-mcp-server)
7. [Building Your Own MCP Server](#7-building-your-own-mcp-server)
8. [Our Real Estate MCP Servers](#8-our-real-estate-mcp-servers)
9. [Transport Protocols: stdio vs SSE/HTTP](#9-transport-protocols-stdio-vs-ssehttp)
10. [Auth, Discovery, and Execution](#10-auth-discovery-and-execution)
11. [Common Misconceptions](#11-common-misconceptions)
12. [When to Use MCP vs Direct API](#12-when-to-use-mcp-vs-direct-api)

**Part II — Protocol Internals**
13. [The `initialize` Handshake](#13-the-initialize-handshake)
14. [The Full Tool-Calling Loop](#14-the-full-tool-calling-loop)
15. [The Four Primitives](#15-the-four-primitives)
16. [Content Blocks](#16-content-blocks)
17. [Transports](#17-transports)
18. [The Security Model](#18-the-security-model)
19. [Client and Server Authoring Patterns](#19-client-and-server-authoring-patterns)

---

## 1. The Problem MCP Solves

### The N×M Integration Problem

Before MCP, every AI application that needed to connect to external tools faced the same nightmare:

```
WITHOUT MCP — The N×M Problem:

  AI App A ──────── custom code ──────── GitHub
  AI App A ──────── custom code ──────── Slack
  AI App A ──────── custom code ──────── Database
  AI App A ──────── custom code ──────── File System

  AI App B ──────── custom code ──────── GitHub
  AI App B ──────── custom code ──────── Slack
  AI App B ──────── custom code ──────── Database
  AI App B ──────── custom code ──────── File System

  If you have N apps and M tools → N×M integrations to build and maintain
  4 apps × 4 tools = 16 separate integration codebases!
```

This creates:
- **Duplicated effort** — every team reimplements GitHub auth, Slack message parsing, etc.
- **Inconsistent interfaces** — each integration is slightly different
- **Maintenance hell** — when GitHub changes their API, you update 4 codebases
- **No reusability** — work done for App A doesn't help App B

### The MCP Solution

```
WITH MCP — The N+M Solution:

  GitHub ──────── GitHub MCP Server ──────────────────────────────┐
  Slack  ──────── Slack MCP Server  ────────────────────────────┐  │
  DB     ──────── DB MCP Server     ──────────────────────────┐  │  │
  Files  ──────── Files MCP Server  ────────────────────────┐  │  │  │
                                                             │  │  │  │
                                    MCP Protocol (standard) │  │  │  │
                                                             │  │  │  │
  AI App A ──── MCP Client ────────────────────────────────┘  │  │  │
  AI App B ──── MCP Client ─────────────────────────────────┘  │  │  │
  AI App C ──── MCP Client ──────────────────────────────────┘  │  │
  AI App D ──── MCP Client ───────────────────────────────────┘  │
                                                                  │
  4 apps + 4 tools = 8 things to build, not 16!                   │
  Any app can use any server automatically ──────────────────────┘
```

MCP is essentially **the USB standard for AI tools** — any MCP-compatible app can plug into any MCP server without custom integration code.

---

## 2. What MCP Actually Is

MCP (Model Context Protocol) is an **open protocol** developed by Anthropic (released November 2024) that standardizes how AI applications connect to external systems.

### Key Characteristics

| Property | Detail |
|---|---|
| **Type** | Application-layer protocol (like HTTP for web) |
| **Developed by** | Anthropic |
| **Open source** | Yes — anyone can implement clients or servers |
| **Language** | Transport-agnostic; SDKs in Python, TypeScript, others |
| **Purpose** | Standardize tool/resource/prompt exposure to AI systems |

### What MCP Exposes

MCP servers can expose three types of things:

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP SERVER                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. TOOLS        → Functions the LLM can call                   │
│     Example: search_repositories(query: str) -> list           │
│     Example: get_market_price(address: str) -> dict            │
│                                                                 │
│  2. RESOURCES    → Data the LLM can read                        │
│     Example: file:///local/project/README.md                   │
│     Example: github://repo/owner/name/blob/main/src/app.py     │
│                                                                 │
│  3. PROMPTS      → Pre-built prompt templates                   │
│     Example: "Review this code for security issues"            │
│     Example: "Summarize these meeting notes"                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

For this workshop, we focus on **Tools** — the most commonly used MCP feature.

---

## 3. MCP Architecture

### The Three Layers

```
┌───────────────────────────────────────────────────────────────┐
│                        HOST APPLICATION                       │
│  (Claude Desktop, your custom app, VS Code with Copilot)      │
│                                                               │
│   ┌─────────────────┐     ┌─────────────────┐                │
│   │   MCP CLIENT A  │     │   MCP CLIENT B  │                │
│   │                 │     │                 │                │
│   │  "I need to     │     │  "I need to     │                │
│   │   search code"  │     │   check prices" │                │
│   └────────┬────────┘     └────────┬────────┘                │
│            │                       │                          │
└────────────│───────────────────────│──────────────────────────┘
             │ MCP Protocol          │ MCP Protocol
             │ (stdio or SSE)        │ (stdio or SSE)
             │                       │
    ─────────│───────────────────────│──────────── BOUNDARY ────
             │                       │
             ▼                       ▼
   ┌─────────────────┐     ┌─────────────────┐
   │  GITHUB MCP     │     │  REAL ESTATE    │
   │  SERVER         │     │  PRICING SERVER │
   │                 │     │                 │
   │  Wraps GitHub   │     │  Wraps MLS/     │
   │  REST API       │     │  Zillow APIs    │
   │                 │     │                 │
   │  Tools:         │     │  Tools:         │
   │  • search_repos │     │  • market_price │
   │  • get_file     │     │  • calc_discount│
   │  • create_issue │     │                 │
   └─────────────────┘     └─────────────────┘
```

### Components Explained

**MCP Host**: The application that runs the AI (your code, Claude Desktop, etc.)

**MCP Client**: A module within the host that speaks the MCP protocol. Each client maintains a 1:1 connection with one server.

**MCP Server**: A separate process that exposes tools/resources/prompts. It doesn't know about the AI — it just exposes a standardized interface.

**Transport**: The communication channel between client and server. Can be:
- `stdio` — client spawns server as subprocess, communicates via stdin/stdout
- `SSE` (Server-Sent Events) — server runs as HTTP service, client subscribes
- `WebSocket` — bidirectional persistent connection

---

## 4. MCP vs Direct API Integration

This comparison is crucial for understanding WHY you'd use MCP.

### Direct API Integration (Without MCP)

```python
# WITHOUT MCP — What agents had to do before
import requests
import base64

class GitHubIntegration:
    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        self.base_url = "https://api.github.com"

    def search_repos(self, query: str) -> list:
        # Each team implements this differently
        # Must handle pagination, rate limits, errors
        response = requests.get(
            f"{self.base_url}/search/repositories",
            headers=self.headers,
            params={"q": query, "per_page": 10}
        )
        response.raise_for_status()
        return response.json()["items"]

    def get_file(self, owner: str, repo: str, path: str) -> str:
        response = requests.get(
            f"{self.base_url}/repos/{owner}/{repo}/contents/{path}",
            headers=self.headers
        )
        data = response.json()
        return base64.b64decode(data["content"]).decode()

# Every AI app that needs GitHub must build this from scratch
# Different teams → different implementations → bugs everywhere
```

### With MCP

```python
# WITH MCP — Standardized, reusable, auto-discoverable
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def use_github_tools():
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # DISCOVER what tools are available — no docs needed!
            tools = await session.list_tools()
            print([t.name for t in tools.tools])
            # Output: ['search_repositories', 'get_file_contents',
            #          'create_issue', 'list_issues', 'search_code', ...]

            # CALL tools with standard interface
            result = await session.call_tool(
                "search_repositories",
                {"query": "real estate pricing python"}
            )
            # Returns standardized CallToolResult
```

### Key Differences Table

```
┌────────────────────────┬──────────────────────────┬──────────────────────────┐
│ Concern                │ Direct API               │ MCP                      │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Tool discovery         │ Read docs manually       │ Auto via list_tools()    │
│ Schema for LLM         │ You write it             │ Auto-generated           │
│ Auth handling          │ Custom per API           │ Server handles it        │
│ Error format           │ Different per API        │ Standard MCP errors      │
│ Switching providers    │ Rewrite integration      │ Swap server, same client │
│ New agent using tool   │ Copy/rewrite code        │ Point to same server     │
│ Rate limiting          │ You implement            │ Server handles it        │
│ Pagination             │ You implement            │ Server handles it        │
└────────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

## 5. GitHub MCP — A Familiar Example

GitHub has an **official MCP server** (`@modelcontextprotocol/server-github`) that exposes GitHub's API as MCP tools. This is a perfect teaching example because every developer already knows GitHub.

### What GitHub MCP Exposes

```
GitHub MCP Server Tools (partial list):
─────────────────────────────────────────
Repository Operations:
  • search_repositories(query, page?, perPage?)
  • get_repository(owner, repo)
  • create_repository(name, description?, private?)
  • fork_repository(owner, repo)

File Operations:
  • get_file_contents(owner, repo, path, branch?)
  • create_or_update_file(owner, repo, path, message, content, sha?)
  • search_code(query)

Issues & PRs:
  • list_issues(owner, repo, state?, labels?)
  • create_issue(owner, repo, title, body?, assignees?)
  • get_issue(owner, repo, issue_number)
  • list_pull_requests(owner, repo, state?)
  • create_pull_request(owner, repo, title, body, head, base)

Users:
  • get_me()     ← get current authenticated user
  • get_user(username)
```

### Why This Matters for Learning

When you see `search_repositories(query="python")` and get back a list of repos — that's MCP working. The AI agent called a tool. The tool called GitHub's REST API. The result came back in a standard format.

**The agent didn't know it was talking to GitHub's REST API**. It just called a tool. This is the entire point of MCP — abstraction.

---

## 6. Connecting to GitHub's MCP Server

### Prerequisites

```bash
# GitHub MCP server is a Node.js package
# You need Node.js + npx installed
node --version  # should be 18+
npx --version

# Get a GitHub Personal Access Token:
# GitHub → Settings → Developer Settings → Personal Access Tokens → Classic
# Scopes needed: repo, read:org (for workshop purposes)
```

### Method 1: Direct stdio Connection (Python)

See `m2_mcp/github_agent_client.py` for the full runnable demo.

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os

async def demo_github_mcp():
    """
    Connects to GitHub's official MCP server and demonstrates tool discovery
    and tool calling — the two fundamental MCP operations.
    """
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={
            **os.environ,  # inherit system environment
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]
        }
    )

    print("🔌 Connecting to GitHub MCP server via stdio...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # Step 1: Initialize the connection
            await session.initialize()
            print("✅ Connected to GitHub MCP server\n")

            # Step 2: DISCOVER available tools
            # This is the magic of MCP — you don't need to read docs!
            tools_response = await session.list_tools()
            tools = tools_response.tools

            print(f"🛠️  Available tools ({len(tools)} total):")
            for tool in tools[:5]:  # show first 5
                print(f"   • {tool.name}: {tool.description[:60]}...")
            print()

            # Step 3: CALL a tool — search for repos
            print("🔍 Calling: search_repositories('real estate python')...")
            result = await session.call_tool(
                "search_repositories",
                {"query": "real estate pricing python", "perPage": 3}
            )

            # Result comes back as content blocks
            import json
            data = json.loads(result.content[0].text)
            print(f"Found {data['total_count']} repositories. Top 3:")
            for repo in data['items'][:3]:
                print(f"   ⭐ {repo['full_name']} ({repo['stargazers_count']} stars)")
            print()

            # Step 4: CALL another tool — get authenticated user
            print("👤 Calling: get_me()...")
            me_result = await session.call_tool("get_me", {})
            me = json.loads(me_result.content[0].text)
            print(f"   Authenticated as: {me['login']} ({me['name']})")

asyncio.run(demo_github_mcp())
```

### What Just Happened (Under the Hood)

```
YOUR CODE                    MCP PROTOCOL                    GITHUB API
─────────────                ────────────────────            ──────────────────

session.initialize()  ──►  {"jsonrpc": "2.0",          The server spawned by
                            "id": 1,                    npx starts up, reads
                            "method": "initialize",     stdio for messages
                            "params": {...}}

                      ◄──  {"result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {...},
                            "serverInfo": {"name": "github-mcp-server"}
                            }}

session.list_tools()  ──►  {"method": "tools/list"}

                      ◄──  {"result": {"tools": [
                            {"name": "search_repositories",
                             "description": "...",
                             "inputSchema": {...}},
                            ...
                            ]}}

session.call_tool(    ──►  {"method": "tools/call",
  "search_repos",          "params": {
  {"query": "..."})          "name": "search_repositories",
                             "arguments": {"query": "..."}
                           }}
                                                         ──► GET /search/repositories
                                                         ◄── {items: [...]}

                      ◄──  {"result": {"content": [
                            {"type": "text",
                             "text": "{\"items\": [...]}"}
                            ]}}
```

Every MCP interaction follows this same JSON-RPC 2.0 pattern. Once you understand it for GitHub, you understand it for every MCP server.

---

## 7. Building Your Own MCP Server

Now that you've seen a real MCP server (GitHub's), let's build our own.

### Using FastMCP (Recommended)

FastMCP is the fastest way to build MCP servers in Python. It handles all the JSON-RPC scaffolding automatically.

```bash
pip install mcp
```

### Minimal MCP Server (Hello World)

```python
from mcp.server.fastmcp import FastMCP

# 1. Create the server
mcp = FastMCP("my-first-server", description="My first MCP server")

# 2. Define tools using decorators (just like Flask routes!)
@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # In production: call a weather API here
    return {
        "city": city,
        "temperature_f": 72,
        "condition": "sunny",
        "humidity_percent": 45
    }

# 3. Run the server
if __name__ == "__main__":
    mcp.run()  # stdio transport by default
```

**That's it.** FastMCP automatically:
- Generates the JSON schema for each tool from Python type hints
- Handles all MCP protocol messages (initialize, list_tools, call_tool)
- Validates inputs against the schema
- Handles errors and formats responses

### Tool Definition Details

```python
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from typing import Literal

mcp = FastMCP("real-estate-tools")

@mcp.tool()
def get_market_price(
    address: str = Field(description="Full property address"),
    property_type: Literal["single_family", "condo", "townhouse"] = Field(
        default="single_family",
        description="Type of property"
    )
) -> dict:
    """
    Get market pricing data for a property based on comparable sales.

    MCP auto-generates this schema for the LLM:
    {
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Full property address"},
            "property_type": {
                "type": "string",
                "enum": ["single_family", "condo", "townhouse"],
                "default": "single_family"
            }
        },
        "required": ["address"]
    }
    """
    # Tool implementation here
    return {"market_value": 462000, "list_price": 485000}
```

### Adding Resources

```python
@mcp.resource("property://{address}")
def get_property_report(address: str) -> str:
    """
    Resources are like MCP's version of GET endpoints.
    They return data the LLM can read, not functions it can call.
    """
    return f"Property Report for {address}\n\nListed: $485,000\nEstimated Value: $462,000"
```

### Error Handling in MCP Tools

```python
from mcp.server.fastmcp import FastMCP
from mcp.types import McpError, ErrorCode

mcp = FastMCP("demo")

@mcp.tool()
def safe_division(numerator: float, denominator: float) -> float:
    """Divide two numbers safely."""
    if denominator == 0:
        # Raise MCP-standard errors that clients understand
        raise McpError(
            ErrorCode.InvalidParams,
            "Denominator cannot be zero"
        )
    return numerator / denominator
```

---

## 8. Our Real Estate MCP Servers

Our workshop has two custom MCP servers that our negotiation agents use.

### Server 1: Pricing Server (`m2_mcp/pricing_server.py`)

**What it simulates**: A real estate pricing data provider (think: Zillow's API, but accessed via MCP instead of direct HTTP calls).

```
Tools exposed:
┌──────────────────────────────────────────────────────────────────┐
│ get_market_price(address, property_type)                         │
│   → Returns: list_price, estimated_value, comparable_sales,     │
│              price_per_sqft, overpriced_by_percent              │
│                                                                  │
│ calculate_discount(base_price, market_condition, days_on_market) │
│   → Returns: suggested_offer_low/high, aggressive_offer,        │
│              reasoning, negotiation_tips                         │
└──────────────────────────────────────────────────────────────────┘
```

**Why use MCP instead of direct import?**

```python
# WITHOUT MCP (direct import) — tightly coupled
from mcp_servers.pricing_server import get_market_price  # ← bad practice
price = get_market_price("742 Evergreen Terrace...")

# WITH MCP — loosely coupled, agent-friendly
result = await mcp_session.call_tool("get_market_price", {
    "address": "742 Evergreen Terrace...",
    "property_type": "single_family"
})
# The agent discovers tools automatically
# The pricing logic could move to a remote server — agent doesn't care
# The LLM gets type-safe schema for this tool automatically
```

### Server 2: Inventory Server (`m2_mcp/inventory_server.py`)

**What it simulates**: An MLS (Multiple Listing Service) inventory system.

```
Tools exposed:
┌──────────────────────────────────────────────────────────────────┐
│ get_inventory_level(zip_code)                                    │
│   → Returns: active_listings, days_on_market_avg,               │
│              absorption_rate, market_condition                   │
│                                                                  │
│ get_minimum_acceptable_price(property_id)                        │
│   → Returns: minimum_price, price_floor_reasoning               │
│   NOTE: In real estate, only the seller's agent knows the       │
│   seller's floor price. Our seller agent uses this tool,        │
│   buyer agent does NOT have access.                             │
└──────────────────────────────────────────────────────────────────┘
```

**Educational note on access control**: The seller agent connects to the inventory server to get `minimum_acceptable_price`. The buyer agent does NOT connect to this tool — just like in real life where the buyer doesn't know the seller's bottom line. MCP servers can implement auth/access control to enforce this.

### How Agents Use These Servers

```
BUYER AGENT (OpenAI GPT-4o / Gemini 2.0 Flash):
  ├── Connects to: pricing_server.py (via MCP)
  │     • Uses get_market_price() to justify offers
  │     • Uses calculate_discount() to determine offer range
  └── Does NOT connect to: inventory_server.py

SELLER AGENT (OpenAI GPT-4o / Gemini 2.0 Flash):
  ├── Connects to: pricing_server.py (via MCP)
  │     • Uses get_market_price() to understand market value
  │     • Uses calculate_discount() to understand buyer expectations
  └── Connects to: inventory_server.py (via MCP)
        • Uses get_inventory_level() to gauge market pressure
        • Uses get_minimum_acceptable_price() to know its floor
```

---

## 9. Transport Protocols: stdio vs SSE/HTTP

MCP supports multiple transport methods. Understanding these is important for production deployments.

### stdio Transport

```
┌─────────────────┐          subprocess pipe          ┌─────────────────┐
│  MCP CLIENT     │ ──── stdin  ────────────────────► │  MCP SERVER     │
│  (your agent)   │ ◄─── stdout ──────────────────── │  (pricing.py)   │
└─────────────────┘                                   └─────────────────┘

Process flow:
1. Client spawns server as subprocess (npx, python, etc.)
2. Communication happens via stdin/stdout pipes
3. Server process dies when client disconnects
4. One server instance per client connection
```

**Best for**: Local development, workshop demos, tools that don't need to be shared.

```python
# stdio client
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(
    command="python",
    args=["m2_mcp/pricing_server.py"]
)
async with stdio_client(params) as (read, write):
    ...
```

```python
# stdio server (default)
mcp.run()          # or explicitly: mcp.run(transport="stdio")
```

### SSE (Server-Sent Events) Transport

```
┌─────────────────┐          HTTP/SSE                ┌─────────────────┐
│  MCP CLIENT     │ ──── POST /messages ───────────► │  MCP SERVER     │
│  (your agent)   │ ◄─── GET /sse (event stream) ─── │  (HTTP server)  │
└─────────────────┘                                   └─────────────────┘

Process flow:
1. Server runs as standalone HTTP process (any machine)
2. Multiple clients can connect to same server
3. Server persists independently of clients
4. Better for production / shared infrastructure
```

**Best for**: Production deployments, multiple agents sharing one server, remote access.

```python
# SSE client
from mcp.client.sse import sse_client

async with sse_client("http://localhost:8001/sse") as (read, write):
    ...
```

```python
# SSE server
python pricing_server.py --sse --port 8001
# Or programmatically:
mcp.run(transport="sse", host="0.0.0.0", port=8001)
```

### Our Workshop Approach

Our MCP servers support **both transports** via a command-line flag:

```bash
# stdio (default) — for simple_agents version
python m2_mcp/pricing_server.py

# SSE — for ADK version or production
python m2_mcp/pricing_server.py --sse --port 8001
```

---

## 10. Auth, Discovery, and Execution

### Authentication

MCP itself doesn't define authentication — servers implement it however they need:

```python
# GitHub MCP: token passed via environment variable
env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."}

# Custom server: could check an API key in initialize params
@mcp.server.initialize_handler()
async def handle_initialize(params):
    api_key = params.get("api_key")
    if api_key != os.environ["EXPECTED_API_KEY"]:
        raise McpError(ErrorCode.Unauthorized, "Invalid API key")
```

### Discovery (list_tools)

When a client connects and calls `list_tools()`, it gets back complete schemas:

```json
{
  "tools": [
    {
      "name": "get_market_price",
      "description": "Get market pricing data for a property including comparable sales.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "address": {
            "type": "string",
            "description": "Full property address"
          },
          "property_type": {
            "type": "string",
            "default": "single_family",
            "enum": ["single_family", "condo", "townhouse", "multi_family"]
          }
        },
        "required": ["address"]
      }
    }
  ]
}
```

The LLM framework takes this schema and automatically makes the tool available to the LLM — no manual tool definition needed.

### Execution Flow

```
1. LLM decides to call a tool
   LLM output: {"tool": "get_market_price", "args": {"address": "742 Evergreen..."}}

2. Client sends call_tool request to MCP server
   JSON-RPC: {"method": "tools/call", "params": {"name": "get_market_price", "arguments": {...}}}

3. Server validates inputs against schema
   FastMCP: Pydantic validation of address (str) and property_type (Literal)

4. Server executes tool function
   Python: calls get_market_price("742 Evergreen...", "single_family")

5. Server returns result
   JSON-RPC: {"result": {"content": [{"type": "text", "text": "{...json...}"}]}}

6. Client parses result and feeds back to LLM
   LLM sees: Tool result: {"list_price": 485000, "estimated_market_value": 462000, ...}

7. LLM reasons about result and decides next action
```

---

## 11. Common Misconceptions

### ❌ "MCP is like an API"

**Reality**: MCP is a protocol for exposing APIs in a standardized way. Think of it as the wrapper around your API that makes it universally accessible to AI agents. The underlying data source (GitHub REST API, Zillow, your database) is still there — MCP just standardizes how agents access it.

### ❌ "MCP only works with Claude"

**Reality**: MCP is an open protocol. It works with any AI system that implements an MCP client. OpenAI, Google, Anthropic, and open-source frameworks (LangGraph, LlamaIndex, etc.) all support MCP.

### ❌ "You need MCP for every tool"

**Reality**: For simple, single-purpose tools that won't be reused, a direct Python function or API call is often better. MCP shines when:
- Multiple agents need the same tool
- Tools need to be shared across teams/projects
- The underlying data source might change

### ❌ "MCP handles the AI reasoning"

**Reality**: MCP handles **connectivity** — getting data to and from external systems. The AI reasoning about WHAT to call and WHAT to do with results is done by the LLM, not by MCP.

### ❌ "MCP servers need to be written in Python"

**Reality**: MCP servers can be in any language. GitHub's official server is TypeScript/Node.js. There are servers in Go, Rust, Java, etc. Our workshop uses Python because it's most familiar.

---

## 12. When to Use MCP vs Direct API

```
Use MCP when:                         Use direct API when:
─────────────────────────────────     ──────────────────────────────────
✅ Multiple agents need same tool     ✅ Single agent, single tool
✅ Tool may be reused across projects ✅ Simple one-off integration
✅ Team wants shared tooling          ✅ Performance is critical
✅ Underlying system might change     ✅ Complex auth that MCP complicates
✅ Want auto-discovery by new agents  ✅ Workshop/prototype/throwaway code
✅ Want standardized error handling   ✅ Already have working integration
✅ Remote tool access needed
```

---

# Part II — Protocol Internals (Phase 2 Deep-Dive)

The first half of this document explains *why* MCP exists and *how to use it*.
This section covers *what is actually on the wire* — the message frames, the
four primitives, content blocks, transports, and the security model. Pair it
with the runnable demos under [`m2_mcp/demos/`](../demos/).

> Each subsection has a matching demo script. Read the section, then run the
> demo and watch the wire output line up with the explanation.

---

## 13. The `initialize` Handshake

Every MCP session starts with a two-step JSON-RPC handshake. Nothing else
is allowed before it completes.

```text
client                                                   server
  │   initialize { protocolVersion, capabilities, clientInfo }     →
  ←   initialize result { protocolVersion, capabilities, serverInfo }
  │   notifications/initialized                                    →
  │
  │   (now free to call tools/list, resources/list, prompts/list,
  │    tools/call, ...)
```

**Why two steps?** The `initialize` *request* negotiates the protocol
version and capabilities. The `notifications/initialized` notification tells
the server "I am ready to receive normal requests now." Only after that may
the client issue `tools/call` etc.

**`protocolVersion`** is a date string (e.g. `"2024-11-05"`). The server
returns the version it agreed to — usually the client's request, but the
server can downgrade if it doesn't support the requested one. Clients that
don't understand the returned version must close the connection.

**`capabilities`** is the negotiation surface. Both sides advertise which
optional features they support:

| Capability key       | Owner    | Meaning                                            |
|----------------------|----------|----------------------------------------------------|
| `tools`              | server   | server exposes tools (list/call)                   |
| `resources`          | server   | server exposes resources (list/read/subscribe)     |
| `prompts`            | server   | server exposes prompts (list/get)                  |
| `logging`            | server   | server can emit `notifications/message` log events |
| `sampling`           | client   | client can satisfy `sampling/createMessage` calls  |
| `roots`              | client   | client exposes filesystem roots to the server      |
| `experimental`       | both     | open-ended experimental flags                      |

**Demo:** `m2_mcp/demos/01_initialize_handshake.py` prints every JSON-RPC
frame of the handshake against `pricing_server.py`.

---

## 14. The Full Tool-Calling Loop

In production, the model never talks to MCP directly. The flow is always:

```text
   USER prompt
     │
     ▼
   HOST (your app — negotiation_agents/buyer_agent/agent.py, etc.)
     │  1. tools/list  ────────────────────────────────► SERVER
     │  ◄────────────── catalog of tools (with JSON-Schema)
     │
     │  2. translate to OpenAI / Anthropic tool spec
     │
     ▼
   MODEL  (GPT-4o, Claude, ...)
     │  3. emits tool_use(name, args)
     │
     ▼
   HOST
     │  4. tools/call(name, args)  ───────────────────► SERVER
     │  ◄────────────── CallToolResult { content[] }
     │
     │  5. inject tool_result back into model context
     ▼
   MODEL
     │  6. either calls another tool (loop back to 3)
     │     or emits the final assistant text
```

Three things that often confuse newcomers:

1. **The model doesn't know MCP exists.** It only sees a list of "functions".
   The host translates between MCP's `Tool` shape and the model provider's
   tool-call shape.
2. **The host enforces budgets.** Number of hops, total tokens, time —
   none of those are protocol concerns. Your host code decides when to stop.
3. **A single user turn can trigger many tool calls.** Each call is an
   independent JSON-RPC request/response, but they all happen within one
   user turn from the model's perspective.

**Demo:** `m2_mcp/demos/02_tool_loop_trace.py` narrates the entire loop
end-to-end with timestamps, against the pricing server + GPT-4o.

---

## 15. The Four Primitives

MCP servers can expose more than tools. There are four primitive kinds.

### 15.1 Tools — *model-invoked* actions

```python
@mcp.tool()
def get_market_price(address: str) -> dict:
    """Estimate the market price of a property."""
    ...
```

- The model decides when to call them.
- Inputs are JSON-Schema-described.
- Output is one or more `Content` blocks.
- Listed via `tools/list`, invoked via `tools/call`.

### 15.2 Resources — *host-attached* documents

```python
@mcp.resource("inventory://floor-prices")
def floor_prices_resource() -> str:
    return json.dumps(SELLER_FLOORS, indent=2)
```

- The **host** (not the model) decides when to attach a resource as context.
- Resources have a URI (any scheme: `file://`, `inventory://`, `https://`...)
  and a MIME type.
- Useful for "here is reference material the agent should always have."
- Listed via `resources/list`, fetched via `resources/read`.

In Phase 2, `m2_mcp/inventory_server.py` exposes `inventory://floor-prices`
so the seller agent can be given the floor-price catalog without having to
call a tool first.

### 15.3 Prompts — *user-selected* templates

```python
@mcp.prompt("negotiation-tactics")
def negotiation_tactics_prompt(role: str = "buyer", market_condition: str = "balanced") -> str:
    return f"You are negotiating as the {role}. Market is {market_condition}. ..."
```

- A **named, parameterized template** the host can render into the chat.
- Think "slash commands" or "starter prompts" surfaced to the user.
- Listed via `prompts/list`, rendered via `prompts/get`.

In Phase 2, `m2_mcp/pricing_server.py` exposes a `negotiation-tactics` prompt
that the host can render into either the buyer or seller agent's
conversation depending on the role parameter.

### 15.4 Sampling — *server-initiated* LLM calls

This one inverts the relationship. A *server* asks the host to run an LLM
call on its behalf:

```text
server  ──── sampling/createMessage ────►  host
host    ──── (calls its model) ────►       OpenAI/Anthropic
host    ◄──── completion ──────────        OpenAI/Anthropic
host    ──── sampling result ─────►        server
```

This lets a server compose its own LLM-powered behavior without holding
API keys. The host stays in control of model choice, redaction, and cost.

The workshop agents (`negotiation_agents/buyer_agent/`, `seller_agent/`) do **not** advertise
the `sampling` capability, so we don't demo this on the wire — but the
pattern is critical for advanced server design.

**Demo:** `m2_mcp/demos/03_list_all_primitives.py` prints all four kinds
from both workshop servers.

---

## 16. Content Blocks

Every tool result and most messages carry a list of typed content blocks:

```json
{
  "content": [
    { "type": "text",     "text": "..." },
    { "type": "image",    "data": "<base64>", "mimeType": "image/png" },
    { "type": "audio",    "data": "<base64>", "mimeType": "audio/wav" },
    { "type": "resource", "resource": { "uri": "...", "mimeType": "text/plain", "text": "..." } }
  ]
}
```

- **text** — most common; UTF-8 string.
- **image** — base64 + MIME type.
- **audio** — base64 + MIME type (added in 2025-03 spec).
- **resource (embedded)** — inline document, useful when the server wants
  to ship a file alongside textual output.

The model's host is responsible for converting these into something the
model provider understands (e.g. OpenAI's `image_url` or Anthropic's
`content` block). For text-only models, image/audio blocks are usually
dropped or summarized.

**Demo:** `m2_mcp/demos/04_content_types.py` spawns a tiny server that
returns each kind of block so you can see the JSON shape.

---

## 17. Transports

The protocol is the same; the carrier changes.

| Transport            | Use when                                       | How it looks                |
|----------------------|------------------------------------------------|-----------------------------|
| **stdio**            | local subprocess, single client                | newline-delimited JSON-RPC over pipes |
| **Streamable HTTP**  | remote/shared server, multiple clients         | HTTP POST + chunked SSE responses     |
| **SSE (legacy)**     | older deployments — superseded by Streamable   | two endpoints (`/sse` + `/messages`)  |

**stdio** is the workshop default. The host spawns the server as a
subprocess and talks to it through pipes. Zero network surface, zero auth
concerns, but only one client can connect.

**Streamable HTTP** is the spec's recommended HTTP transport. A single
endpoint accepts POST requests and uses Server-Sent Events for streaming
responses on the same connection. This is what production deployments use
when the server lives in a different process or host than the agent.

**Demo:** `m2_mcp/demos/05_streamable_http_transport.py` runs the same
`echo` tool over Streamable HTTP. Compare it to the stdio demos — exact
same protocol, just a different envelope.

---

## 18. The Security Model

MCP itself defines very little about security. The spec spells out **who
is responsible for what**, then defers to existing standards:

- **Transport-level auth.**
  - stdio: assumed local-trust; any auth is whatever you put in env vars.
  - Streamable HTTP: standard HTTP auth — bearer tokens, OAuth 2.1 PKCE,
    mTLS — set by the deploying team. The 2025-06-18 revision of the spec
    formalized OAuth 2.1 with Resource Indicators.
- **Authorization to call tools.** The server decides. A common pattern
  is a per-client allowlist; another is signed JWT scopes mapped to tool
  names. Our `_BUYER_ALLOWED_TOOLS` / `_SELLER_ALLOWED_TOOLS` allowlists
  in `negotiation_agents/buyer_agent/agent.py` / `seller_agent/agent.py` show the same pattern enforced
  *host-side* via ADK callbacks.
- **Data privacy.** The server is the gatekeeper for what it returns.
  `get_minimum_acceptable_price` in `inventory_server.py` is the
  workshop's example: only the seller's host connects to that server, so
  the buyer's host literally cannot see those numbers.
- **Sandboxing.** stdio servers run with the same OS privileges as the
  host — be intentional about which servers you spawn. Streamable HTTP
  servers can be deployed in containers or behind reverse proxies the
  same way any other web service is.

The takeaway: **MCP gives you a shared shape for tools and discovery. You
still own auth, authorization, and isolation.**

---

## 19. Client and Server Authoring Patterns

Two patterns repeat across the workshop:

**Pattern A — host-owned MCP client.** Your application code (the host)
opens a `ClientSession`, calls `initialize()`, then either lists tools
manually (the M2 baseline) or hands the session to a higher-level
framework (M3's `MCPToolset`). The host is responsible for closing the
session on exit.

```python
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("get_market_price", {...})
```

**Pattern B — FastMCP server.** Decorate functions with `@mcp.tool()`,
`@mcp.resource(...)`, or `@mcp.prompt(...)`. FastMCP introspects the
function signature to build the JSON-Schema, registers the handler, and
takes care of the protocol envelope. You write *only* the business logic.

```python
mcp = FastMCP("my-server")

@mcp.tool()
def my_tool(x: int) -> dict: ...

@mcp.resource("my-scheme://catalog")
def my_resource() -> str: ...

if __name__ == "__main__":
    mcp.run()                       # stdio (default)
    # or: mcp.run(transport="streamable-http")
```

When in doubt: hosts open + close sessions; servers expose primitives.

---

## 20. MCP Server Design Principles

Patterns from production MCP deployments (source: [Anthropic — Building agents that reach production systems with MCP](https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp)):

### Principle 1: Group tools around intent, not endpoints

Fewer, well-described tools consistently outperform exhaustive API mirrors.
Don't wrap your API 1:1 — group operations around what the agent is trying
to accomplish.

```
❌  BAD:  list_comps() + get_sqft_price() + calculate_value() + get_market_condition()
✅  GOOD: get_market_price(address) → returns comps, value, $/sqft, condition in one call
```

Our `pricing_server.py` already follows this: `get_market_price` returns a
rich object with comps, estimated value, price analysis, and market context.
One tool call gives the LLM everything it needs.

### Principle 2: Design for context efficiency

20+ tool schemas consume significant LLM context. At scale:
- **Defer loading**: only surface tools the agent actually needs for the current task
- **Process in code**: filter and aggregate tool results in code before returning to the LLM, rather than dumping raw data into context

Our servers expose 2–3 tools each — small enough that context isn't an issue.
But if you built a full MLS integration with 50+ operations, you'd want to
split into multiple focused servers or use tool search.

### Principle 3: Start stdio, ship HTTP

stdio is the right transport for local development (simple, no network).
HTTP (Streamable HTTP) is the right transport for production (remote, multi-client, behind auth).
The protocol is identical — only the wire changes.

```bash
# Development
python pricing_server.py                          # stdio (default)

# Production
python pricing_server.py --sse --port 8001        # HTTP (same tools, same code)
```

### Principle 4: Code orchestration for large surfaces

If your service has hundreds of operations (AWS, Kubernetes, Cloudflare),
intent-grouping won't cover it. Instead, expose a thin tool surface that
accepts code: the agent writes a script, your server runs it in a sandbox.
Cloudflare's MCP server covers ~2,500 endpoints with just 2 tools (`search`
and `execute`) in ~1K tokens.

This pattern is beyond our workshop scope but worth mentioning to advanced
students.



| Concept | Key Takeaway |
|---|---|
| **MCP purpose** | Solves N×M integration problem for AI tools |
| **Architecture** | Host → Client → [Transport] → Server → External System |
| **GitHub MCP** | Official MCP server wrapping GitHub's REST API |
| **stdio** | Server as subprocess, local, simple, 1:1 connection |
| **SSE/HTTP** | Server as HTTP service, remote, shared, scalable |
| **FastMCP** | Python library that makes building servers trivial |
| **Discovery** | Clients call list_tools() to auto-discover capabilities |
| **Auth** | Handled by individual servers, not MCP protocol |
| **When to use** | Multiple agents need same tool; shared infrastructure |

---

*← [Agent Fundamentals](../../m1_baseline/notes/agents_fundamentals.md)*
*→ [A2A Protocols](../../m3_adk_multiagents/notes/a2a_protocols.md)*
