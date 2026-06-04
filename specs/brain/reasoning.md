# Internal Reasoning

Silent think-first planning before pipeline execution.

## Source Mapping

| Source | Reference |
|--------|-----------|
| brain.md | Section 2 (Reasoning) |
| brain-flow.mermaid | `R` (Internal Reasoning) |

## Responsibilities

- Run **think-first** internal reasoning before the pipeline executes.
- Produce an execution plan covering:
  - What to retrieve
  - Whether tools are needed
  - Whether a correction may be warranted
  - How to frame the response
- Operate silently — user sees only final output.
- Act as the blueprint; the Sequential Execution Pipeline builds from the plan.

## Inputs / Outputs

| Direction | Content |
|-----------|---------|
| **In** | Clean text from Input Mode Layer (`I5` → `R`) |
| **Out** | Execution plan → Shared Context State → Router (`R` → `CONTEXT` → `B`) |

## Flow

```mermaid
flowchart LR
    I5[Clean Text] --> R[Internal Reasoning]
    R --> CONTEXT[Shared Context State]
    CONTEXT --> B[Router]
```

## Rules and Constraints

- Reasoning is silent; no user-visible intermediate reasoning output.
- Plan must inform retrieval, tools, correction eligibility, and response framing.

## Ordering Note (preserve both sources)

- **brain-flow.mermaid:** `I5` → `R` → `CONTEXT` → `B` (reasoning before router).
- **brain.md §2:** “Reasoning runs immediately after the router assigns a path, before any retrieval or tool use.”
- Implementation must reconcile this; both statements are retained until the parent spec is updated.

## Open Items

- [ ] Define context window budget per pipeline step for target local model (brain.md §11)

## Cross-References

- [input-mode-layer.md](input-mode-layer.md)
- [context-awareness.md](context-awareness.md)
- [router.md](router.md)
- [sequential-execution-pipeline.md](sequential-execution-pipeline.md)
- [verification-pipeline.md](verification-pipeline.md) — correction warrant in plan
- [model-layer.md](model-layer.md)
