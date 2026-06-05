# C.O.B.R.A. MCP Server Layer — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The MCP Server Layer manages how C.O.B.R.A. connects to, validates, routes to, and monitors Model Context Protocol (MCP) servers. MCP servers extend C.O.B.R.A.'s capabilities for tool use and external verification. All connections are manually configured, all calls require approval, and all activity is logged.

---

## 1. Discovery

- MCP servers are **manually configured only** — added explicitly via the config file or the setup wizard
- No automatic network scanning or auto-discovery
- Each server entry in the config defines: name, endpoint URL, description, and what capabilities it provides
- New servers can be added at any time without restarting C.O.B.R.A.

---

## 2. Multi-Server Support

- C.O.B.R.A. connects to **all configured MCP servers simultaneously** on startup
- Each server runs as an independent connection — one server going down does not affect others
- C.O.B.R.A. maintains a live registry of available servers and their capabilities
- Routing to the correct server is automatic based on the capability required

### 2.1 Routing Logic
- Each MCP server declares what capabilities it provides (e.g. web search, calendar, code execution)
- When a tool or verification call is needed, C.O.B.R.A. routes to the server that declares that capability
- If multiple servers declare the same capability, C.O.B.R.A. routes to the first available one
- Routing decisions are logged for every call

---

## 3. Startup Validation

All configured MCP servers are validated on startup before C.O.B.R.A. is ready:

| Check | What it validates |
|---|---|
| Server reachable | Endpoint responds at configured URL |
| Capabilities declared | Server returns a valid capability list |
| Protocol version | Server MCP protocol version is compatible |

- If a server fails validation, C.O.B.R.A. reports which server failed and why
- C.O.B.R.A. still starts with the remaining valid servers
- Failed servers are flagged as unavailable in the live registry
- The user is notified of any validation failures at startup

---

## 4. Approval Model

**Every MCP server call requires explicit user approval before execution — no exceptions.**

Before calling any MCP server, C.O.B.R.A.:
1. Stops and tells the user exactly which server it wants to call and why
2. Shows what data will be sent to the server (sanitized — topic only, never personal context)
3. Waits for explicit user approval
4. Denied = call is cancelled, nothing is sent

This applies to all MCP calls including verification pipeline queries.

---

## 5. Server Down Mid-Session

If an MCP server goes offline during an active session:

1. C.O.B.R.A. retries the connection silently in the background
2. If the server recovers → resumes normal operation, notifies the user
3. If the server remains down after a defined retry period → notifies the user and marks the server unavailable
4. Any pending tasks requiring that server are paused and the user is informed
5. C.O.B.R.A. continues operating normally with remaining available servers

---

## 6. Logging

Every MCP server interaction is logged in full in the wiki under a dedicated MCP log page:

- Server name and endpoint called
- Capability invoked
- Sanitized query sent (never raw personal data)
- Response received (summarized if large)
- Outcome (success, failure, timeout)
- Timestamp
- Whether user approval was granted or denied

Logs are stored locally only — never sent externally.

---

## 7. Privacy — Hard Rule

All MCP server calls follow the master privacy rule:
- **Outbound calls carry topic only — never personal context**
- All queries are sanitized before being sent to any MCP server
- Personal data never leaves the system through an MCP call without explicit per-request user approval
- Approval is required for every call regardless of data sensitivity

---

## 8. Config Structure

```yaml
mcp_servers:
  - name: "Web Search MCP"
    endpoint: "http://localhost:3000"
    description: "Provides web search capability"
    capabilities:
      - web_search
    enabled: true

  - name: "Calendar MCP"
    endpoint: "http://localhost:3001"
    description: "Provides calendar read and write"
    capabilities:
      - calendar_read
      - calendar_write
    enabled: true
```

---

## Open Items

- [ ] Define retry interval and maximum retry count before marking server unavailable
- [ ] Define MCP protocol version compatibility requirements
- [ ] Define behavior when two servers declare conflicting capabilities
- [ ] Define whether capability routing priority can be manually configured per server
- [ ] Define what happens to a paused task when a server comes back online — auto-resume or require user to re-trigger

---

## Component Specs

Decomposed, implementable specs live in **`specs/mcp-server-layer/`**. The parent document and [mcp-server-layer-flow.mermaid](mcp-server-layer-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [mcp-server-layer/mcp-server-layer-overview.md](mcp-server-layer/mcp-server-layer-overview.md) | Overall MCP layer index and cross-cutting rules |
| [mcp-server-layer/implementation-plan.md](mcp-server-layer/implementation-plan.md) | Phased implementation plan |
| [mcp-server-layer/discovery.md](mcp-server-layer/discovery.md) | Manual MCP server registration only |
| [mcp-server-layer/multi-server-support.md](mcp-server-layer/multi-server-support.md) | Simultaneous independent connections |
| [mcp-server-layer/live-registry.md](mcp-server-layer/live-registry.md) | Live server capabilities and status |
| [mcp-server-layer/startup-validation.md](mcp-server-layer/startup-validation.md) | Startup reachability and protocol checks |
| [mcp-server-layer/routing-logic.md](mcp-server-layer/routing-logic.md) | Capability-based server selection |
| [mcp-server-layer/approval-model.md](mcp-server-layer/approval-model.md) | Per-call user approval |
| [mcp-server-layer/server-down-mid-session.md](mcp-server-layer/server-down-mid-session.md) | Mid-session retry and task pause |
| [mcp-server-layer/logging.md](mcp-server-layer/logging.md) | Wiki MCP audit log |
| [mcp-server-layer/privacy.md](mcp-server-layer/privacy.md) | Topic-only outbound and local logs |
| [mcp-server-layer/config-structure.md](mcp-server-layer/config-structure.md) | `mcp_servers` YAML schema |
| [mcp-server-layer/execution-flow.md](mcp-server-layer/execution-flow.md) | Runtime call spine to brain pipeline |

---

*This spec is a living document. No implementation begins without user approval.*
