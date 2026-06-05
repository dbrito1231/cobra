# C.O.B.R.A. Seed Document — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Seed Document is the foundational personality profile for C.O.B.R.A. It captures who the user is — how they communicate, how they make decisions, what they value, and how they behave — so C.O.B.R.A. can mirror the user's personality accurately from day one. It is built through a staged interview process and lives as a wiki page that C.O.B.R.A. updates automatically over time.

---

## 1. Purpose

The Seed Document serves three functions:

1. **Bootstraps the personality model** — gives C.O.B.R.A. enough signal to respond in the user's voice before behavioral logging has accumulated sufficient data
2. **Grounds the wiki You page** — the seed document becomes the initial content of the "You" wiki page
3. **Sets the baseline** — all future personality updates are measured against this document as the starting reference

---

## 2. Interview Approach

The interview is conducted in **stages** — a few personality dimensions per session. This avoids fatigue and allows thoughtful, accurate answers rather than rushed ones.

Each stage is a structured conversation where C.O.B.R.A. asks targeted questions, listens to answers, and summarizes what it learned for the user to review and correct before storing.

---

## 3. Priority Dimensions — Captured First

The first interview stages focus on the four highest-priority dimensions:

### Stage 1 — Communication Style and Tone
- How do you naturally write and speak? (formal, casual, direct, verbose)
- How do you open conversations vs. close them?
- Do you prefer short answers or thorough explanations?
- How do you adjust your tone for different audiences?
- What phrases or words do you use often?
- What communication habits do you dislike in others?

### Stage 2 — Decision-Making Patterns
- How do you approach a big decision?
- Do you gather all information first, or decide with what you have?
- How do you handle uncertainty?
- Do you prefer reversible or irreversible decisions and why?
- How do you weigh logic vs. intuition?
- How do you handle being wrong about a decision?

### Stage 3 — Values and Beliefs
- What are your non-negotiables — things you will never compromise on?
- What do you stand for professionally? Personally?
- What do you believe that most people disagree with?
- How do you treat people who are rude to you?
- What makes someone earn your trust?
- What causes you to lose trust in someone?

### Stage 4 — Humor and Personality Quirks
- How would you describe your sense of humor?
- What do you find genuinely funny vs. annoying in humor?
- What are your biggest pet peeves?
- How do you act when you're stressed vs. when you're relaxed?
- How do you handle conflict with people you respect?
- What do people consistently misunderstand about you?

---

## 4. Additional Dimensions — Captured in Later Stages

After the four priority stages, subsequent sessions capture:

- Context-specific behavior (professional vs. casual vs. close relationships)
- How you like to receive feedback
- Your relationship with failure
- Your energy patterns (when you're most productive, what drains you)
- Your opinions on topics you frequently discuss
- Habits and routines that define your day

---

## 5. Living Document — Automatic Updates

The seed document is not static. C.O.B.R.A. updates it automatically as it learns more about the user through interactions:

- New behavioral patterns observed during sessions update the relevant dimensions
- Contradictions between current behavior and the seed document are noted and reconciled
- The "You" wiki page version history tracks all changes over time
- The user can review the current seed document at any time in the wiki browser
- The user can manually correct or override any section at any time

---

## 6. Output Format

The seed document is stored as the "You" wiki page at `~/.cobra/wiki/you.md` using the following structure:

```markdown
# You
*Last updated: [date]*

## Communication Style
[C.O.B.R.A.-generated summary from Stage 1 interview]

## Decision-Making
[C.O.B.R.A.-generated summary from Stage 2 interview]

## Values and Beliefs
[C.O.B.R.A.-generated summary from Stage 3 interview]

## Humor and Personality
[C.O.B.R.A.-generated summary from Stage 4 interview]

## Context-Specific Behavior
[Added in later stages]

## Observed Patterns
[Auto-populated from behavioral logging over time]
```

---

## 7. Interview Session Flow

Each stage follows this structure:

1. C.O.B.R.A. introduces the dimension being covered
2. C.O.B.R.A. asks questions one at a time — never more than one question per exchange
3. User answers in their own words
4. C.O.B.R.A. reflects back what it understood and asks for confirmation
5. User corrects or confirms
6. At end of stage, C.O.B.R.A. writes a summary of the dimension
7. User reviews the summary and approves or edits before it is stored

---

## Open Items

- [ ] Define the exact question set for each stage (to be done collaboratively with Claude)
- [ ] Define minimum viable seed document — what is the minimum number of stages before C.O.B.R.A. is ready to use
- [ ] Define how often C.O.B.R.A. prompts the user to complete remaining stages
- [ ] Define whether the seed document can be exported for backup

---

## Component Specs

Decomposed, implementable specs live in **`specs/seed-document/`**. The parent document and [seed-document-flow.mermaid](seed-document-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [seed-document/seed-document-overview.md](seed-document/seed-document-overview.md) | Overall seed document index and cross-cutting rules |
| [seed-document/implementation-plan.md](seed-document/implementation-plan.md) | Phased implementation plan |
| [seed-document/purpose.md](seed-document/purpose.md) | Three functions of the seed document |
| [seed-document/interview-approach.md](seed-document/interview-approach.md) | Staged interview approach |
| [seed-document/priority-dimensions.md](seed-document/priority-dimensions.md) | Stages 1–4 questions and dimensions |
| [seed-document/additional-dimensions.md](seed-document/additional-dimensions.md) | Stage 5+ additional dimensions |
| [seed-document/interview-stages.md](seed-document/interview-stages.md) | Entry, resume, and stage sequencing |
| [seed-document/interview-session-flow.md](seed-document/interview-session-flow.md) | Per-stage interview conversation flow |
| [seed-document/output-format.md](seed-document/output-format.md) | You wiki page structure and path |
| [seed-document/living-document.md](seed-document/living-document.md) | Automatic updates and reconciliation |
| [seed-document/user-override.md](seed-document/user-override.md) | Manual authoritative overrides |
| [seed-document/minimum-viable-seed.md](seed-document/minimum-viable-seed.md) | MVP readiness gate for personality model |

---

*This spec is a living document. No implementation begins without user approval.*
