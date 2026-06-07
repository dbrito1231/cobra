# C.O.B.R.A. Tools — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Tools component defines every action C.O.B.R.A. can take on behalf of the user beyond conversation. Tools are sandboxed by default, logged for learning, and governed by a clear approval model. The user retains full control over destructive actions and all outbound communication.

---

## 1. Tool Set

| Tool | Description |
|---|---|
| **Web Search** | Search the internet for information |
| **Code Execution** | Write and run code on the user's machine |
| **File Management** | Read, write, and organize files and folders |
| **App Control** | Open, close, and interact with applications |
| **Calendar** | Read and create events, check schedule |
| **Communication** | Draft emails and messages (Slack, Discord, etc.) |
| **System Control** | Volume, brightness, notifications, system settings |
| **Extensibility** | Add new tools on demand |

> Browser control is explicitly excluded.

---

## 2. Approval Model

### 2.1 Read-Only Tools
Tools that only read or retrieve data execute automatically without asking for approval.

Examples: web search, reading a file, checking the calendar, reading system status.

### 2.2 Destructive or Irreversible Actions
Any tool call that modifies, deletes, sends, or creates something requires explicit user approval before execution.

Examples: deleting a file, creating a calendar event, sending a message, changing system settings.

C.O.B.R.A. stops, explains exactly what it wants to do and why, and waits for approval before proceeding. Denied = nothing executed.

### 2.3 Communication — Special Rule
C.O.B.R.A. **never sends messages on behalf of the user.** All communication tools produce drafts only. The user always sends manually. This applies to email, Slack, Discord, and any other communication tool regardless of recipient.

### 2.4 Code Execution — Special Rule
C.O.B.R.A. **always shows the user the code before running it**, no exceptions. The user reviews and approves before execution proceeds. This applies to all scripts regardless of complexity or scope.

---

## 3. Tool Chaining

C.O.B.R.A. can chain multiple tools together automatically to complete complex tasks without interrupting the user.

Example: "Summarize my emails about the C.O.B.R.A. project and add a task to my calendar" → C.O.B.R.A. reads emails (read-only, automatic) → summarizes → creates calendar event (destructive, requires approval before creating).

Rules:
- Read-only chains execute automatically end to end
- If any step in the chain is destructive, C.O.B.R.A. pauses the chain at that step and asks for approval before continuing
- If a step fails mid-chain, the failure handling rules apply (see Section 4)

---

## 4. Failure Handling

If a tool fails or returns an error:
1. C.O.B.R.A. retries automatically once
2. If retry also fails → C.O.B.R.A. reports the failure to the user and asks how to proceed
3. C.O.B.R.A. does not silently swallow errors or substitute unrelated tools without notifying the user

---

## 5. Sandboxing

### 5.1 Default Behavior
All tools run in a sandboxed environment by default. This isolates tool execution from the rest of the user's system, preventing accidental damage.

### 5.2 Override
The user can explicitly grant full system access to a specific tool when needed. This is a per-tool, per-session override — not a global setting. C.O.B.R.A. notifies the user when a tool is running outside the sandbox.

---

## 6. Tool Memory

Every tool call is logged in full and stored in the wiki under a dedicated Tools log page. This includes:
- Tool used
- Action taken
- Outcome (success or failure)
- Timestamp

This data is used by C.O.B.R.A. to:
- Learn the user's tool preferences over time
- Improve future tool selection and chaining decisions
- Surface patterns (e.g. "You run this type of search every Monday")

Tool memory follows the same privacy rules as all other memory — fully local, never sent externally.

---

## 7. Extensibility

When the user wants to add a new tool:
1. User describes what the tool should do in plain language
2. C.O.B.R.A. asks clarifying questions if needed
3. C.O.B.R.A. proposes a tool design for user approval
4. Upon approval, C.O.B.R.A. builds and registers the tool
5. The new tool is immediately available for use and follows all approval, sandboxing, and logging rules automatically

No implementation begins without user approval at step 4.

---

## 8. Privacy — Hard Rule

All tool calls follow the same master privacy rule as the brain:
- Tools never send personal data externally without explicit user approval
- Outbound tool calls (e.g. web search queries) are sanitized — topic only, never personal context
- Communication drafts stay local until the user manually sends them

---

## Open Items

- [ ] Define specific retry count before reporting failure (e.g. 1 retry or 2)
- [ ] Define sandbox technology (e.g. Docker, subprocess isolation, virtual environment)
- [ ] Define which communication platforms are supported at launch (email, Slack, Discord, etc.)
- [ ] Define tool registry format for storing and loading custom tools

---

## Component Specs

Decomposed, implementable specs live in **`specs/tools/`**. The parent document and [tools-flow.mermaid](tools-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [tools/tools-overview.md](tools/tools-overview.md) | Overall tools component index and cross-cutting rules |
| [tools/implementation-plan.md](tools/implementation-plan.md) | Phased implementation plan |
| [tools/tool-set.md](tools/tool-set.md) | Built-in tool catalog (browser control excluded) |
| [tools/execution-flow.md](tools/execution-flow.md) | Core runtime spine and brain return path |
| [tools/approval-model.md](tools/approval-model.md) | Read-only, destructive, code, and communication rules |
| [tools/tool-chaining.md](tools/tool-chaining.md) | Multi-tool chains and pause behavior |
| [tools/failure-handling.md](tools/failure-handling.md) | Retry, report, and user recovery |
| [tools/sandboxing.md](tools/sandboxing.md) | Default sandbox and per-session override |
| [tools/tool-memory.md](tools/tool-memory.md) | Wiki logging and learning |
| [tools/extensibility.md](tools/extensibility.md) | Adding and registering custom tools |
| [tools/privacy.md](tools/privacy.md) | Privacy hard rule for all tool calls |

**Platform support:** OS-integrated tools (app control, system control), sandbox env, and capability tiers defer to [platform-support.md](platform-support.md). **Communication platforms** (Slack, email, etc.) are unrelated to OS platform support — see Open Items below.

---

*This spec is a living document. No implementation begins without user approval.*
