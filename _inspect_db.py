import sqlite3, json, sys

db = sys.argv[1] if len(sys.argv) > 1 else "m3_adk_multiagents/adk_demos/d02_mcp_tools/.adk/session.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=" * 70)
print(f"DATABASE: {db}")
print("=" * 70)

print("\n--- sessions ---")
for r in conn.execute("SELECT * FROM sessions"):
    state = json.loads(r["state"]) if r["state"] else {}
    print(f"  app: {r['app_name']}  user: {r['user_id']}  id: {r['id'][:12]}...")
    print(f"  state: {json.dumps(state, indent=4)}")

print("\n--- events (chronological) ---")
rows = conn.execute("SELECT * FROM events ORDER BY timestamp").fetchall()
print(f"Total: {len(rows)}")
for i, r in enumerate(rows):
    ed = json.loads(r["event_data"])
    author = ed.get("author", "?")
    parts = ed.get("content", {}).get("parts", [])
    summary = []
    for p in parts:
        if "text" in p:
            summary.append(f'text: "{p["text"][:140]}"')
        elif "function_call" in p:
            fc = p["function_call"]
            summary.append(f'tool_call: {fc.get("name","?")}({json.dumps(fc.get("args",{}))[:120]})')
        elif "function_response" in p:
            fr = p["function_response"]
            resp_str = json.dumps(fr.get("response", {}))
            summary.append(f'tool_result: {fr.get("name","?")} -> {resp_str[:180]}')
    finish = ed.get("finish_reason", "")
    model = ed.get("model_version", "")
    if summary:
        label = f"Event {i+1}/{len(rows)} | author: {author}"
        if model: label += f" | model: {model}"
        if finish: label += f" | finish: {finish}"
        print(f"\n  {label}")
        for s in summary:
            print(f"    {s}")

print("\n--- app_states ---")
rows = conn.execute("SELECT * FROM app_states").fetchall()
print(f"  ({len(rows)} rows)")
for r in rows: print(f"  {dict(r)}")

print("\n--- user_states ---")
rows = conn.execute("SELECT * FROM user_states").fetchall()
print(f"  ({len(rows)} rows)")
for r in rows: print(f"  {dict(r)}")

conn.close()
