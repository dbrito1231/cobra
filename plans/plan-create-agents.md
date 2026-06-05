# Plan: Create Agent System for C.O.B.R.A.

**Status:** Pending Approval  
**Created:** 2026-06-05  
**Owner:** Damian  

---

## 1. Purpose

This plan defines how to create a multi-agent development system for the C.O.B.R.A. project. The system consists of a **Lead Developer Agent** and a team of **Subagents**, each responsible for a specific component. The Lead Developer coordinates all work, enforces spec compliance, and keeps specs and code in sync at all times.

**Agent files:** [[AGENTS]] · [[config-agent]] · [[security-agent]] · [[mcp-agent]] · [[brain-agent]] · [[tools-agent]] · [[voice-agent]] · [[chat-ui-agent]] · [[orchestrator-agent]] · [[spec-sync-agent]]

---

## 2. Project Context

C.O.B.R.A. (*Cognitive Optimized Brain for Retrieval and Action*) is a local-first AI assistant. It has **8 major components**, each with its own spec folder under `specs/`:

| Component | Spec Root | Sub-specs |
|---|---|---|
| Brain | `specs/brain.md` | `specs/brain/` (16 files) |
| Chat UI | `specs/chat-ui.md` | `specs/chat-ui/` (12 files) |
| Configuration | `specs/configuration.md` | `specs/configuration/` (12 files) |
| MCP Server Layer | `specs/mcp-server-layer.md` | `specs/mcp-server-layer/` (13 files) |
| Orchestrator | `specs/orchestrator.md` | `specs/orchestrator/` (9 files) |
| Security | `specs/security.md` | `specs/security/` (9 files) |
| Tools | `specs/tools.md` | `specs/tools/` (11 files) |
| Voice | `specs/voice.md` | `specs/voice/` (11 files) |
| Seed Document | `specs/seed-document.md` | `specs/seed-document/` (11 files) |

Every spec is a living document — no implementation begins without Damian's approval.

---

## 3. File Structure to Create

```
cobra/
├── agents/
│   ├── AGENTS.md                  ← Lead Developer (main file)
│   ├── brain-agent.md             ← Brain subagent
│   ├── chat-ui-agent.md           ← Chat UI subagent
│   ├── config-agent.md            ← Configuration subagent
│   ├── mcp-agent.md               ← MCP Server Layer subagent
│   ├── orchestrator-agent.md      ← Orchestrator subagent
│   ├── security-agent.md          ← Security subagent
│   ├── spec-sync-agent.md         ← Spec↔Code Sync subagent
│   ├── tools-agent.md             ← Tools subagent
│   └── voice-agent.md             ← Voice subagent
└── plans/
    └── plan-create-agents.md      ← This file
```

---

## 4. Lead Developer Agent — AGENTS.md

### 4.1 Role
The Lead Developer is the single point of authority for all development decisions on C.O.B.R.A. It reads and maintains deep knowledge of every spec file before any work begins and throughout the project. It never guesses — it either finds the answer in specs or asks Damian.

### 4.2 Responsibilities

**Spec Mastery**
- Read all spec files (`specs/*.md` and all `specs/*/`) before any subagent is dispatched
- Maintain a running spec index so it can answer any subagent question without re-reading
- Detect contradictions between specs and surface them to Damian before implementation

**Task Delegation**
- Dispatch subagents to build components in parallel when dependencies allow
- Follow the Orchestrator's startup phase order as the natural dependency graph:
  - Phase 1 (parallel): Configuration, Security setup
  - Phase 2 (parallel): Brain, MCP Server Layer, Tools
  - Phase 3 (parallel): Voice Layer, Chat UI
  - Orchestrator wires them all together last
- Assign each subagent a clear task with: which specs to implement, what interfaces to expose, and what other components it depends on

**Communication Hub**
- All subagent questions route through the Lead Developer first
- If the Lead Developer can resolve a question from specs → answers immediately
- If the question cannot be resolved from specs → escalates to Damian with context
- Lead Developer broadcasts interface decisions to all affected subagents so nothing breaks in parallel

**Review Gate**
- Every component must pass Lead Developer review before being marked complete
- Review checklist (per component):
  - [ ] All spec requirements implemented (mapped line by line)
  - [ ] No gaps — partial implementations are rejected
  - [ ] Integration points match what other subagents expect
  - [ ] Privacy hard rules enforced (external APIs get topic only, never personal data)
  - [ ] Approval model enforced (destructive actions require user approval)
  - [ ] Logging implemented per spec
  - [ ] Open Items in the spec are noted and flagged to Damian if blocking
- Work is **never** marked complete without passing this review
- Failed reviews are sent back to the subagent with specific line-item deficiencies

**Spec↔Code Sync (New Feature)**
- Monitors both directions of drift between specs and code
- See Section 6 for full detail

**Doubt Resolution**
- The Lead Developer never fabricates solutions for unknowns
- If a subagent has a doubt the specs don't answer → Lead Developer asks Damian
- Questions are batched when possible to avoid interrupting Damian repeatedly
- Damian's answers are recorded and shared with all relevant subagents

### 4.3 What the Lead Developer Must NOT Do
- Second-guess or invent solutions not grounded in specs
- Mark work complete without Lead Developer validation
- Leave spec gaps unfilled — every gap is either resolved or escalated
- Proceed on any ambiguity without Damian's confirmation

---

## 5. Subagent Definitions

Each subagent is responsible for one component. Subagents work in parallel on independent components. They communicate through the Lead Developer, not directly — except for agreed interface contracts that the Lead Developer has broadcast to both parties.

### 5.1 Config Agent (`config-agent.md`)
**Owns:** `specs/configuration.md` + `specs/configuration/`  
**Builds:**
- YAML config file schema and loader
- First-time setup wizard (10-step flow)
- Startup validation (checks V1–V9)
- LM Studio wait-and-retry loop
- Profile system (named profiles, hot switch)
- Hot reload (file watcher + revalidate)
- Backup and restore commands  

**Exposes to other agents:** Config reader API — all components call this to read their settings  
**Depends on:** Nothing — loads first  

---

### 5.2 Security Agent (`security-agent.md`)
**Owns:** `specs/security.md` + `specs/security/`  
**Builds:**
- OS file permission setup for `~/.cobra/` data directories
- Auto-lock timeout (configurable, default disabled)
- Outbound request audit log (`~/.cobra/logs/outbound-audit.log`)
- Network binding (localhost vs. local network)
- Anomaly detection — allowlist + block/alert on unexpected outbound  

**Exposes to other agents:** Outbound audit logging function — all components that make external calls use this  
**Depends on:** Config Agent (reads security config block)  

---

### 5.3 MCP Agent (`mcp-agent.md`)
**Owns:** `specs/mcp-server-layer.md` + `specs/mcp-server-layer/`  
**Builds:**
- MCP server connection manager (parallel connections on startup)
- Live capability registry
- Startup validation per server (reachable, capabilities declared, protocol version)
- Capability-based routing (first-available)
- Per-call user approval flow (stop → explain → wait → approve/deny)
- Mid-session retry and task pause on server down
- Wiki MCP audit log  

**Exposes to other agents:** `call_mcp(capability, sanitized_query)` — Brain and Tools use this  
**Depends on:** Config Agent  

---

### 5.4 Brain Agent (`brain-agent.md`)
**Owns:** `specs/brain.md` + `specs/brain/`  
**Builds:**
- Input Mode Layer (voice + text normalization)
- Model Layer (LM Studio OpenAI-compatible client, model-agnostic)
- Router (rule-based fast path + LLM classification for ambiguous cases)
- Think-first reasoning (plan before execute)
- Sequential Execution Pipeline (P1–P6: memory → tools → verification → personality → synthesis)
- Memory architecture (raw logs, wiki, ChromaDB vector index)
- Session summarizer (chunked, topic-shift first, meta-summary)
- Wiki operations (ingest, query, lint)
- Verification pipeline (2-source minimum, Claude API → Copilot → MCP)
- Personality model (seed document → structured interviews → behavioral logging)
- Proactivity engine (event-driven, dormant until "conversation complete")
- Failure handling ("I don't know, here's where I'd look")
- Privacy hard rule enforcement on every outbound call  

**Exposes to other agents:** `process_input(text)` → response event stream; session events for Orchestrator; pipeline step events for Chat UI  
**Depends on:** Config Agent, MCP Agent  

---

### 5.5 Tools Agent (`tools-agent.md`)
**Owns:** `specs/tools.md` + `specs/tools/`  
**Builds:**
- Built-in tool set: Web Search, Code Execution, File Management, App Control, Calendar, Communication (draft-only), System Control
- Approval model (read-only auto, destructive requires approval, code always shows first, communication always draft)
- Tool chaining (auto chain read-only, pause on destructive)
- Retry on failure (once auto, then report to user)
- Sandbox environment (default on, per-session override)
- Tool memory wiki log
- Extensibility: guided new-tool flow (describe → clarify → propose → approve → build → register)  

**Exposes to other agents:** Tool execution API called by Brain during pipeline P2  
**Depends on:** Config Agent, MCP Agent, Brain Agent (for registration)  

---

### 5.6 Voice Agent (`voice-agent.md`)
**Owns:** `specs/voice.md` + `specs/voice/`  
**Builds:**
- Wake word detection (local, configurable, passive listening)
- Session lifecycle state machine (passive → listening → responding → passive)
- Voice input pipeline: capture → Whisper transcription → confidence check → clean text
- Mood inference from speech patterns (pace, pauses — not text length)
- Voice cloning: guided recording session, local XTTS training, test playback approval
- Voice output: cloned TTS + text simultaneously, speed adaptation by mood
- Interruption queue (finish response, then process queued input)
- Audio privacy: raw audio never written to disk  

**Exposes to other agents:** `transcribed_text` events to Brain Input Mode Layer; voice output subscriber to Brain response events  
**Depends on:** Config Agent, Brain Agent  

---

### 5.7 Chat UI Agent (`chat-ui-agent.md`)
**Owns:** `specs/chat-ui.md` + `specs/chat-ui/`  
**Builds:**
- Python FastAPI/Flask local web server (localhost, port from config)
- Single-page app: HTML/CSS/JS, dark mode only, no toggle
- Three-panel layout: Chat Panel (left), Wiki Browser (center), Status Panel (right)
- Top bar: logo, voice indicator (idle/listening/speaking), profile name, search button
- Chat Panel: message history, inline pipeline indicators, approval cards, proactive item cards
- Wiki Browser: renders `index.md` catalog, markdown page viewer, back navigation, read-only
- Status Panel: live pipeline step, MCP server status, proactive queue count + preview + "Tell me now"
- WebSocket connection to backend for real-time pipeline step and status updates
- Full-text local search overlay (results-as-you-type, session date + excerpt + jump link)
- Approval prompts: what/why/data + Approve/Deny, C.O.B.R.A. waits  

**Exposes to other agents:** WebSocket server that Brain and Orchestrator push events to  
**Depends on:** Config Agent, Brain Agent, Voice Agent  

---

### 5.8 Orchestrator Agent (`orchestrator-agent.md`)
**Owns:** `specs/orchestrator.md` + `specs/orchestrator/`  
**Builds:**
- Component registry with dependency graph
- Phased parallel startup (Phase 1 → 2 → 3 → 4 per spec, LM Studio gate before Phase 3)
- Continuous health monitoring (ping each component at configured interval)
- User-driven failure response (restart component / ignore / restart all — never silent retry)
- Individual component restart with dependent pause/resume
- Lifecycle log (`~/.cobra/logs/orchestrator.log`)
- Graceful shutdown sequence (reverse startup order, session summarization before brain stops)
- Event bus: components publish → Orchestrator routes → subscribers (e.g., pipeline step → Chat UI)  

**Exposes to other agents:** The event bus all other agents use to communicate  
**Depends on:** All components (wires them together last)  

---

### 5.9 Spec Sync Agent (`spec-sync-agent.md`)
**Owns:** Spec↔Code integrity — this is a new agent for the new feature  
**See Section 6 for full detail.**

---

## 6. New Feature: Spec↔Code Sync

This is a new capability not in any existing spec. It must be implemented as part of this agent system.

### 6.1 Problem

Specs and code can drift in two directions:
1. **Spec updated, code not** — Damian updates a spec; code still implements the old behavior
2. **Code updated, spec not** — a subagent or developer changes code without updating the spec

Both are unacceptable. C.O.B.R.A.'s specs are the source of truth. The agent system must enforce this.

### 6.2 Trigger: Damian Notifies of Spec Change

When Damian says "I made changes to spec files":

1. **Lead Developer reads the changed spec files** (git diff or direct comparison)
2. **Lead Developer identifies what changed**: new function, renamed field, replaced protocol, removed behavior, etc.
3. **Lead Developer classifies the change**:
   - **Small/isolated** (e.g., rename a config field, change a timeout value) → Lead Developer implements directly
   - **Large/cross-cutting** (e.g., new pipeline step, table rename that touches multiple files, new approval flow) → Lead Developer dispatches the relevant subagent(s)
4. **Subagents receive a precise change brief**: what spec changed, what exact code to update, what other components are affected
5. **Lead Developer reviews the code change** against the updated spec before marking it complete
6. **Lead Developer confirms to Damian** the change is fully implemented and validated

**Hard rule:** Spec changes are never partially implemented. If a spec change touches 10 files, all 10 are updated before the change is closed.

### 6.3 Trigger: Code Changed Without Spec Update

When a code change is made that has no corresponding spec update:

1. **Spec Sync Agent detects the drift** (compares code behavior/structure to spec claims)
2. **Spec Sync Agent reports to Lead Developer**: which spec is now outdated, what the code does vs. what the spec says
3. **Lead Developer updates the relevant spec files** to accurately reflect what the code does
4. **Lead Developer confirms** specs now match code exactly
5. **Damian is notified** of the spec update so the living document stays accurate

**Hard rule:** Spec files must always accurately describe what the code actually does — not what was originally planned if that plan changed during implementation.

### 6.4 Spec Sync Agent Responsibilities

The Spec Sync Agent monitors drift between specs and code. It is invoked by the Lead Developer, not autonomously. Its job is to:

- Compare a component's implementation against its spec files and identify every gap
- Produce a line-item report: spec claim → code reality → pass/fail
- For code→spec drift: draft updated spec language for Lead Developer to review and apply
- For spec→code drift: produce a precise change brief for the relevant subagent

The Spec Sync Agent **never edits specs or code directly**. It always reports to the Lead Developer.

---

## 7. Subagent Communication Protocol

Subagents communicate through the Lead Developer. The protocol:

1. **Interface contracts are broadcast before parallel work begins.** Before dispatching two agents that share an interface (e.g., Brain Agent and Voice Agent both use the Input Mode Layer), the Lead Developer defines the exact contract (function signatures, event schemas, data shapes) and gives it to both agents in writing.

2. **Questions go to the Lead Developer, not peer agents.** If Brain Agent needs to know what format Voice Agent will deliver transcriptions in, it asks the Lead Developer — who either already knows from the spec or asks Voice Agent and relays the answer.

3. **Blockers are escalated immediately.** If a subagent is blocked (spec is ambiguous, another component's interface is undefined), it must report to the Lead Developer immediately rather than guessing or proceeding with assumptions.

4. **No assumptions about other components.** A subagent may only rely on what has been explicitly confirmed by the Lead Developer.

5. **Integration checkpoints.** When two components that share an interface both claim to be complete, the Lead Developer runs an integration checkpoint — a review where both components' interface implementations are compared to the agreed contract.

---

## 8. Review Gate Protocol

No component is marked complete until it passes the Lead Developer's review. The review is documented, not verbal.

### Review Report Format (per component)

```
Component: [Name]
Spec Version: [version from spec header]
Review Date: [date]

REQUIREMENTS CHECK:
[List every spec requirement with PASS / FAIL / PARTIAL]

INTEGRATION CHECK:
[List every interface this component exposes and verify contract match]

PRIVACY COMPLIANCE:
[Verify all outbound calls are sanitized, all approvals are in place]

OPEN ITEMS:
[List any spec Open Items that were blocking — these must be confirmed with Damian]

VERDICT: PASS / FAIL
[If FAIL: list exactly what must be fixed before re-review]
```

A FAIL verdict means the subagent receives the report and must address every line item before resubmitting. The Lead Developer does not re-review until all listed items are resolved.

---

## 9. Escalation to Damian

The Lead Developer asks Damian when:

- A spec Open Item is blocking implementation (cannot proceed without the answer)
- Two specs contradict each other and the Lead Developer cannot resolve the conflict
- A subagent's question cannot be answered from specs
- A proposed implementation deviates from the spec and needs approval for the deviation
- A code change during development requires a spec update (Damian approves the updated spec before it is written)

Questions are batched where possible. The Lead Developer does not ask the same question twice.

**Damian's answers are binding.** Once Damian answers a question, that answer is recorded in the relevant spec or agent file and treated as authoritative.

---

## 10. Implementation Steps

The following steps will be executed after Damian approves this plan:

### Step 1 — Create agents folder and AGENTS.md
- Create `agents/` directory
- Write `agents/AGENTS.md` (Lead Developer full definition)
- No subagent files yet

### Step 2 — Write subagent files (parallel)
All 9 subagent `.md` files are written in parallel:
- `brain-agent.md`
- `chat-ui-agent.md`
- `config-agent.md`
- `mcp-agent.md`
- `orchestrator-agent.md`
- `security-agent.md`
- `spec-sync-agent.md`
- `tools-agent.md`
- `voice-agent.md`

Each file contains: role, owned specs, responsibilities, what it exposes, what it depends on, communication rules, and review checklist.

### Step 3 — Lead Developer cross-reference check
Lead Developer reads all subagent files and verifies:
- No two agents claim the same responsibility
- All interfaces are defined and matched between consumer and provider
- Dependency order is consistent with Orchestrator startup phases
- Spec Sync Agent's scope covers all components

### Step 4 — Spec Sync Agent validation
Spec Sync Agent reviews all spec files against the agent definitions and confirms every spec section is owned by exactly one subagent with no gaps.

### Step 5 — Damian review
All files presented to Damian. No implementation of C.O.B.R.A. code begins until Damian approves.

---

## 11. Constraints

- **No second-guessing.** Every decision is grounded in a spec citation or a confirmed answer from Damian.
- **No partial implementations.** Every spec requirement is fully implemented or explicitly escalated.
- **No self-declared completion.** Work is complete only when the Lead Developer's review passes.
- **No spec gaps left open.** Every Open Item in every spec is either resolved or flagged to Damian.
- **No code↔spec drift tolerated.** The Spec Sync Agent ensures both directions of drift are caught and corrected immediately.

---

## 12. Approval

This plan requires Damian's explicit approval before any files in `agents/` are created.

> **Damian — please review and confirm you approve this plan before implementation begins.**

Specific questions for Damian before proceeding:

1. Should the `agents/` folder live at the root of `cobra/` (same level as `specs/`) or somewhere else?
2. Should each subagent `.md` file include a "current status" section that tracks which spec requirements are implemented vs. pending? This would make it easier to track progress across sessions.
3. For the Spec Sync feature: when Damian notifies of spec changes, should the Lead Developer ask for confirmation of exactly which files changed, or should it detect changes automatically by reading all spec files and comparing to its last known state?
