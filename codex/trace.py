#!/usr/bin/env python3
"""SHAPE trace logger — PostToolUse hook for OpenAI Codex CLI."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path("/tmp/shape-sessions")

def main():
    event = json.loads(sys.stdin.read())
    sid = event.get("session_id", os.environ.get("SHAPE_SESSION", "default"))
    p = SESSIONS_DIR / f"{sid}.json"
    if not p.exists():
        sys.exit(0)

    state = json.loads(p.read_text())
    tool_name = event.get("tool_name", "unknown")

    for trace in reversed(state["traces"]):
        if trace["tool"] == tool_name and "result_success" not in trace:
            trace["result_success"] = event.get("success", True)
            trace["completed_at"] = datetime.now(timezone.utc).isoformat()
            break

    p.write_text(json.dumps(state, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
