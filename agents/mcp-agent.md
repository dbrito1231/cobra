# MCP Agent — C.O.B.R.A.

**Component:** MCP Server Layer
**Phase:** 2 (parallel with Brain, Tools)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/mcp-server-layer]]
- `specs/mcp-server-layer/` — all files:
  - `mcp-server-layer-overview.md`, `config-structure.md`, `discovery.md`
  - `multi-server-support.md`, `live-registry.md`, `startup-validation.md`
  - `routing-logic.md`, `approval-model.md`, `execution-flow.md`
  - `server-down-mid-session.md`, `privacy.md`, `logging.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- MCP server connection manager (parallel connections on startup — `multi-server-support.md`, `discovery.md`)
- Live capability registry (`live-registry.md`)
- Startup validation per server: reachable, capabilities declared, protocol version (`startup-validation.md`)
- Capability-based routing — first-available (`routing-logic.md`)
- Per-call user approval flow: stop → explain → wait → approve/deny (`approval-model.md`)
- Mid-session retry and task pause on server down (`server-down-mid-session.md`)
- Wiki MCP audit log (`logging.md`)

## 3. Exposes to Other Agents
- **`call_mcp(capability, sanitized_query)`** — Brain and Tools call this. Routes to the first available server for the requested capability and triggers the per-call approval flow. Returns the server result or an approval-required / denied event.

## 4. Depends On
- **[[config-agent]]** — reads MCP config block (`config-structure.md`) via the Config reader API.
- Uses the **[[security-agent]]** outbound audit logging for external MCP calls.

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess routing or approval behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- The `call_mcp` contract is shared with Brain and Tools; any change must be re-broadcast by the Lead Developer.

## 6. Review Checklist (Lead Developer gate)
- [ ] Parallel connection manager connects to all configured servers on startup
- [ ] Live registry reflects current capabilities and updates on server state change
- [ ] Startup validation checks reachability, declared capabilities, protocol version
- [ ] Routing selects first-available server per capability
- [ ] Per-call approval flow: stops, explains, waits, honors approve/deny
- [ ] Server-down mid-session: retry then pause task per spec (never silent failure)
- [ ] Wiki MCP audit log written per `logging.md`
- [ ] Privacy: queries sanitized before leaving the machine (`privacy.md`)
- [ ] `call_mcp` contract matches Brain and Tools expectations
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Connection manager / discovery | Not started |
| Live registry | Not started |
| Startup validation | Not started |
| Routing logic | Not started |
| Approval flow | Not started |
| Server-down handling | Not started |
| MCP audit log | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[security-agent]]
- Consumers: [[brain-agent]] · [[tools-agent]]
