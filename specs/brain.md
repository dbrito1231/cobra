# C.O.B.R.A. Brain — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 2.0  
**Last Updated:** 2026-05-31  
**Owner:** Damian  

---

## Overview

The brain is the core reasoning and decision-making component of C.O.B.R.A. It is responsible for processing input (voice or text), retrieving context, reasoning internally before acting, routing to the correct execution path, and ensuring every response reflects the user's personality and privacy requirements. All processing is local-first. No personal data leaves the system without explicit user approval.

---

## 0. Input Mode Layer

C.O.B.R.A. supports voice and text input simultaneously. The user may switch freely between them at any point within a session.

### 0.1 Voice Input (Whisper)
- Audio is transcribed via Whisper before entering the pipeline
- If transcription confidence is low, C.O.B.R.A. asks the user to repeat or confirm what it heard before proceeding
- Audio is never stored — only the transcription is kept
- Mood inference for voice uses speech patterns (pace, pauses) — not transcribed text length
- Transcription errors and artifacts are handled gracefully before reaching the router

### 0.2 Text Input
- Text enters the pipeline directly with no pre-processing step

### 0.3 Shared Behavior
- Both input modes produce clean text that enters the router identically
- Voice and text can be mixed freely within the same session

---

## 1. Model Layer

- C.O.B.R.A. is **model-agnostic** — the underlying LLM can be swapped without changing any code
- LM Studio exposes an OpenAI-compatible REST API; all model calls go through this interface
- Model selection and configuration are handled via environment/config only — never hardcoded
- Failure mode: if LM Studio is unreachable or the model is loading, C.O.B.R.A. notifies the user immediately and waits — it does not silently fail

---

## 2. Reasoning

- C.O.B.R.A. uses a **think-first approach** — internal reasoning occurs before the pipeline executes
- Reasoning runs immediately after the router assigns a path, before any retrieval or tool use
- Reasoning produces a plan: what to retrieve, whether tools are needed, whether a correction may be warranted, and how to frame the response
- The reasoning process is silent — the user only sees the final output
- Think of reasoning as the blueprint; the pipeline builds from it

---

## 3. Router

The router is the first layer that processes every incoming message after the Input Mode Layer. It classifies intent and determines the execution path.

### 3.1 Classification Strategy
- **Rule-based** for obvious cases (greetings, simple factual questions, small talk)
- **LLM-based** for ambiguous cases where rules are insufficient
- Hybrid approach prioritizes speed for clear cases, accuracy for complex ones

### 3.2 Priority Order (Sequential)
Execution is sequential — thoroughness over speed. Each step completes before the next begins.

1. **Memory retrieval** — check the wiki and vector DB for what C.O.B.R.A. already knows
2. **Tool execution** — if memory alone cannot answer, retrieve external data
3. **Verification pipeline** — triggered only when C.O.B.R.A. is about to correct the user
4. **Personality mirror** — every response is filtered through the user's personality before output
5. **Response synthesis** — assembles the final answer from all pipeline outputs. This runs on every path. True fallback (failure handling) is a separate branch.

### 3.3 Uncertainty Handling
- When the router cannot confidently classify intent, it **asks for clarification**
- Clarification is presented as **2-3 options plus a custom response input**
- C.O.B.R.A. never silently guesses

### 3.4 Pattern Learning
- The router learns classification patterns over time
- Repeated query types from the user improve routing accuracy automatically
- Pattern memory persists across sessions

### 3.5 Data Privacy — Hard Rule
- **No personal data leaves the system without explicit user approval**
- Every outbound request is screened before sending
- If a request requires sharing personal context externally, C.O.B.R.A. stops, explains exactly what it wants to share and why, and waits for approval
- **Denied = nothing sent, no exceptions**
- **Outbound query sanitization:** External APIs receive the topic only — never the person. Personal context is stripped from all outbound queries before transmission. Fresh topic-only queries are constructed from scratch — raw log content is never bundled into outbound requests.
- Example: "How does late night screen time affect sleep?" ✅ | "Damian codes late at night and has sleep issues..." ❌

---

## 4. Memory Architecture

C.O.B.R.A.'s memory uses three layers working together: raw logs, a structured wiki, and a vector search index.

### 4.1 Layer 1 — Raw Conversation Logs
- Immutable record of all conversations
- C.O.B.R.A. reads from them, never modifies them
- Source of truth for all summarization and wiki ingestion
- Kept forever — no automatic expiry
- Never passed raw to external APIs

### 4.2 Layer 2 — The Wiki (LLM-Maintained)
C.O.B.R.A. maintains a persistent, human-readable wiki of markdown files. Knowledge is compiled and integrated at ingestion time — not re-derived at every query.

**Wiki pages:**
- **You** — living page about the user: personality, values, communication style, behavioral patterns
- **Preferences** — evolving record of user preferences with timestamps. Conflicting preferences are kept as a preference evolution trail ("used to prefer X, now prefers Y") — never overwritten
- **Verified Facts** — facts confirmed by the verification pipeline, stored with citations
- **Topics** — pages on subjects discussed frequently (e.g. Bitcoin, the C.O.B.R.A. project)
- **Decisions** — important decisions made by the user with reasoning captured
- **Non-findings** — facts checked but unverified. Each entry has a 30-day TTL. After expiry, the topic is treated as unchecked and re-queried if it comes up again

**Wiki operations:**
- **Ingest** — runs automatically at end of each session. C.O.B.R.A. reads the session summary and updates all relevant wiki pages. A single session may touch multiple pages.
- **Query** — C.O.B.R.A. reads `index.md` first to locate relevant pages, then drills into them. Useful answers and analyses produced during conversation are automatically filed as new wiki pages — not lost in chat history.
- **Lint** — runs daily. C.O.B.R.A. health-checks the wiki: flags contradictions between pages, catches stale claims, identifies orphaned pages, and surfaces gaps worth investigating.

**Wiki schema:**
- A schema document defines page formats, naming conventions, cross-referencing rules, and what qualifies as a "useful answer" worth filing
- The schema evolves over time — C.O.B.R.A. may suggest improvements as the wiki grows; user approves all schema changes

**Navigation files (human-readable):**
- `index.md` — full catalog of all wiki pages with one-line summaries, organized by category
- `log.md` — chronological append-only record of every ingest, query, and lint pass

### 4.3 Layer 3 — Vector DB (Semantic Search)
- Embeddings of all wiki pages stored in a local vector database (e.g. ChromaDB)
- Powers fast semantic retrieval during pipeline execution
- Updated automatically whenever wiki pages are created or modified
- All data is **fully local** — nothing is stored externally

### 4.4 Summarization Strategy
- Raw conversations are summarized by C.O.B.R.A. at the end of each session using a chunked approach:
  - Sessions are split by topic shift first; fixed exchange count is used as a fallback if no topic shift is detected
  - Each segment is summarized independently
  - A meta-summary is generated from all segment summaries
  - Both segment summaries and meta-summary are stored
- The meta-summary drives wiki ingest for that session

### 4.5 Memory Retrieval
- Memory retrieval is the first step in every pipeline execution (after reasoning)
- C.O.B.R.A. reads `index.md`, identifies relevant wiki pages, retrieves them, and injects their content into context
- Vector search is used for semantic similarity when index lookup alone is insufficient

---

## 5. Personality

### 5.1 Goal
C.O.B.R.A. mimics the user's personality exactly — in all contexts (professional, casual, personal). The personality model lives in the wiki as the "You" page and is updated continuously.

### 5.2 Data Collection Strategy (Three-Layer Approach)
1. **Seed document** — a structured document capturing the user's communication style, values, decision-making patterns, humor, and hard preferences. Created collaboratively with Claude before first use.
2. **Structured interviews** — ongoing questions C.O.B.R.A. asks the user over time to deepen personality understanding: tone, beliefs, pet peeves, how they treat people in different contexts.
3. **Behavioral logging** — every interaction with C.O.B.R.A. becomes training data. The "You" wiki page improves continuously as new patterns are observed.

### 5.3 Personality Dimensions Captured
- Communication style and tone
- Decision-making patterns and how tradeoffs are weighed
- Core values and beliefs
- Pet peeves and hard nos
- Context-specific behavior (professional vs. casual vs. close relationships)
- Humor style
- How the user handles being wrong

### 5.4 Agreement and Correction Rules
- C.O.B.R.A. **agrees with the user by default**
- The correction trigger fires when:
  - C.O.B.R.A.'s internal reasoning identifies a statement as a verifiable factual claim (auto-detection)
  - The user explicitly requests a fact check at any time (manual trigger)
- C.O.B.R.A. may **correct the user only when** the verification pipeline returns at minimum 2 independent sources in agreement
- If sources conflict → C.O.B.R.A. surfaces the conflict to the user with both sides and lets the user decide
- If fewer than 2 sources agree → correction is suppressed regardless of confidence
- Hallucinated corrections are never acceptable under any circumstances
- Verified facts are stored in the wiki's Verified Facts page

---

## 6. Verification Pipeline

Triggered when C.O.B.R.A.'s reasoning identifies a verifiable factual claim or the user manually requests a fact check.

### 6.1 Flow
1. C.O.B.R.A. forms a potential correction internally (via reasoning)
2. Constructs a sanitized, topic-only query — no personal context included
3. Queries sources sequentially: Claude API → Copilot API → MCP servers
4. Minimum 2 independent sources must agree before a correction is issued
5. If sources conflict → surface conflict to user with both sides
6. If fewer than 2 sources agree → correction suppressed
7. If evidence found → store as verified fact in wiki with citation (permanent)
8. If no evidence found → store as non-finding with 30-day TTL

### 6.2 Source Timeout
- Each external API call has a defined timeout
- If a source times out → treated as "not found" for that source, pipeline continues to next source
- User is not notified of individual timeouts unless all sources fail

### 6.3 Query Sanitization
- All queries sent to external APIs are sanitized per the data privacy hard rule
- Raw log content is never bundled into verification queries
- Fresh topic-only queries are always constructed from scratch

---

## 7. Proactivity

C.O.B.R.A. is observant but patient — it notices things, queues them, and speaks only at the right moment.

### 7.1 Triggers
C.O.B.R.A. queues a proactive item when it detects:
- A **pattern** noticed over time ("You've asked about X three times this week")
- An **unfinished intention** ("You said last month you wanted to do Y — you haven't yet")
- A **contradiction** between something said now vs. something said before
- A **time-based gap** ("It's been 3 weeks since you reviewed Z")

### 7.2 Input Sources
- **Session buffer** — a lightweight buffer of completed exchanges within the current session. Feeds the proactivity engine in real time for intra-session pattern detection. Cleared at session end after summarization.
- **Wiki + vector DB** — cross-session pattern detection. C.O.B.R.A. monitors long-term memory for triggers between sessions.

### 7.3 Surfacing Behavior
- C.O.B.R.A. uses an **event-driven trigger** — the Proactivity Engine is dormant until it receives a "conversation complete" event fired by Response Synthesis
- On receiving the event, it checks if there are queued items and whether there is silence
- If both conditions are met → surfaces the top priority item
- If silence has not yet occurred → returns to dormant and waits for the next "conversation complete" event
- Items are surfaced **one at a time**, most important first
- C.O.B.R.A. also surfaces proactive items **when explicitly asked** ("anything I should know?")
- C.O.B.R.A. never interrupts mid-conversation and never polls continuously

---

## 8. Context Awareness

Context is packaged into a **shared state object** at the start of every pipeline run. Every pipeline step reads from this shared state. No step may modify it — only the user or C.O.B.R.A.'s auto-detection can update it.

### 8.1 Time and Date
- C.O.B.R.A. always has access to the current time and date
- Used for reminders, pattern detection, and episodic memory references

### 8.2 Current Task
- The user explicitly tells C.O.B.R.A. what they are working on at session start
- C.O.B.R.A. does not assume or carry over task context from previous sessions
- If no task is declared, C.O.B.R.A. waits — it does not ask
- Context auto-updates mid-session if C.O.B.R.A. detects a clear topic shift
- Explicit user declarations always take priority over auto-detected context

### 8.3 Mood and Energy Inference
- C.O.B.R.A. infers the user's current mood and energy from communication patterns
- For text: message length, complexity, and tone are used as signals
- For voice: speech pace and pauses are used as signals — not transcribed text length
- Short/clipped → C.O.B.R.A. assumes busy/stressed → adjusts to concise, direct responses
- Long/exploratory → C.O.B.R.A. assumes relaxed → adjusts to more conversational responses
- The user can declare mood explicitly at session start alongside task declaration
- If signals are unclear, C.O.B.R.A. asks once early in the session
- Mood inferences are logged and tracked over time to improve accuracy for this specific user
- This adjustment happens silently — explicit user declarations always override inference

---

## 9. Failure Handling

When C.O.B.R.A. cannot answer something and external verification also fails:

- C.O.B.R.A. responds: **"I don't know, but here's where I'd look"**
- It never fabricates an answer to fill the gap
- It provides actionable next steps for the user to find the answer themselves

---

## 10. Privacy — Master Rule

> **External APIs get the topic, never the person.**

This rule applies to every component of the brain without exception.

- Behavioral logs are used in full internally for personalization
- Raw log content is never passed to external APIs — fresh topic-only queries are always constructed from scratch
- Every outbound request is screened before sending
- Personal data only leaves the system with explicit, per-request user approval. Denied = nothing sent.
- The user can trigger a full reset at any time — wipes behavioral logs, wiki, and personality model

---

## 11. Open Items

- [ ] Seed document — to be created collaboratively (structured interview with Claude)
- [ ] Define MCP servers to connect for verification pipeline
- [ ] Define wiki schema document structure and conventions
- [ ] Define confidence threshold for router LLM classification
- [ ] Define what qualifies as a "useful answer" worth auto-filing to wiki
- [ ] Define API timeout thresholds for verification pipeline sources
- [ ] Define context window budget per pipeline step for target local model

---

## Component Specs

Decomposed, implementable specs live in **`specs/brain/`**. The parent document and [brain-flow.mermaid](brain-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [brain/brain-overview.md](brain/brain-overview.md) | Overall brain component index and cross-cutting rules |
| [brain/implementation-plan.md](brain/implementation-plan.md) | Phased implementation plan |
| [brain/input-mode-layer.md](brain/input-mode-layer.md) | Voice and text input normalization |
| [brain/model-layer.md](brain/model-layer.md) | Model-agnostic LLM access (LM Studio) |
| [brain/reasoning.md](brain/reasoning.md) | Internal think-first reasoning |
| [brain/router.md](brain/router.md) | Intent classification and routing |
| [brain/context-awareness.md](brain/context-awareness.md) | Shared context state (time, task, mood) |
| [brain/memory-architecture.md](brain/memory-architecture.md) | Raw logs, wiki, vector DB |
| [brain/session-summarizer.md](brain/session-summarizer.md) | End-of-session summarization |
| [brain/wiki-operations.md](brain/wiki-operations.md) | Wiki ingest, query, lint |
| [brain/sequential-execution-pipeline.md](brain/sequential-execution-pipeline.md) | Sequential Execution Pipeline (`P1`–`P6`) |
| [brain/verification-pipeline.md](brain/verification-pipeline.md) | Verification Pipeline |
| [brain/personality-model.md](brain/personality-model.md) | Personality Model |
| [brain/proactivity-engine.md](brain/proactivity-engine.md) | Proactivity Engine |
| [brain/failure-handling.md](brain/failure-handling.md) | Failure and final response paths |
| [brain/privacy.md](brain/privacy.md) | Privacy hard rule (master) |

---

*This spec is a living document. No implementation begins without user approval.*
