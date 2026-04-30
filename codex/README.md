# SHAPE → OpenAI Codex CLI Integration

Implements SHAPE governance as Codex CLI hooks (Architecture A: SHAPE as hook).

## What it does

- **Phase enforcement** — blocks write tools (`write_file`, `apply_patch`, `create_file`, `shell`) unless in `commit` phase
- **Budget gates** — tracks cumulative cost per session, blocks at thresholds
- **Rule DSL** — evaluates `.shape` rules before each tool call
- **Proof traces** — logs every tool call decision to session state

## Setup

```bash
# Copy hooks to Codex config directory
mkdir -p ~/.codex/shape
cp gate.py trace.py ~/.codex/shape/
cp rules.shape ~/.codex/shape/

# Add hook config (merge with existing codex config)
cp codex-config.json ~/.codex/config.json

# Update paths in config to point to your gate.py location

# Make transition script accessible (shared with other integrations)
ln -sf "$(pwd)/../kiro/transition.py" ~/.local/bin/shape-transition
```

## Usage

```bash
# Start Codex — agent begins in EXPLORE phase (read-only)
codex

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
| `codex-config.json` | Codex CLI hook configuration example |

## Limitations (Architecture A)

- No transactional atomicity — each tool call is independent
- No compensation/rollback on failure
- Budget is estimated, not actual API cost
- Phase transitions are manual (user runs `shape-transition`)

For full SHAPE governance including transactions, use Architecture B (SHAPE as orchestrator wrapping the agent).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHAPE_RULES` | `~/.codex/shape/rules.shape` | Path to rules file |
| `SHAPE_BUDGET` | `5.0` | Session budget limit |
| `SHAPE_SESSION` | `default` | Session identifier |
