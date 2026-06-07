# Tools Agent — C.O.B.R.A.

**Component:** Tools
**Phase:** 2 (parallel with Brain, MCP)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/tools]]
- `specs/tools/` — all files:
  - `tools-overview.md`, `tool-set.md`, `approval-model.md`
  - `tool-chaining.md`, `failure-handling.md`, `sandboxing.md`
  - `tool-memory.md`, `extensibility.md`, `execution-flow.md`
  - `privacy.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- Built-in tool set: Web Search, Code Execution, File Management, App Control, Calendar, Communication (draft-only), System Control (`tool-set.md`)
- Approval model: read-only auto, destructive requires approval, code always shows first, communication always draft (`approval-model.md`)
- Tool chaining: auto-chain read-only, pause on destructive (`tool-chaining.md`)
- Retry on failure: once automatically, then report to user (`failure-handling.md`)
- Sandbox environment: default on, per-session override (`sandboxing.md`)
- Tool memory wiki log (`tool-memory.md`)
- Extensibility: guided new-tool flow — describe → clarify → propose → approve → build → register (`extensibility.md`)

## 3. Exposes to Other Agents
- **Tool execution API** — called by the Brain during pipeline step P2. Executes a tool under the approval model and returns a result or an approval-required event.

## 4. Depends On
- **[[config-agent]]** — tool + sandbox settings via Config reader API
- **[[mcp-agent]]** — `call_mcp` for capabilities backed by MCP servers
- **[[brain-agent]]** — for new-tool registration during the extensibility flow
- **[[security-agent]]** — outbound audit logging for tools that make external calls

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess approval or sandbox behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- The Tool execution API contract is shared with Brain; coordinate changes through the Lead Developer.

## 6. Review Checklist (Lead Developer gate)
- [ ] All seven built-in tools implemented
- [ ] Approval model: read-only auto; destructive requires approval; code shows first; communication is draft-only
- [ ] Tool chaining auto-chains read-only and pauses on destructive
- [ ] Retry-once-then-report behavior matches spec
- [ ] Sandbox default-on with per-session override
- [ ] Tool memory logged to wiki
- [ ] Extensibility flow follows describe→clarify→propose→approve→build→register
- [ ] **Privacy:** outbound tool calls sanitized; no personal data leaks (`tools/privacy.md`)
- [ ] Tool execution API contract matches Brain expectations
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Tool set (7 tools) | Implemented — system_control macOS volume/brightness/wifi |
| Approval model | Implemented (default_operation alignment fixed) |
| Tool chaining | Implemented |
| Failure/retry | Implemented |
| Sandboxing | Implemented — session override wired from Brain |
| Tool memory | Implemented — wiki `tools-log.md` + JSONL backup |
| Extensibility flow | register_tool implemented; E1–E5 design flow in extensibility.handle |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[mcp-agent]] · [[brain-agent]] · [[security-agent]]
