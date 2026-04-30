# SHAPE → Kiro CLI Integration

Implements SHAPE governance as Kiro CLI hooks (Architecture A: SHAPE as hook).

## What it does

- **Phase enforcement** — blocks write tools (`fs_write`, `execute_bash`, `use_aws`) unless in `commit` phase
- **Budget gates** — tracks cumulative cost per session, blocks at thresholds (75% blocks commit, 100% blocks all)
- **Rule DSL** — evaluates `.shape` rules before each tool call
- **Proof traces** — logs every tool call decision to session state

## Setup

```bash
# Copy agent config to Kiro
cp shape-governed.json ~/.kiro/agents/

# Copy rules (or set SHAPE_RULES env var)
mkdir -p ~/.kiro/shape
cp rules.shape ~/.kiro/shape/

# Make transition script accessible
ln -sf "$(pwd)/transition.py" ~/.local/bin/shape-transition
chmod +x transition.py
```

## Usage

```bash
# Start Kiro with SHAPE governance
kiro-cli chat --agent shape-governed

# Agent starts in EXPLORE phase (read-only)
# To allow writes:
shape-transition decide        # propose changes
shape-transition commit        # execute changes

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
| `transition.py` | CLI tool to change SHAPE phase |
| `rules.shape` | Example governance rules |
| `shape-governed.json` | Kiro agent configuration |

## Limitations (Architecture A)

- No transactional atomicity (each tool call is independent)
- No compensation/rollback on failure
- Budget is estimated, not actual API cost
- Phase transitions are manual (user runs `shape-transition`)

For full SHAPE governance including transactions, use Architecture B (SHAPE as orchestrator wrapping Kiro via `-p` flag).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHAPE_RULES` | `~/.kiro/shape/rules.shape` | Path to rules file |
| `SHAPE_BUDGET` | `5.0` | Session budget limit |
