# Config Agent — C.O.B.R.A.

**Component:** Configuration
**Phase:** 1 (loads first)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/configuration]]
- `specs/configuration/` — all files:
  - `configuration-overview.md`, `config-file-structure.md`, `storage.md`
  - `first-time-setup.md`, `startup-flow.md`, `startup-validation.md`
  - `lm-studio-wait.md`, `profiles.md`, `hot-reload.md`
  - `backup-restore.md`, `privacy.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- YAML config file schema and loader
- First-time setup wizard (10-step flow per `first-time-setup.md`)
- Startup validation (checks V1–V9 per `startup-validation.md`)
- LM Studio wait-and-retry loop (`lm-studio-wait.md`)
- Profile system (named profiles, hot switch — `profiles.md`)
- Hot reload (file watcher + revalidate — `hot-reload.md`)
- Backup and restore commands (`backup-restore.md`)

## 3. Exposes to Other Agents
- **Config reader API** — typed, read-only accessors for each config block. Every component reads its settings through this API. Raises on missing required keys; never returns silent defaults for required fields.
- Contract is broadcast by the Lead Developer (see [[AGENTS]] §8) before any consumer begins.

## 4. Depends On
- Nothing. Configuration loads first in Phase 1.

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately (ambiguous spec, undefined interface) — do not guess.
- Only rely on contracts the Lead Developer has confirmed in writing.
- When you change the config schema, notify the Lead Developer so the reader-API contract is re-broadcast to all consumers.

## 6. Review Checklist (Lead Developer gate)
- [ ] Config schema matches `config-file-structure.md` exactly
- [ ] 10-step setup wizard implemented in full (no skipped steps)
- [ ] Validation checks V1–V9 all implemented and ordered per spec
- [ ] LM Studio wait/retry loop matches timeout and retry behavior in spec
- [ ] Profile create/switch/hot-switch works; active profile persists
- [ ] Hot reload re-validates on file change and rejects invalid edits
- [ ] Backup and restore round-trip verified
- [ ] Privacy rules in `configuration/privacy.md` enforced (no secrets logged)
- [ ] Reader API contract matches what consumers expect
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Config schema + loader | Not started |
| First-time setup wizard | Not started |
| Startup validation V1–V9 | Not started |
| LM Studio wait/retry | Not started |
| Profiles | Not started |
| Hot reload | Not started |
| Backup/restore | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- Consumers: [[security-agent]] · [[mcp-agent]] · [[brain-agent]] · [[tools-agent]] · [[voice-agent]] · [[chat-ui-agent]] · [[orchestrator-agent]]
