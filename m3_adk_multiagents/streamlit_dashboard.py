"""
Negotiation Dashboard — Streamlit UI for A2A Negotiations
==========================================================
Visual dashboard that runs the A2A negotiation orchestrator and
displays rounds, price convergence, tool calls, and outcomes in real time.

PREREQUISITES:
  1. Start the seller A2A server in a separate terminal:
     python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102

  2. Run this dashboard:
     streamlit run m3_adk_multiagents/streamlit_dashboard.py

WHAT IT SHOWS:
  - Live round-by-round negotiation progress
  - Price convergence chart (buyer offers vs seller counters)
  - Tool calls made by each agent
  - Final outcome: AGREED / DEADLOCKED / BUYER_WALKED
  - Full message history with expandable details
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import streamlit as st

# Ensure repo root is importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

import httpx
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import Message, MessageSendParams, Role, SendMessageRequest, TextPart
from pydantic import ValidationError

from m3_adk_multiagents.buyer_adk import BuyerAgentADK


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_texts(obj) -> list[str]:
    """Recursively extract all 'text' values from nested A2A response."""
    texts = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "text" and isinstance(v, str):
                texts.append(v)
            else:
                texts.extend(_extract_texts(v))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_extract_texts(item))
    return texts


def _extract_first_envelope(payload: dict) -> dict | None:
    """Find the first valid seller JSON envelope in A2A response text parts.

    The A2A response may include conversation history containing the buyer's
    original message alongside the seller's response. We filter for
    from_agent == 'seller' to avoid returning the buyer's own envelope,
    which would cause the orchestrator to miss ACCEPT/REJECT signals.
    """
    for text in _extract_texts(payload):
        try:
            candidate = json.loads(text)
            if (
                isinstance(candidate, dict)
                and candidate.get("from_agent") == "seller"
                and "message_type" in candidate
            ):
                return candidate
        except (json.JSONDecodeError, ValueError):
            continue
    return None


# ─── Async orchestration ─────────────────────────────────────────────────────

async def run_negotiation(seller_url: str, max_rounds: int, progress_callback):
    """Run the A2A negotiation and call progress_callback after each round."""
    session_id = f"dashboard_{uuid.uuid4().hex[:8]}"
    rounds_data = []

    async with BuyerAgentADK(session_id=f"{session_id}_buyer") as buyer:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            # Discover seller
            resolver = A2ACardResolver(httpx_client=http_client, base_url=seller_url)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            last_seller = None
            status = "negotiating"
            agreed_price = None

            for round_num in range(1, max_rounds + 1):
                round_info = {"round": round_num, "buyer": {}, "seller": {}, "status": "negotiating"}

                # Buyer turn
                if round_num == 1:
                    buyer_message = await buyer.make_initial_offer_envelope()
                else:
                    if last_seller is None:
                        break
                    buyer_message = await buyer.respond_to_counter_envelope(last_seller)

                round_info["buyer"] = buyer_message

                if buyer_message.get("message_type") == "WITHDRAW":
                    round_info["status"] = "buyer_walked"
                    status = "buyer_walked"
                    rounds_data.append(round_info)
                    progress_callback(rounds_data, status, agreed_price)
                    break

                # Seller turn via A2A
                request = SendMessageRequest(
                    id=f"req_{uuid.uuid4().hex[:8]}",
                    params=MessageSendParams(
                        message=Message(
                            messageId=f"msg_{uuid.uuid4().hex[:8]}",
                            role=Role.user,
                            parts=[TextPart(text=json.dumps(buyer_message))],
                        )
                    ),
                )

                response = await client.send_message(request)
                dumped = response.model_dump(mode="json")
                seller_message = _extract_first_envelope(dumped)

                if seller_message is None:
                    round_info["status"] = "error"
                    round_info["seller"] = {"error": "Could not parse seller response"}
                    status = "error"
                    rounds_data.append(round_info)
                    progress_callback(rounds_data, status, agreed_price)
                    break

                last_seller = seller_message
                round_info["seller"] = seller_message

                if seller_message.get("message_type") == "ACCEPT":
                    status = "agreed"
                    agreed_price = seller_message.get("price")
                    round_info["status"] = "agreed"
                elif seller_message.get("message_type") == "REJECT":
                    status = "seller_rejected"
                    round_info["status"] = "seller_rejected"
                else:
                    round_info["status"] = "negotiating"

                rounds_data.append(round_info)
                progress_callback(rounds_data, status, agreed_price)

                if status != "negotiating":
                    break

            if status == "negotiating":
                status = "deadlocked"
                progress_callback(rounds_data, status, agreed_price)

    return rounds_data, status, agreed_price


# ─── Streamlit UI ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Real Estate Negotiation Dashboard",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Real Estate Negotiation Dashboard")
st.markdown("**A2A Protocol Negotiation** — Buyer and Seller agents communicating over HTTP")

# Sidebar controls
with st.sidebar:
    st.header("Configuration")
    seller_url = st.text_input("Seller A2A URL", value="http://127.0.0.1:9102")
    max_rounds = st.slider("Max Rounds", min_value=1, max_value=10, value=5)

    api_key_set = bool(os.environ.get("OPENAI_API_KEY"))
    if api_key_set:
        st.success("OPENAI_API_KEY is set")
    else:
        st.error("OPENAI_API_KEY not found in .env")

    st.markdown("---")
    st.markdown("""
    **How to use:**
    1. Start the seller server in a terminal:
       ```
       python m3_adk_multiagents/a2a_protocol_seller_server.py --port 9102
       ```
    2. Click **Start Negotiation** below
    """)

    start_button = st.button("🚀 Start Negotiation", type="primary", disabled=not api_key_set)

# Main content area
if "rounds_data" not in st.session_state:
    st.session_state.rounds_data = []
    st.session_state.status = None
    st.session_state.agreed_price = None
    st.session_state.running = False

# Placeholders for live updates
status_placeholder = st.empty()
chart_placeholder = st.empty()
rounds_placeholder = st.empty()
result_placeholder = st.empty()


def render_dashboard(rounds_data, status, agreed_price):
    """Render the current state of the negotiation."""

    # Status banner
    with status_placeholder.container():
        if status == "agreed":
            st.success(f"✅ DEAL REACHED at ${agreed_price:,.0f}" if agreed_price else "✅ DEAL REACHED")
        elif status == "deadlocked":
            st.warning(f"⏸️ DEADLOCKED after {len(rounds_data)} rounds — no agreement")
        elif status == "buyer_walked":
            st.error("🚶 BUYER WALKED AWAY")
        elif status == "seller_rejected":
            st.error("❌ SELLER REJECTED")
        elif status == "error":
            st.error("⚠️ ERROR during negotiation")
        else:
            st.info(f"🔄 Negotiating... Round {len(rounds_data)} of {max_rounds}")

    # Price convergence chart
    if rounds_data:
        with chart_placeholder.container():
            st.subheader("Price Convergence")

            import pandas as pd
            chart_data = []
            for r in rounds_data:
                row = {"Round": r["round"]}
                buyer_price = r.get("buyer", {}).get("price")
                seller_price = r.get("seller", {}).get("price")
                if buyer_price:
                    row["Buyer Offer"] = buyer_price
                if seller_price:
                    row["Seller Counter"] = seller_price
                chart_data.append(row)

            df = pd.DataFrame(chart_data)
            if "Buyer Offer" in df.columns or "Seller Counter" in df.columns:
                plot_cols = [c for c in ["Buyer Offer", "Seller Counter"] if c in df.columns]
                st.line_chart(df.set_index("Round")[plot_cols])

            # Show the zone of agreement
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Buyer Budget Ceiling", "$460,000")
            with col2:
                st.metric("Seller Floor", "$445,000")
            with col3:
                st.metric("Zone of Agreement", "$445K – $460K")

    # Round-by-round details
    if rounds_data:
        with rounds_placeholder.container():
            st.subheader("Round History")

            for r in reversed(rounds_data):
                round_num = r["round"]
                buyer = r.get("buyer", {})
                seller = r.get("seller", {})

                with st.expander(
                    f"Round {round_num} — "
                    f"Buyer: ${buyer.get('price', 0):,.0f} → "
                    f"Seller: {'${:,.0f}'.format(seller.get('price', 0)) if seller.get('price') else seller.get('message_type', 'N/A')}",
                    expanded=(round_num == len(rounds_data)),
                ):
                    col_b, col_s = st.columns(2)

                    with col_b:
                        st.markdown("**🛒 Buyer**")
                        st.markdown(f"**Type:** `{buyer.get('message_type', 'N/A')}`")
                        if buyer.get("price"):
                            st.markdown(f"**Price:** ${buyer['price']:,.0f}")
                        st.markdown(f"**Message:** {buyer.get('message', 'N/A')}")
                        conditions = buyer.get("conditions", [])
                        if conditions:
                            st.markdown(f"**Conditions:** {', '.join(conditions)}")

                    with col_s:
                        st.markdown("**🏠 Seller**")
                        if seller:
                            st.markdown(f"**Type:** `{seller.get('message_type', 'N/A')}`")
                            if seller.get("price"):
                                st.markdown(f"**Price:** ${seller['price']:,.0f}")
                            st.markdown(f"**Message:** {seller.get('message', 'N/A')}")
                        else:
                            st.markdown("*(no response yet)*")


def progress_callback(rounds_data, status, agreed_price):
    """Called after each round to update the UI."""
    st.session_state.rounds_data = rounds_data
    st.session_state.status = status
    st.session_state.agreed_price = agreed_price
    render_dashboard(rounds_data, status, agreed_price)


# Run negotiation when button is clicked
if start_button:
    st.session_state.rounds_data = []
    st.session_state.status = "negotiating"
    st.session_state.agreed_price = None

    with st.spinner("Running negotiation over A2A..."):
        try:
            rounds_data, status, agreed_price = asyncio.run(
                run_negotiation(seller_url, max_rounds, progress_callback)
            )
            st.session_state.rounds_data = rounds_data
            st.session_state.status = status
            st.session_state.agreed_price = agreed_price
        except Exception as e:
            st.error(f"Negotiation failed: {e}")
            st.session_state.status = "error"

    render_dashboard(
        st.session_state.rounds_data,
        st.session_state.status,
        st.session_state.agreed_price,
    )

# Render existing state on page load (after rerun)
elif st.session_state.rounds_data:
    render_dashboard(
        st.session_state.rounds_data,
        st.session_state.status,
        st.session_state.agreed_price,
    )
else:
    st.info("👆 Configure the seller URL and click **Start Negotiation** to begin.")
    st.markdown("""
    ### What this dashboard shows

    | Feature | Description |
    |---|---|
    | **Price Convergence Chart** | Buyer offers and seller counters plotted per round |
    | **Round History** | Expandable details for each round — messages, conditions, prices |
    | **Status Banner** | Live status: negotiating, agreed, deadlocked, walked away |
    | **Zone of Agreement** | Visual reference for buyer ceiling ($460K) and seller floor ($445K) |

    The negotiation runs over **A2A HTTP** — the buyer and seller are separate processes
    communicating via JSON-RPC, exactly as they would in production.
    """)
