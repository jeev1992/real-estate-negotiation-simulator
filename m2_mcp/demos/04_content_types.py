"""
Demo 04 — MCP content block types
==================================
A tiny self-contained MCP server that returns each kind of `Content` block
(text, image, embedded resource), and a client that prints the structured
response so you can see the JSON shape of each variant.

Note: image bytes are a 1x1 PNG (base64) so the wire payload stays tiny.
Audio is documented in the notes but omitted here to keep the demo small.

Run:
    python m2_mcp/demos/04_content_types.py
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# A 1x1 transparent PNG.
TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


SERVER_SOURCE = '''
import sys
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ImageContent, EmbeddedResource, TextResourceContents

mcp = FastMCP("content-types-demo")

PNG_B64 = "''' + TINY_PNG_BASE64 + '''"

@mcp.tool()
def get_text() -> str:
    """Returns plain text — the most common Content block."""
    return "hello as plain text"

@mcp.tool()
def get_image() -> ImageContent:
    """Returns an image as a base64 ImageContent block."""
    return ImageContent(type="image", data=PNG_B64, mimeType="image/png")

@mcp.tool()
def get_resource() -> EmbeddedResource:
    """Returns an EmbeddedResource pointing at an inline document."""
    return EmbeddedResource(
        type="resource",
        resource=TextResourceContents(
            uri="demo://greeting.txt",
            mimeType="text/plain",
            text="hello from an embedded resource",
        ),
    )

if __name__ == "__main__":
    mcp.run()
'''


async def main() -> None:
    # Write the inline server to a temp file we can spawn.
    tmp = Path(__file__).resolve().with_name("_inline_content_server.py")
    tmp.write_text(SERVER_SOURCE, encoding="utf-8")
    try:
        params = StdioServerParameters(command=sys.executable, args=[str(tmp)])
        # Redirect server stderr away from the parent's stderr — FastMCP's
        # startup log lines on Windows can race with the JSON-RPC stdio pipe
        # and trigger spurious "Connection closed" errors.
        with open(os.devnull, "wb") as errsink:
            async with stdio_client(params, errlog=errsink) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    for tool_name in ("get_text", "get_image", "get_resource"):
                        result = await session.call_tool(tool_name, {})
                        print(f"\n=== {tool_name} ===")
                        for block in result.content:
                            block_type = getattr(block, "type", "?")
                            print(f"  type={block_type}")
                            if block_type == "text":
                                print(f"  text={block.text!r}")
                            elif block_type == "image":
                                print(f"  mimeType={block.mimeType}  data_len={len(block.data)} (base64)")
                            elif block_type == "resource":
                                r = block.resource
                                print(f"  uri={r.uri}  mimeType={r.mimeType}  text={getattr(r, 'text', None)!r}")
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())
