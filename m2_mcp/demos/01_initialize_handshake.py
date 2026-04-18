"""
Demo 01 — MCP `initialize` handshake on the wire
=================================================
Spawns `m2_mcp/pricing_server.py` as a subprocess and prints every JSON-RPC
frame exchanged during the MCP handshake. No SDK, no abstraction — raw
JSON-RPC over stdio so you can see exactly what the protocol looks like.

Run:
    python m2_mcp/demos/01_initialize_handshake.py

You will see:
    1. client -> server   initialize          (capabilities, clientInfo)
    2. server -> client   initialize result   (negotiated protocolVersion)
    3. client -> server   notifications/initialized
    4. client -> server   tools/list
    5. server -> client   tools/list result
"""

import json
import subprocess
import sys
from pathlib import Path

PRICING_SERVER = Path(__file__).resolve().parents[1] / "pricing_server.py"


def send(proc: subprocess.Popen, payload: dict) -> None:
    line = json.dumps(payload) + "\n"
    print(f"\n>>> client -> server\n{json.dumps(payload, indent=2)}")
    proc.stdin.write(line)
    proc.stdin.flush()


def recv(proc: subprocess.Popen) -> dict:
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("Server closed stdout")
    msg = json.loads(line)
    print(f"\n<<< server -> client\n{json.dumps(msg, indent=2)}")
    return msg


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, str(PRICING_SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    try:
        # 1. initialize — handshake. The client tells the server which
        #    protocol version + capabilities it supports; server responds with
        #    the negotiated version + its own capabilities.
        send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "demo-client", "version": "0.1"},
            },
        })
        recv(proc)

        # 2. notifications/initialized — required follow-up so server knows
        #    the client is ready to receive requests. No response expected.
        send(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        # 3. tools/list — now that the handshake is done we can use the
        #    server's primitives. Asking for the catalog of tools.
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        recv(proc)

        print("\n--- handshake complete ---")
    finally:
        proc.terminate()
        proc.wait(timeout=2)


if __name__ == "__main__":
    main()
