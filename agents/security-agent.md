# Security Agent — C.O.B.R.A.

**Component:** Security
**Phase:** 1 (parallel with Configuration)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/security]]
- `specs/security/` — all files:
  - `security-overview.md`, `data-protection.md`, `authentication.md`
  - `auto-lock.md`, `outbound-audit-log.md`, `network-access.md`
  - `anomaly-detection.md`, `privacy.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- OS file permission setup for `~/.cobra/` data directories (`data-protection.md`)
- Auto-lock timeout — configurable, default disabled (`auto-lock.md`)
- Outbound request audit log → `~/.cobra/logs/outbound-audit.log` (`outbound-audit-log.md`)
- Network binding — localhost vs. local network (`network-access.md`)
- Anomaly detection — allowlist + block/alert on unexpected outbound (`anomaly-detection.md`)

## 3. Exposes to Other Agents
- **Outbound audit logging function** — `audit_outbound(destination, topic, sanitized_payload)`. Every component that makes external calls uses this. Writes to `~/.cobra/logs/outbound-audit.log`.
- Anomaly detection wraps this path: unexpected destinations are blocked/alerted per the allowlist.

## 4. Depends On
- **[[config-agent]]** — reads the security config block via the Config reader API.

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess on privacy or security behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- Privacy and approval rules are hard rules: if a spec is ambiguous about a security boundary, escalate rather than assume the permissive option.

## 6. Review Checklist (Lead Developer gate)
- [ ] `~/.cobra/` directories created with correct OS permissions
- [ ] Auto-lock implemented, configurable, default disabled
- [ ] Outbound audit log captures destination, topic, sanitized payload for every external call
- [ ] Network binding respects localhost vs. local-network config
- [ ] Anomaly detection: allowlist enforced, unexpected outbound blocked/alerted
- [ ] Privacy hard rule: no personal data in any logged outbound payload
- [ ] Audit logging contract matches what all consumer components expect
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| File permissions / data protection | Not started |
| Auto-lock | Not started |
| Outbound audit log | Not started |
| Network binding | Not started |
| Anomaly detection | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] — security config
- Consumers: [[mcp-agent]] · [[brain-agent]] · [[tools-agent]]
