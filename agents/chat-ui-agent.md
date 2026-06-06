# Chat UI Agent — C.O.B.R.A.

**Component:** Chat UI
**Phase:** 3 (parallel with Voice)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/chat-ui]]
- `specs/chat-ui/` — all files:
  - `chat-ui-overview.md`, `application-type.md`, `technology-stack.md`, `theme.md`
  - `top-bar.md`, `chat-panel.md`, `pipeline-indicators.md`
  - `wiki-browser-panel.md`, `status-panel.md`, `search.md`
  - `approval-prompts.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- Python FastAPI/Flask local web server: localhost, port from config (`application-type.md`, `technology-stack.md`)
- Single-page app: HTML/CSS/JS, dark mode only, no toggle (`theme.md`)
- Three-panel layout: Chat Panel (left), Wiki Browser (center), Status Panel (right)
- Top bar: logo, voice indicator (idle/listening/speaking), profile name, search button (`top-bar.md`)
- Chat Panel: message history, inline pipeline indicators, approval cards, proactive item cards (`chat-panel.md`, `pipeline-indicators.md`)
- Wiki Browser: renders `index.md` catalog, markdown page viewer, back navigation, read-only (`wiki-browser-panel.md`)
- Status Panel: live pipeline step, MCP server status, proactive queue count + preview + "Tell me now" (`status-panel.md`)
- WebSocket connection to backend for real-time pipeline step and status updates
- Full-text local search overlay: results-as-you-type, session date + excerpt + jump link (`search.md`)
- Approval prompts: what/why/data + Approve/Deny, C.O.B.R.A. waits (`approval-prompts.md`)

## 3. Exposes to Other Agents
- **WebSocket server** that Brain and Orchestrator push events to (pipeline-step, status, approval, proactive events).

## 4. Depends On
- **[[config-agent]]** — UI port + settings via Config reader API
- **[[brain-agent]]** — `process_input`, pipeline-step events, approval + proactive events
- **[[voice-agent]]** — voice indicator state (idle/listening/speaking)

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess event schemas or layout behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- The WebSocket event-push contract is shared with Brain and Orchestrator; coordinate changes through the Lead Developer.

## 6. Review Checklist (Lead Developer gate)
- [ ] Local web server binds to localhost on the configured port
- [ ] SPA is dark-mode only with no theme toggle
- [ ] Three-panel layout: Chat / Wiki Browser / Status
- [ ] Top bar shows logo, voice indicator states, profile name, search button
- [ ] Chat Panel renders history, inline pipeline indicators, approval cards, proactive cards
- [ ] Wiki Browser renders `index.md` catalog + markdown pages, back nav, read-only
- [ ] Status Panel shows live pipeline step, MCP status, proactive queue + "Tell me now"
- [ ] WebSocket delivers real-time pipeline + status updates
- [ ] Search overlay returns results-as-you-type with date + excerpt + jump link
- [ ] Approval prompts show what/why/data with Approve/Deny and block until answered
- [ ] WebSocket contract matches Brain + Orchestrator expectations
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Web server | Implemented (`src/chat_ui/server.py`, default port 8765) |
| Theme (dark only) | Implemented (`src/chat_ui/static/css/theme.css`) |
| Three-panel layout | Implemented (`src/chat_ui/static/index.html`) |
| Top bar | Implemented |
| Chat panel + indicators | Implemented |
| Wiki browser | Implemented |
| Status panel | Implemented |
| WebSocket | Implemented (`/ws` event contract in `models.py`) |
| Search overlay | Implemented — cross-session jump via `/api/session/{id}/activate` |
| Approval prompts | Implemented — sanitized data_summary, code_preview, draft_content |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[brain-agent]] · [[voice-agent]]
