#!/usr/bin/env python3
"""SHAPE gate for OpenAI Codex CLI — PreToolUse hook enforcing phases, budget, and rules.

Reads hook event JSON from stdin. Exits 0 to allow, 2 to block (stderr → LLM).
State persisted per session in /tmp/shape-sessions/.

Usage in codex config:
  hooks.pre_tool_use = "python3 /path/to/gate.py"
"""
import json, os, sys, re
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path("/tmp/shape-sessions")
RULES_FILE = Path(os.environ.get("SHAPE_RULES", os.path.expanduser("~/.codex/shape/rules.shape")))
DEFAULT_BUDGET = float(os.environ.get("SHAPE_BUDGET", "5.0"))

WRITE_TOOLS = {"shell", "write_file", "apply_patch", "create_file"}
READ_TOOLS = {"read_file", "list_dir", "search"}
TOOL_COSTS = {"shell": 0.05, "write_file": 0.02, "apply_patch": 0.02, "create_file": 0.02}

PHASE_ALLOWS_WRITE = {"explore": False, "decide": False, "commit": True}

def tool_effect(name):
    if name in READ_TOOLS:
        return "read"
    if name in WRITE_TOOLS:
        return "write"
    return "write"  # default to write for safety

_RULE_RE = re.compile(r"^(BLOCK|FLAG|ALLOW)\s+(\S+)\s+WHEN\s+(.+)$", re.IGNORECASE)
_COND_RE = re.compile(r"(phase|budget|tool|time)\s+(IS NOT|IS|ABOVE|BELOW)\s+(\S+)", re.IGNORECASE)

def parse_rules(text):
    rules = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _RULE_RE.match(line)
        if not m:
            continue
        conditions = [(c.group(1).lower(), c.group(2).upper(), c.group(3).lower())
                      for c in _COND_RE.finditer(m.group(3))]
        rules.append({"action": m.group(1).upper(), "tool": m.group(2), "conditions": conditions})
    return rules

def eval_rule(rule, ctx, tool_name):
    pat = rule["tool"]
    if pat != "*" and pat != tool_name and not tool_name.endswith(pat):
        return False
    for field, op, val in rule["conditions"]:
        actual = str(ctx.get(field, "")).lower()
        if op == "IS" and actual != val: return False
        if op == "IS NOT" and actual == val: return False
        if op == "ABOVE":
            try:
                if float(ctx.get(field, 0)) <= float(val.rstrip("%")): return False
            except ValueError: return False
        if op == "BELOW":
            try:
                if float(ctx.get(field, 0)) >= float(val.rstrip("%")): return False
            except ValueError: return False
    return True

def session_path(sid):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{sid}.json"

def load_session(sid):
    p = session_path(sid)
    if p.exists():
        return json.loads(p.read_text())
    return {"phase": "explore", "budget_spent": 0.0, "budget_limit": DEFAULT_BUDGET,
            "traces": [], "call_count": 0}

def save_session(sid, state):
    session_path(sid).write_text(json.dumps(state, indent=2))

def main():
    event = json.loads(sys.stdin.read())
    tool_name = event.get("tool_name", "unknown")
    session_id = event.get("session_id", os.environ.get("SHAPE_SESSION", "default"))

    state = load_session(session_id)
    phase = state["phase"]
    budget_pct = (state["budget_spent"] / state["budget_limit"] * 100) if state["budget_limit"] > 0 else 0
    effect = tool_effect(tool_name)
    blocks = []

    if effect == "write" and not PHASE_ALLOWS_WRITE.get(phase, False):
        blocks.append(f"⛔ {tool_name} blocked: write tool in '{phase}' phase (only allowed in 'commit')")

    if budget_pct >= 100:
        blocks.append(f"⛔ Budget exhausted ({budget_pct:.0f}%)")
    elif budget_pct >= 75 and phase == "commit":
        blocks.append(f"⛔ Budget ≥75% ({budget_pct:.0f}%), must exit commit phase first")

    if RULES_FILE.exists():
        ctx = {"phase": phase, "budget": budget_pct, "tool": effect,
               "time": datetime.now(timezone.utc).strftime("%H:%M")}
        for rule in parse_rules(RULES_FILE.read_text()):
            if eval_rule(rule, ctx, tool_name) and rule["action"] == "BLOCK":
                blocks.append(f"⛔ Rule: BLOCK {rule['tool']} matched")

    cost = TOOL_COSTS.get(tool_name, 0.01)
    trace = {"tool": tool_name, "phase": phase, "effect": effect, "budget_pct": round(budget_pct, 1),
             "decision": "BLOCKED" if blocks else "ALLOWED",
             "ts": datetime.now(timezone.utc).isoformat()}
    state["traces"].append(trace)
    state["call_count"] += 1

    if blocks:
        save_session(session_id, state)
        msg = "\n".join(blocks)
        msg += f"\n\nSHAPE state: phase={phase} | budget={budget_pct:.0f}% | calls={state['call_count']}"
        msg += "\nTo transition phase: shape-transition <explore|decide|commit>"
        print(msg, file=sys.stderr)
        sys.exit(2)

    state["budget_spent"] += cost
    save_session(session_id, state)
    sys.exit(0)

if __name__ == "__main__":
    main()
