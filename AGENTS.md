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
