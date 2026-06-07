# Seed Document Spec-Sync Audit

**Component:** Seed Document (+ PE1–PE3)  
**Scan Date:** 2026-06-06  
**Direction:** Bidirectional  
**Auditor:** Lead Developer (spec-sync-agent format)

## Executive Summary

| Area | Verdict | Blocks PASS? |
|------|---------|--------------|
| I1–I12 interview flow | PASS | No |
| S1–S5 stages / entry-resume | PARTIAL | Yes (session boundary) |
| MV1–MV3 readiness | PASS | No |
| W1–W7 output format | PARTIAL | Yes (W7 on I12) |
| LV1–LV5 living document | PARTIAL | Yes (W7 on I12) |
| OV1–OV5 override | PASS | No |
| PE1–PE3 personality model | PARTIAL | Yes (PE2) |
| Chat UI seed wiring | PASS | No |
| Bootstrap seed_mode push | PASS | No |

**Interim verdict: FAIL** — three blockers identified below.

---

## Line-Item Findings

### interview-session-flow.md (I1–I12)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| I1–I12 | Full per-stage loop | `src/brain/seed_document.py` | PASS |

### interview-stages.md (A–D, S1–S5)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| A–D | Entry/resume | bootstrap + seed_state.json | PASS |
| S1–S5 | Stage sequence | InterviewStage enum | PASS |

### minimum-viable-seed.md (MV1–MV3)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| MV1 | S1–S4 complete | `MVP_STAGES`, `mvp_complete()` | PASS |
| MV2 | Personality active | `personality_ready()` after MVP | PASS |
| MV3 | Prompt remaining | `should_prompt_mv3`, proactivity | PASS |

### output-format.md (W1–W7)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| W1–W6 | you.md sections | WikiStore + write_section | PASS |
| W7 | Version history | you-history.md on override/session only | **PARTIAL** |

### living-document.md (LV1–LV5)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| LV1–LV4 | Session updates + reconcile | `living_document.py` | PASS |
| LV5 | History on all writes | Missing on I12 seed store | **PARTIAL** |

### user-override.md (OV1–OV5)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| OV1–OV5 | Chat override authoritative | `service.py` Override command | PASS |

### interview-approach.md

| Requirement | Code reality | Verdict |
|-------------|--------------|---------|
| One dimension per session | Auto-advances after store | **FAIL** |

### personality-model.md (PE1–PE3)

| ID | Spec claim | Code reality | Verdict |
|----|------------|--------------|---------|
| PE1 | Seed document | Full S1–S5 interview | PASS |
| PE2 | Ongoing structured interviews | Not implemented beyond S5 | **FAIL** |
| PE3 | Behavioral logging | ingest_session + log_behavior | PASS |

---

## code→spec Drift (implemented; specs stale)

1. MVP = stages 1–4 — open items in `minimum-viable-seed.md`, overview
2. MV3 frequency = once per calendar day — open items in `interview-stages.md`
3. Question sets S1–S5 — open items in `priority-dimensions.md`, `additional-dimensions.md`
4. Export backup — `GET /api/seed/export` — open item in `output-format.md`
5. Override chat syntax — document in `user-override.md`
6. PE1 open item in `personality-model.md` — obsolete

---

## spec→code Gaps (blocking)

1. **W7/LV5 on I12 store** — interview writes skip version history
2. **One dimension per session** — `_handle_summary_review` auto-opens next stage
3. **PE2** — no follow-up refresh interviews after initial profile

---

## Proposed Actions

**spec→code:** Fix W7 on store; enforce session boundary; implement PE2 refresh interviews.  
**code→spec:** Close resolved open items in Phase 3 spec batch (Damian-approved).

---

## Damian Decisions (2026-06-06)

1. **One dimension per session:** Enforce — end session after each stage store; resume via banner/command.
2. **PE2 scope:** Build follow-up refresh interviews beyond Stage 5 before PASS.
