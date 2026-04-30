#!/usr/bin/env python3
"""Transition SHAPE phase for a Kiro session.

Usage: shape-transition <explore|decide|commit> [session_id]
"""
import json, sys
from pathlib import Path

SESSIONS_DIR = Path("/tmp/shape-sessions")
VALID = {"explore", "decide", "commit"}
TRANSITIONS = {
    "explore": {"decide"},
    "decide": {"explore", "commit"},
    "commit": {"decide", "explore"},
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in VALID:
        print(f"Usage: {sys.argv[0]} <{'|'.join(VALID)}> [session_id]")
        sys.exit(1)

    target = sys.argv[1]
    sid = sys.argv[2] if len(sys.argv) > 2 else "default"
    p = SESSIONS_DIR / f"{sid}.json"

    if not p.exists():
        print(f"No session '{sid}' found. Start a Kiro session with SHAPE gate first.")
        sys.exit(1)

    state = json.loads(p.read_text())
    current = state["phase"]

    if target == current:
        print(f"Already in '{current}' phase.")
        sys.exit(0)

    if target not in TRANSITIONS.get(current, set()):
        print(f"Cannot transition {current} → {target}. Valid: {TRANSITIONS[current]}")
        sys.exit(1)

    state["phase"] = target
    p.write_text(json.dumps(state, indent=2))
    print(f"✓ Phase: {current} → {target}")

    budget_pct = (state["budget_spent"] / state["budget_limit"] * 100) if state["budget_limit"] > 0 else 0
    print(f"  Budget: {budget_pct:.0f}% used | Calls: {state['call_count']}")

if __name__ == "__main__":
    main()
