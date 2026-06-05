# Brain Agent — C.O.B.R.A.

**Component:** Brain (+ Seed Document / personality)
**Phase:** 2 (parallel with MCP, Tools)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/brain]]
- `specs/brain/` — all files:
  - `brain-overview.md`, `input-mode-layer.md`, `model-layer.md`, `router.md`
  - `reasoning.md`, `sequential-execution-pipeline.md`, `memory-architecture.md`
  - `session-summarizer.md`, `wiki-operations.md`, `verification-pipeline.md`
  - `personality-model.md`, `proactivity-engine.md`, `context-awareness.md`
  - `failure-handling.md`, `privacy.md`, `implementation-plan.md`
- [[specs/seed-document]] and `specs/seed-document/` — the personality interview + living-document model that feeds `personality-model.md`. (Assigned to Brain by the Lead Developer so personality logic lives with the component that uses it.)

You own every section in these files. No section is shared with another agent.

## 2. Builds
- Input Mode Layer (voice + text normalization — `input-mode-layer.md`)
- Model Layer (LM Studio OpenAI-compatible client, model-agnostic — `model-layer.md`)
- Router (rule-based fast path + LLM classification for ambiguous cases — `router.md`)
- Think-first reasoning: plan before execute (`reasoning.md`)
- Sequential Execution Pipeline P1–P6: memory → tools → verification → personality → synthesis (`sequential-execution-pipeline.md`)
- Memory architecture: raw logs, wiki, ChromaDB vector index (`memory-architecture.md`)
- Session summarizer: chunked, topic-shift first, meta-summary (`session-summarizer.md`)
- Wiki operations: ingest, query, lint (`wiki-operations.md`)
- Verification pipeline: 2-source minimum, Claude API → Copilot → MCP (`verification-pipeline.md`)
- Personality model: seed document → structured interviews → behavioral logging (`personality-model.md`, `specs/seed-document/`)
- Proactivity engine: event-driven, dormant until "conversation complete" (`proactivity-engine.md`)
- Failure handling: "I don't know, here's where I'd look" (`failure-handling.md`)
- Privacy hard-rule enforcement on every outbound call (`privacy.md`)

## 3. Exposes to Other Agents
- **`process_input(text)`** → response event stream
- **Session events** for the Orchestrator
- **Pipeline step events** for the Chat UI (consumed via the WebSocket push and the event bus)

## 4. Depends On
- **[[config-agent]]** — model + memory + verification settings via Config reader API
- **[[mcp-agent]]** — `call_mcp(capability, sanitized_query)` for retrieval and verification
- **[[tools-agent]]** — Tool execution API during pipeline step P2
- **[[security-agent]]** — outbound audit logging for every external call

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess pipeline ordering or verification rules.
- Only rely on contracts the Lead Developer has confirmed in writing.
- `process_input` and the pipeline-step event schema are shared contracts; coordinate changes through the Lead Developer.

## 6. Review Checklist (Lead Developer gate)
- [ ] Input mode layer normalizes both voice and text input
- [ ] Model layer is model-agnostic against LM Studio's OpenAI-compatible API
- [ ] Router uses rule-based fast path, falls back to LLM classification on ambiguity
- [ ] Think-first reasoning plans before executing
- [ ] Pipeline P1–P6 implemented in order with no skipped steps
- [ ] Memory: raw logs + wiki + ChromaDB index all wired
- [ ] Session summarizer: topic-shift-first chunking + meta-summary
- [ ] Wiki ingest/query/lint operations functional
- [ ] Verification: 2-source minimum enforced, source order Claude → Copilot → MCP
- [ ] Personality model built from seed document + interviews + behavioral logging
- [ ] Proactivity engine dormant until "conversation complete"
- [ ] Failure handling returns "I don't know, here's where I'd look"
- [ ] **Privacy hard rule:** external APIs get topic only, never personal data
- [ ] `process_input` + event schemas match Voice, Chat UI, Orchestrator expectations
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Input mode layer | Not started |
| Model layer | Not started |
| Router | Not started |
| Reasoning | Not started |
| Sequential pipeline P1–P6 | Not started |
| Memory architecture | Not started |
| Session summarizer | Not started |
| Wiki operations | Not started |
| Verification pipeline | Not started |
| Personality model + seed document | Not started |
| Proactivity engine | Not started |
| Failure handling | Not started |
| Privacy enforcement | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[mcp-agent]] · [[tools-agent]] · [[security-agent]]
- Consumers: [[voice-agent]] · [[chat-ui-agent]] · [[orchestrator-agent]]
