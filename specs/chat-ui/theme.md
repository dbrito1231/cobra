# Theme

Dark-mode-only visual design for the Chat UI.

## Source Mapping

| Source | Reference |
|--------|-----------|
| chat-ui.md | Section 8 (Theme) |
| chat-ui-flow.mermaid | Styling `classDef` only (visual; no functional nodes) |

## Responsibilities

- **Dark mode only** — no light mode, no toggle.
- **Color palette:** dark backgrounds, high contrast text, accent colors for status indicators.
- **Consistent with C.O.B.R.A.'s identity.**

Applies to:

- Three-panel layout ([chat-ui-overview.md](chat-ui-overview.md))
- Top bar, voice indicator states, approval cards, proactive highlights
- Pipeline and MCP status accents

## Inputs / Outputs

| Direction | Content |
|-----------|---------|
| **In** | Design tokens / CSS |
| **Out** | Rendered SPA appearance |

## Flow

_No runtime flow — presentational layer only._

## Rules and Constraints

- No theme switcher in UI.
- Status colors should align with voice indicator semantics (idle/listening/speaking).

## Open Items

_None specific to this component._

## Cross-References

- [chat-ui-overview.md](chat-ui-overview.md)
- [top-bar.md](top-bar.md)
- [technology-stack.md](technology-stack.md)
