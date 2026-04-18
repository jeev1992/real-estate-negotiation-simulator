"""
Demo 05 — MCP over Streamable HTTP transport
=============================================
Same MCP protocol, different transport. Spins up a tiny FastMCP server in
Streamable HTTP mode (the spec's recommended replacement for raw SSE) and
connects to it from a client.

Run:
    # Terminal 1:
    python m2_mcp/demos/05_streamable_http_transport.py --serve --port 8765

    # Terminal 2 (or run with --client to do both in this process):
    python m2_mcp/demos/05_streamable_http_transport.py --client --port 8765
"""

import argparse
import asyncio
import sys
from pathlib import Path


def run_server(port: int) -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("http-transport-demo")

    @mcp.tool()
    def echo(text: str) -> str:
        """Echo back the supplied text."""
        return f"echo: {text}"

    # FastMCP's HTTP transport is the spec's "Streamable HTTP" — the
    # successor to raw SSE for HTTP-based MCP servers.
    print(f"Serving MCP on http://127.0.0.1:{port}/mcp", flush=True)
    mcp.settings.host = "127.0.0.1"
    mcp.settings.port = port
    mcp.run(transport="streamable-http")


async def run_client(port: int) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = f"http://127.0.0.1:{port}/mcp"
    print(f"Connecting client to {url}")
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"discovered tools: {[t.name for t in tools.tools]}")
            result = await session.call_tool("echo", {"text": "hello over HTTP"})
            print(f"response: {result.content[0].text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--client", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.serve and args.client:
        print("pick one of --serve or --client (run them in separate terminals)")
        sys.exit(2)
    if args.serve:
        run_server(args.port)
    elif args.client:
        asyncio.run(run_client(args.port))
    else:
        print("specify --serve or --client")
        sys.exit(2)


if __name__ == "__main__":
    main()
