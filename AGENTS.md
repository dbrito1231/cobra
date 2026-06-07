# C.O.B.R.A. — Cursor Agent System

You are working on **C.O.B.R.A.** (*Cognitive Optimized Brain for Retrieval and Action*), a local-first AI assistant. This project uses a multi-agent development system.

## Default role: Lead Developer

When no component subagent is explicitly invoked, act as the **Lead Developer** defined in `agents/AGENTS.md`. Read that file for full responsibilities, the spec index, interface contracts, review format, and escalation rules.

**Hard rules:**
- Specs under `specs/` are the single source of truth.
- Never guess — cite a spec or escalate to Damian.
- Never mark work complete without a documented PASS review.
- Catch and fix spec↔code drift in both directions.

## Component subagents

Specialized subagents live in `.cursor/agents/` and mirror the canonical briefs in `agents/`:

| Subagent | Canonical brief | Specs | Code |
|---|---|---|---|
| `lead-developer` | `agents/AGENTS.md` | all `specs/` | all `src/` |
| `config-agent` | `agents/config-agent.md` | `specs/configuration/` | — |
| `security-agent` | `agents/security-agent.md` | `specs/security/` | — |
| `mcp-agent` | `agents/mcp-agent.md` | `specs/mcp-server-layer/` | — |
| `brain-agent` | `agents/brain-agent.md` | `specs/brain/`, `specs/seed-document/` | — |
| `tools-agent` | `agents/tools-agent.md` | `specs/tools/` | `src/tools/` |
| `voice-agent` | `agents/voice-agent.md` | `specs/voice/` | — |
| `chat-ui-agent` | `agents/chat-ui-agent.md` | `specs/chat-ui/` | `src/chat_ui/` |
| `orchestrator-agent` | `agents/orchestrator-agent.md` | `specs/orchestrator/` | — |
| `spec-sync-agent` | `agents/spec-sync-agent.md` | all `specs/` vs code | — |

## How to use agents in Cursor

1. **Automatic delegation** — The agent delegates to `.cursor/agents/` subagents when the task matches their `description`.
2. **Explicit invocation** — `/tools-agent implement sandboxing` or "Use the tools-agent subagent to…"
3. **Manual context** — Attach briefs with `@agents/tools-agent.md` or `@agents/` for the full agent library.
4. **Coordination** — The Lead Developer dispatches work following the dependency graph in `agents/AGENTS.md` §5.

## Dependency order

```
Phase 1:  Configuration, Security
Phase 2:  MCP Server Layer, Brain, Tools  (parallel)
Phase 3:  Voice, Chat UI                  (parallel; LM Studio gate first)
Phase 4:  Orchestrator                    (wires everything last)
```

## Updating agent definitions

Edit the canonical brief in `agents/<name>.md`, then sync the matching `.cursor/agents/<name>.md` if the body changed materially. The `agents/` folder is the source of truth for role content; `.cursor/agents/` adds Cursor frontmatter for discovery and delegation.

## Cursor Cloud specific instructions

C.O.B.R.A. is a **single Python process** (Orchestrator) with an embedded FastAPI Chat UI — not a multi-service monorepo. There is no `package.json`, Docker Compose, or dedicated lint config.

### Install

```bash
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

Optional voice ML stack: `pip install -r requirements-voice.txt` (heavy; tests use stubs).

### Lint

Not configured. No ruff/flake8/mypy CI job. Skip lint unless a linter is added to the repo.

### Test

```bash
PYTHONPATH=src COBRA_SKIP_LM_STUDIO=1 COBRA_BRAIN_OFFLINE=1 python3 -m pytest tests/ -q --tb=short
```

Matches `.github/workflows/test.yml`. `tests/conftest.py` adds `src/` to `sys.path`.

**Known Linux caveat:** `tests/tools/test_system_control.py::test_status_includes_volume_brightness_wifi` may fail on headless Linux VMs (brightness subprocess returns `str` instead of `bytes`). 204/205 tests pass otherwise.

Several config/orchestrator tests also expect `~/.cobra/config.yaml` to exist; create it before running the full suite (see below).

### Run (dev)

**Full app (recommended):**

```bash
export PYTHONPATH=src
export COBRA_SKIP_LM_STUDIO=1      # bypass LM Studio gate
export COBRA_BRAIN_OFFLINE=1       # offline brain stub responses
export COBRA_UI_OPEN_BROWSER=0     # headless / cloud VMs
python3 -m orchestrator
```

Chat UI: `http://127.0.0.1:8765` (override with `COBRA_UI_HOST` / `COBRA_UI_PORT`).

**Chat UI only** (no Brain/Voice wiring):

```bash
PYTHONPATH=src python3 -m chat_ui --host 127.0.0.1 --port 8765 --no-browser
```

**First-run config:** Orchestrator requires `~/.cobra/config.yaml`. Quick bootstrap:

```bash
PYTHONPATH=src python3 -c "from config.loader import ensure_config; from config.models import ApiKeys; from config.loader import save_config, load_config; c=ensure_config(); p=c.active(); p.api_keys=ApiKeys(claude='sk-dev-claude-key', copilot='copilot-dev-key'); save_config(c)"
```

Or complete the setup wizard in the Chat UI on first launch.

**LM Studio** is required for real inference (`http://127.0.0.1:1234`). Omit the `COBRA_SKIP_LM_STUDIO` / `COBRA_BRAIN_OFFLINE` flags when LM Studio is running with a loaded model.

Use **tmux** for long-running `python3 -m orchestrator` sessions in Cloud VMs.
