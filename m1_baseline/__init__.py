"""
Baseline — Intentionally Broken Naive Negotiation
===================================================
Run this FIRST to understand WHY the rest of the architecture exists.

Files:
  naive_negotiation.py  — The broken naive implementation (10 failure modes)
  state_machine.py      — The FSM that solves termination (Layer 7 fix)

Teaching sequence:
  1. python m1_m1_baseline/naive_negotiation.py      ← Watch it fail
  2. python m1_m1_baseline/state_machine.py          ← Add termination guarantee
  3. python main_simple.py                     ← Full MCP + A2A + LangGraph version
"""
