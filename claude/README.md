# SHAPE → Claude Code Integration

Implements SHAPE governance as Claude Code hooks (Architecture A: SHAPE as hook).

## What it does

- **Phase enforcement** — blocks write tools (`write`, `edit`, `bash`) unless in `commit` phase
- **Budget gates** — tracks cumulative cost per session, blocks at thresholds
- **Rule DSL** — evaluates `.shape` rules before each tool call
- **Proof traces** — logs every tool call decision to session state

## Setup

```bash
# Copy hooks to your project's .claude directory
mkdir -p .claude/shape
cp gate.py trace.py .claude/shape/
cp rules.shape .claude/shape/

# Add hooks to .claude/settings.json (or merge with existing)
cp settings.json .claude/settings.json

# Update paths in settings.json to point to your gate.py location

# Make transition script accessible (shared with other integrations)
ln -sf "$(pwd)/../kiro/transition.py" ~/.local/bin/shape-transition
```

## Usage

```bash
# Start Claude Code — agent begins in EXPLORE phase (read-only)
claude

# To allow writes, in another terminal:
shape-transition commit

# To go back to safe mode:
shape-transition explore

# Check session state:
cat /tmp/shape-sessions/default.json | python3 -m json.tool
```

## Files

| File | Purpose |
|------|---------|
| `gate.py` | PreToolUse hook — evaluates phase/budget/rules, blocks or allows |
| `trace.py` | PostToolUse hook — logs tool results to session traces |
| `rules.shape` | Example governance rules |
| `settings.json` | Claude Code hook configuration example |

## Limitations (Architecture A)

- No transactional atomicity — each tool call is independent
- No compensation/rollback on failure
- Budget is estimated, not actual API cost
- Phase transitions are manual (user runs `shape-transition`)

For full SHAPE governance including transactions, use Architecture B (SHAPE as orchestrator wrapping the agent).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHAPE_RULES` | `~/.claude/shape/rules.shape` | Path to rules file |
| `SHAPE_BUDGET` | `5.0` | Session budget limit |
| `SHAPE_SESSION` | `default` | Session identifier |
