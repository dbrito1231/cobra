# Minimum Viable Seed

Readiness gate — when the personality model becomes active vs. prompts to continue.

## Source Mapping

| Source | Reference |
|--------|-----------|
| seed-document.md | Implied readiness (Overview; open item on minimum stages) |
| seed-document-flow.mermaid | `MVP` subgraph `MV1`–`MV3` |

## Responsibilities

After each `I12` store dimension:

- `MV1` — Stages 1–4 complete?
  - **Yes** → `MV2` C.O.B.R.A. personality model active
  - **No** → `MV3` C.O.B.R.A. prompts to complete remaining stages → `STAGES`

Aligns with [purpose.md](purpose.md) bootstrap goal and [specs/brain/personality-model.md](../brain/personality-model.md).

Parent open items owned here:

- Minimum number of stages before C.O.B.R.A. is ready to use
- How often to prompt for remaining stages

## Inputs / Outputs

| Direction | Content |
|-----------|---------|
| **In** | Completed stage count |
| **Out** | Personality active flag; continuation prompts |

## Flow

```mermaid
flowchart TD
    I12[Store dimension] --> MV1{Stages 1-4 complete?}
    MV1 -->|Yes| MV2[Personality model active]
    MV1 -->|No| MV3[Prompt complete remaining] --> STAGES[Resume stages]
```

## Rules and Constraints

- Stages 1–4 map to [priority-dimensions.md](priority-dimensions.md).
- Stage 5 required for first-run hard gate (full profile before operational use).
- **MVP minimum:** Stages 1–4 (`S1`–`S4`) activate the personality model (`MV2`).
- **First-run hard gate:** Stages 1–5 (`S1`–`S5`) must all be stored before C.O.B.R.A. is fully operational ([specs/onboarding/first-run-sequence.md](../onboarding/first-run-sequence.md)).
- **Pre-MVP gate:** First launch requires the seed interview after voice enrollment; one dimension per session ([interview-approach.md](interview-approach.md)).
- **Post-gate MV3:** After operational, optional refresh prompts for incomplete dimensions via PE2.

## Open Items

_None — resolved in implementation._

## Cross-References

- [purpose.md](purpose.md)
- [interview-stages.md](interview-stages.md)
- [specs/brain/personality-model.md](../brain/personality-model.md)
