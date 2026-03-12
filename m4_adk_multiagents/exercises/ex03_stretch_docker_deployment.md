# Exercise 3 — Deploy Seller to Docker and Run a Networked Negotiation `[Stretch]`

## Goal
Containerize the A2A seller server in Docker and run a real networked negotiation between a local buyer orchestrator and a containerized seller. This teaches you how A2A agents are deployed and discovered across network boundaries — a key production pattern.

## Why this matters
The A2A protocol's value comes from enabling agents built with **different frameworks, languages, and runtimes** to communicate over HTTP. Running the seller in a container proves that the protocol boundary is truly the HTTP API, not shared Python imports.

## Steps

### Step 1 — Create a Dockerfile for the seller

Create `m4_adk_multiagents/Dockerfile.seller`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy only what the seller needs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY m4_adk_multiagents/ ./m4_adk_multiagents/
COPY m2_mcp/ ./m2_mcp/

# The seller server listens on port 9102
EXPOSE 9102

CMD ["python", "m4_adk_multiagents/a2a_protocol_seller_server.py", "--host", "0.0.0.0", "--port", "9102"]
```

### Step 2 — Build and run the container

```bash
# From the negotiation_workshop root:
docker build -f m4_adk_multiagents/Dockerfile.seller -t seller-a2a .

# Run with your OpenAI API key:
docker run -p 9102:9102 -e OPENAI_API_KEY=$env:OPENAI_API_KEY seller-a2a
```

### Step 3 — Verify agent discovery works across the container boundary

```bash
curl http://localhost:9102/.well-known/agent-card.json
```

Or use the script from Exercise 1:
```bash
python m4_adk_multiagents/fetch_agent_card.py
```

### Step 4 — Run the orchestrator locally against the containerized seller

```bash
python m4_adk_multiagents/a2a_protocol_http_orchestrator.py --seller-url http://localhost:9102 --rounds 3
```

The buyer runs locally (native Python), the seller runs in Docker. They communicate purely over A2A HTTP JSON-RPC.

### Step 5 — Verify the interaction

Check that:
- Agent card discovery works (Step 3)
- The negotiation runs for the specified rounds
- The seller responds with properly formatted A2A messages
- The final result matches what you see when both run locally

## Verify
- `docker build` succeeds without errors
- The containerized seller starts and serves the Agent Card
- A full negotiation completes between local buyer and containerized seller
- Results are consistent with the non-containerized version

## Reflection question
> What would need to change to run the buyer in a second container? Think about: how would the buyer discover the seller (DNS vs IP), how would environment variables be managed, and would you need a Docker Compose setup?
