# C.O.B.R.A. Orchestrator — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Orchestrator is the top-level manager of C.O.B.R.A. It is responsible for starting, stopping, monitoring, and coordinating all components. It is the first thing that runs when C.O.B.R.A. launches and the last thing that stops when C.O.B.R.A. shuts down. Every component reports to the Orchestrator.

---

## 1. Component Registry

The Orchestrator maintains a registry of all C.O.B.R.A. components:

| Component | Dependencies |
|---|---|
| Configuration | None — loads first |
| Security | Configuration |
| MCP Server Layer | Configuration |
| Brain | Configuration, MCP Server Layer |
| Voice Layer | Configuration, Brain |
| Chat UI | Configuration, Brain, Voice Layer |
| Tools | Brain, MCP Server Layer |
| Orchestrator | None — manages all |

---

## 2. Startup — Parallel Where Possible

Components start in the fastest safe order based on dependencies:

**Phase 1 — No dependencies (parallel):**
- Configuration loads and validates

**Phase 2 — Depends on Configuration (parallel):**
- Security initializes
- MCP Server Layer connects and validates servers

**Phase 3 — Depends on Phase 2 (parallel):**
- Brain initializes (requires Config + MCP)
- Tools initializes (requires Config + MCP)

**Phase 4 — Depends on Brain:**
- Voice Layer initializes (requires Brain)
- Chat UI starts (requires Brain)

Each component signals the Orchestrator when it is ready. The Orchestrator waits for all dependencies before advancing to the next phase. LM Studio is a special case — the Orchestrator waits indefinitely for it to become available (per the Configuration spec) before Phase 3 begins.

---

## 3. Health Monitoring

The Orchestrator runs **continuous health checks** on all components:

- Each component exposes a health endpoint the Orchestrator pings at a defined interval
- If a component fails to respond → Orchestrator marks it degraded
- If a component reports an error → Orchestrator marks it failed
- Health status is displayed live in the Chat UI status panel
- **Any degraded or failed component triggers an immediate user alert** — voice + Chat UI

Health states:
- **Healthy** — component responding normally
- **Degraded** — component responding but reporting issues
- **Failed** — component not responding or crashed
- **Restarting** — component is being restarted by the Orchestrator

---

## 4. Individual Component Restart

Any component can be restarted individually without restarting all of C.O.B.R.A.:

- When a component fails, the Orchestrator immediately alerts the user and asks what to do
- Options presented: Restart this component / Ignore for now / Restart all of C.O.B.R.A.
- If the user chooses restart: only that component restarts, all others continue running
- The Orchestrator re-validates the restarted component before marking it healthy
- Dependent components are paused during the restart and resume automatically when the component is healthy again

---

## 5. Failure Policy

On any component failure, the Orchestrator immediately asks the user what to do. There is no automatic silent retry — every failure surfaces to the user.

Options the user can choose from:
- **Restart component** — attempt one restart immediately
- **Ignore for now** — mark as unavailable, continue with remaining components
- **Restart all of C.O.B.R.A.** — full clean restart

If the user chooses restart and the restart also fails, the Orchestrator asks again — it never silently gives up.

---

## 6. Lifecycle Logging

Every component lifecycle event is logged in full:

- Component name
- Event type: Start / Stop / Restart / Degraded / Failed / Recovered
- Timestamp
- Trigger: Startup / User command / Health check failure / Dependency failure
- Outcome: Success / Failure + error message

Logs stored at `~/.cobra/logs/orchestrator.log` — local only, never sent externally.

---

## 7. Graceful Shutdown

When the user shuts down C.O.B.R.A.:

1. Orchestrator receives shutdown signal
2. Waits for C.O.B.R.A. to finish any response currently in progress
3. Triggers end-of-session summarization in the brain (wiki ingest)
4. Stops components in reverse startup order:
   - Chat UI stops first
   - Voice Layer stops
   - Tools stops
   - Brain stops (completes memory write)
   - MCP Server Layer disconnects
   - Security finalizes audit log
   - Configuration saves state
5. Orchestrator exits cleanly

No data is lost. The current session is always summarized before shutdown.

---

## 8. Inter-Component Communication

All components communicate through the Orchestrator — no component talks directly to another without the Orchestrator's awareness:

- Components publish events to the Orchestrator (e.g. "pipeline step changed", "MCP server went offline")
- Orchestrator routes events to relevant subscribers (e.g. Chat UI receives pipeline step updates)
- This keeps component coupling minimal and makes failures traceable

---

## Open Items

- [ ] Define health check ping interval (e.g. every 10 seconds)
- [ ] Define health check timeout before marking a component degraded
- [ ] Define whether the Orchestrator itself has a watchdog process to restart it if it crashes
- [ ] Define inter-component communication protocol (e.g. internal message bus, WebSocket, direct function calls)
- [ ] Define whether component restart attempts have a cooldown period

---

## Component Specs

Decomposed, implementable specs live in **`specs/orchestrator/`**. The parent document and [orchestrator-flow.mermaid](orchestrator-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [orchestrator/orchestrator-overview.md](orchestrator/orchestrator-overview.md) | Overall orchestrator index and cross-cutting rules |
| [orchestrator/implementation-plan.md](orchestrator/implementation-plan.md) | Phased implementation plan |
| [orchestrator/component-registry.md](orchestrator/component-registry.md) | Component dependency registry |
| [orchestrator/startup-phases.md](orchestrator/startup-phases.md) | Phased parallel startup and LM Studio gate |
| [orchestrator/health-monitoring.md](orchestrator/health-monitoring.md) | Continuous health checks and alerts |
| [orchestrator/failure-response.md](orchestrator/failure-response.md) | User-driven restart, ignore, or full relaunch |
| [orchestrator/lifecycle-logging.md](orchestrator/lifecycle-logging.md) | Local orchestrator lifecycle log |
| [orchestrator/graceful-shutdown.md](orchestrator/graceful-shutdown.md) | Ordered shutdown with session summarization |
| [orchestrator/inter-component-communication.md](orchestrator/inter-component-communication.md) | Event publish and route via orchestrator |

**Platform support:** Launch entry point and process model defer to [platform-support.md](platform-support.md).

---

*This spec is a living document. No implementation begins without user approval.*
