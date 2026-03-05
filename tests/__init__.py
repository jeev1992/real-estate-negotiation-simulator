"""
Test Suite — Real Estate Negotiation Workshop
=============================================
Tests that run WITHOUT API keys (no OpenAI/Gemini calls).

Run all tests:
    pytest tests/

Run a specific file:
    pytest tests/test_fsm.py -v
    pytest tests/test_a2a.py -v

WHAT IS TESTED:
  test_fsm.py  — NegotiationFSM state machine (pure logic, no LLM)
  test_a2a.py  — A2A message schema and state machine validation
"""
