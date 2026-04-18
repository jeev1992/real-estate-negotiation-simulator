"""
Demo 03 — List all four MCP primitives
=======================================
Connects to both workshop MCP servers and asks each one for everything it
exposes: Tools, Resources, and Prompts. Shows that an MCP server can carry
more than just tools — and demonstrates the new Resource (inventory) and
Prompt (pricing) primitives added in Phase 2.

Sampling is the fourth primitive (server-initiated LLM calls); it is
listed in the notes but not demonstrated here because it requires a
sampling-capable host, which our workshop hosts are not.

Run:
    python m2_mcp/demos/03_list_all_primitives.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[2]


async def inspect(label: str, server_path: Path) -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])
    print(f"\n=== {label} ({server_path.name}) ===")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            caps = init.capabilities
            print(f"server caps: tools={caps.tools is not None} "
                  f"resources={caps.resources is not None} "
                  f"prompts={caps.prompts is not None}")

            try:
                tools = (await session.list_tools()).tools
                print(f"\n[tools] {len(tools)}")
                for t in tools:
                    print(f"  - {t.name}: {(t.description or '').splitlines()[0]}")
            except Exception as e:
                print(f"[tools] not supported ({e})")

            try:
                resources = (await session.list_resources()).resources
                print(f"\n[resources] {len(resources)}")
                for r in resources:
                    print(f"  - {r.uri} :: {r.name}")
            except Exception as e:
                print(f"[resources] not supported ({e})")

            try:
                prompts = (await session.list_prompts()).prompts
                print(f"\n[prompts] {len(prompts)}")
                for p in prompts:
                    print(f"  - {p.name}: {(p.description or '').splitlines()[0]}")
            except Exception as e:
                print(f"[prompts] not supported ({e})")


async def main() -> None:
    await inspect("PRICING SERVER", REPO_ROOT / "m2_mcp" / "pricing_server.py")
    await inspect("INVENTORY SERVER", REPO_ROOT / "m2_mcp" / "inventory_server.py")


if __name__ == "__main__":
    asyncio.run(main())
