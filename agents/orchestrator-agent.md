# Orchestrator Agent — C.O.B.R.A.

**Component:** Orchestrator
**Phase:** 4 (wires everything together last)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/orchestrator]]
- `specs/orchestrator/` — all files:
  - `orchestrator-overview.md`, `component-registry.md`, `startup-phases.md`
  - `health-monitoring.md`, `failure-response.md`, `lifecycle-logging.md`
  - `graceful-shutdown.md`, `inter-component-communication.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- Component registry with dependency graph (`component-registry.md`)
- Phased parallel startup: Phase 1 → 2 → 3 → 4, LM Studio gate before Phase 3 (`startup-phases.md`)
- Continuous health monitoring: ping each component at the configured interval (`health-monitoring.md`)
- User-driven failure response: restart component / ignore / restart all — never silent retry (`failure-response.md`)
- Individual component restart with dependent pause/resume
- Lifecycle log → `~/.cobra/logs/orchestrator.log` (`lifecycle-logging.md`)
- Graceful shutdown sequence: reverse startup order, session summarization before brain stops (`graceful-shutdown.md`)
- Event bus: components publish → Orchestrator routes → subscribers, e.g. pipeline step → Chat UI (`inter-component-communication.md`)

## 3. Exposes to Other Agents
- **The event bus** that all other agents use to communicate (publish/subscribe).

## 4. Depends On
- **All components** — the Orchestrator wires them together last. Startup order must match the dependency graph in [[AGENTS]] §5.

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess startup ordering or failure behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- The event bus is the shared backbone for every contract; any change to its schema must be re-broadcast by the Lead Developer to all agents.

## 6. Review Checklist (Lead Developer gate)
- [ ] Component registry encodes the full dependency graph
- [ ] Startup runs phases 1→2→3→4 in parallel within each phase
- [ ] LM Studio gate passes before Phase 3 begins
- [ ] Health monitoring pings each component at the configured interval
- [ ] Failure response is user-driven (restart / ignore / restart all) — never silent retry
- [ ] Individual restart pauses and resumes dependents correctly
- [ ] Lifecycle log written to `~/.cobra/logs/orchestrator.log`
- [ ] Graceful shutdown reverses startup order; session summarized before brain stops
- [ ] Event bus routes publishers to correct subscribers (e.g. pipeline step → Chat UI)
- [ ] All consumed interfaces match each component's exposed contract
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Component registry | Not started |
| Startup phases | Not started |
| Health monitoring | Not started |
| Failure response | Not started |
| Lifecycle logging | Not started |
| Graceful shutdown | Not started |
| Event bus | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[security-agent]] · [[mcp-agent]] · [[brain-agent]] · [[tools-agent]] · [[voice-agent]] · [[chat-ui-agent]]
