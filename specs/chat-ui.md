# C.O.B.R.A. Chat UI — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Chat UI is the primary visual interface for C.O.B.R.A. It is a local web application served on the user's machine — no internet required. The UI presents a three-panel dark-mode layout: conversation panel, wiki browser panel, and status panel. It shows real-time pipeline activity, supports full-text search across all sessions, and always displays voice state.

---

## 1. Application Type

- **Local web app** — served by a local web server running on the user's machine
- Accessed via browser at `http://localhost:[port]` (default port defined in config)
- No internet connection required — fully offline capable
- Starts automatically when C.O.B.R.A. launches
- Stops when C.O.B.R.A. stops

---

## 2. Layout — Three Panel

```
┌─────────────────────────────────────────────────────────┐
│  C.O.B.R.A.   [Voice Indicator]   [Profile]   [Search] │  ← Top bar
├──────────────────┬──────────────────┬────────────────────┤
│                  │                  │                    │
│  CHAT PANEL      │  WIKI BROWSER    │  STATUS PANEL      │
│  (left)          │  (center)        │  (right)           │
│                  │                  │                    │
│  Conversation    │  Wiki pages      │  Pipeline step     │
│  history         │  index.md        │  MCP servers       │
│  Input bar       │  Page viewer     │  Proactive queue   │
│                  │                  │                    │
├──────────────────┴──────────────────┴────────────────────┤
│  Text input bar                          [Send]          │  ← Bottom bar
└─────────────────────────────────────────────────────────┘
```

### 2.1 Chat Panel (Left)
- Displays full conversation history — all exchanges in the current session
- Each message shows: sender label (You / C.O.B.R.A.), timestamp, message content
- C.O.B.R.A. responses display voice and text simultaneously during playback
- Pipeline step indicators appear inline below each C.O.B.R.A. response while processing
- Approval prompts appear inline when C.O.B.R.A. requires user sign-off
- Proactive items surface as a highlighted card between exchanges

### 2.2 Wiki Browser Panel (Center)
- Displays the wiki `index.md` by default — full catalog of all pages
- User can click any wiki page to open and read it
- Pages render as formatted markdown
- Back navigation to return to the index
- Read-only — wiki is edited by C.O.B.R.A. only, not through the UI directly

### 2.3 Status Panel (Right)
Three live sections:

**Active Pipeline Step**
- Shows exactly which step C.O.B.R.A. is currently executing
- Steps: Idle / Reasoning / Memory Retrieval / Tool Execution / Verification / Personality Mirror / Response Synthesis
- Updates in real time as C.O.B.R.A. works
- Idle state shows when C.O.B.R.A. is waiting for input

**Connected MCP Servers**
- Lists all configured MCP servers with live status: Online / Offline / Validating
- Updates automatically when server status changes

**Proactive Items Queue**
- Shows count of queued proactive items waiting to surface
- Displays a preview of the top priority item
- User can tap "Tell me now" to surface the top item immediately

---

## 3. Top Bar

- **C.O.B.R.A. logo / name** — left aligned
- **Voice Indicator** — always visible, shows current voice state:
  - 🔵 Idle — waiting for wake word
  - 🟢 Listening — active session, ready for input
  - 🟡 Speaking — C.O.B.R.A. is playing a voice response
- **Active profile name** — shows current profile (e.g. Default, Work)
- **Search button** — opens full-text search overlay

---

## 4. Search

- Full-text search across all sessions and all conversation history
- Search overlay opens over the three-panel layout
- Results show: matched text excerpt, session date, and a link to jump to that exchange
- Search is local — no external service used
- Results update as you type

---

## 5. Voice and Text Coexistence

- Text input bar is always visible at the bottom of the chat panel
- Voice and text can be used freely within the same session
- When C.O.B.R.A. responds via voice, the text appears in the chat panel simultaneously
- Voice indicator in the top bar always reflects the current state regardless of whether text or voice is the active input mode

---

## 6. Pipeline Step Indicators

When C.O.B.R.A. is processing, the status panel and an inline indicator in the chat show the active step:

| Step | Label shown |
|---|---|
| Internal Reasoning | Thinking... |
| Memory Retrieval | Searching memory... |
| Tool Execution | Running tool: [tool name] |
| Verification Pipeline | Verifying claim... |
| Personality Mirror | Composing response... |
| Response Synthesis | Finalizing... |

- Indicators disappear when the response is delivered
- If a step takes longer than expected, a subtle elapsed time counter appears

---

## 7. Approval Prompts

When C.O.B.R.A. requires user approval (tool action, MCP call, data sharing):
- An approval card appears inline in the chat panel
- Card shows: what C.O.B.R.A. wants to do, why, and what data will be involved
- Two buttons: **Approve** and **Deny**
- C.O.B.R.A. waits — it does not proceed until the user responds

---

## 8. Theme

- **Dark mode only** — no light mode, no toggle
- Color palette: dark backgrounds, high contrast text, accent colors for status indicators
- Consistent with C.O.B.R.A.'s identity

---

## 9. Technology Stack

- **Frontend:** HTML, CSS, JavaScript — single page application
- **Local server:** Python (FastAPI or Flask) serving the web app on localhost
- **Markdown rendering:** Client-side markdown parser for wiki page display
- **Real-time updates:** WebSocket connection between browser and C.O.B.R.A. backend for live pipeline step updates and status panel data

---

## Open Items

- [ ] Define default localhost port
- [ ] Define whether panels are resizable by the user
- [ ] Define behavior when browser tab is closed — does C.O.B.R.A. continue running in background?
- [ ] Define whether search indexes are built on startup or on demand
- [ ] Define markdown rendering library for wiki panel

---

## Component Specs

Decomposed, implementable specs live in **`specs/chat-ui/`**. The parent document and [chat-ui-flow.mermaid](chat-ui-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [chat-ui/chat-ui-overview.md](chat-ui/chat-ui-overview.md) | Overall Chat UI index, layout diagram, cross-cutting rules |
| [chat-ui/implementation-plan.md](chat-ui/implementation-plan.md) | Phased implementation plan |
| [chat-ui/application-type.md](chat-ui/application-type.md) | Local web app lifecycle and localhost access |
| [chat-ui/chat-panel.md](chat-ui/chat-panel.md) | Conversation, input, voice+text, proactive cards |
| [chat-ui/wiki-browser-panel.md](chat-ui/wiki-browser-panel.md) | Read-only wiki browser and markdown view |
| [chat-ui/status-panel.md](chat-ui/status-panel.md) | Pipeline step, MCP status, proactive queue |
| [chat-ui/top-bar.md](chat-ui/top-bar.md) | Logo, voice indicator, profile, search button |
| [chat-ui/search.md](chat-ui/search.md) | Full-text local search overlay |
| [chat-ui/pipeline-indicators.md](chat-ui/pipeline-indicators.md) | Live step labels in chat and status |
| [chat-ui/approval-prompts.md](chat-ui/approval-prompts.md) | Inline approve/deny cards |
| [chat-ui/theme.md](chat-ui/theme.md) | Dark-mode-only visual design |
| [chat-ui/technology-stack.md](chat-ui/technology-stack.md) | SPA, Python server, markdown, WebSocket |

**Platform support:** Browser launch, background lifecycle, and Python server runtime defer to [platform-support.md](platform-support.md).

---

*This spec is a living document. No implementation begins without user approval.*
