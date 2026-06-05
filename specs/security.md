# C.O.B.R.A. Security — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Security component defines how C.O.B.R.A. protects local data, controls access, monitors outbound activity, and alerts on anomalies. Security is enforced locally — no cloud service is used for any security function.

---

## 1. Data Protection

- All local data (wiki, memory, logs, config, voice model) is protected by **OS file permissions**
- No additional encryption at rest is applied
- Files are owned by the user's OS account only — no other system user can access them
- The user is responsible for OS-level security (machine password, disk encryption if desired)

---

## 2. Authentication

- C.O.B.R.A. **auto-starts without requiring a login or password**
- No PIN, password, or biometric required to launch
- Access is controlled at the OS level — whoever is logged into the machine can use C.O.B.R.A.

---

## 3. Auto-Lock

- C.O.B.R.A. supports a **configurable auto-lock timeout**
- When the timeout expires after inactivity, C.O.B.R.A. locks itself
- In locked state: voice and text input are disabled, the UI displays a lock screen
- Unlocking requires the user to interact with the UI (click or speak to resume)
- Timeout is user-defined in the config file — no default enforced
- Auto-lock can be disabled entirely by setting timeout to zero

```yaml
security:
  auto_lock_timeout_minutes: 0   # 0 = disabled. Set to any value to enable.
```

---

## 4. Outbound Request Audit Log

Every outbound request made by C.O.B.R.A. is logged in full:

| Field | Description |
|---|---|
| Timestamp | When the request was made |
| Destination | API or server called (Claude API, Copilot, MCP server name) |
| Sanitized query | What was sent — topic only, never personal data |
| Trigger | Which pipeline step initiated the request |
| Approval status | Approved / Denied / Auto (read-only tool) |
| Outcome | Success / Failure / Timeout |

- Audit log is stored locally at `~/.cobra/logs/outbound-audit.log`
- Never sent externally
- Viewable in the Chat UI (future: audit log panel)
- Retained indefinitely — user can clear manually

---

## 5. Network Access

- C.O.B.R.A. is accessible from **any device on the user's local home network**
- The local web server binds to the local network interface (not just localhost)
- No internet exposure — C.O.B.R.A. is not accessible from outside the home network
- Network access can be restricted to localhost only via config if preferred

```yaml
security:
  network_access: local_network   # Options: localhost_only, local_network
```

---

## 6. Anomaly Detection

C.O.B.R.A. monitors for unexpected outbound connection attempts — any connection not initiated by the known pipeline:

- If detected → **immediately alerts the user** in the Chat UI and via voice
- Alert includes: what tried to connect, the destination, and the timestamp
- The connection attempt is blocked and logged in the audit log
- C.O.B.R.A. does not attempt to identify the source — it reports what it observed and lets the user decide

Known outbound destinations (not flagged):
- Claude API endpoint
- Copilot API endpoint
- Configured MCP server endpoints
- LM Studio local API

Any other outbound attempt is treated as unexpected.

---

## 7. Privacy — Hard Rule

All security mechanisms enforce the master privacy rule:
- Audit logs contain sanitized queries only — never raw personal data
- No security telemetry is sent externally
- Anomaly alerts are displayed locally only

---

## Open Items

- [ ] Define anomaly detection mechanism (OS-level firewall hooks, network monitor, or application-level intercept)
- [ ] Define audit log format (plain text, JSON, or structured log)
- [ ] Define whether the audit log is searchable from the Chat UI
- [ ] Define behavior when auto-lock triggers mid-response
- [ ] Define whether local network access requires any authentication from other devices

---

## Component Specs

Decomposed, implementable specs live in **`specs/security/`**. The parent document and [security-flow.mermaid](security-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [security/security-overview.md](security/security-overview.md) | Overall security index and cross-cutting rules |
| [security/implementation-plan.md](security/implementation-plan.md) | Phased implementation plan |
| [security/data-protection.md](security/data-protection.md) | OS file permissions for local data |
| [security/authentication.md](security/authentication.md) | No in-app login; OS-level access |
| [security/auto-lock.md](security/auto-lock.md) | Inactivity lock screen and input disable |
| [security/outbound-audit-log.md](security/outbound-audit-log.md) | Local outbound request audit trail |
| [security/network-access.md](security/network-access.md) | Local network vs localhost binding |
| [security/anomaly-detection.md](security/anomaly-detection.md) | Known-destination allowlist and block/alert |
| [security/privacy.md](security/privacy.md) | Sanitized logs and local-only alerts |

---

*This spec is a living document. No implementation begins without user approval.*
