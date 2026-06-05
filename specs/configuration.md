# C.O.B.R.A. Configuration — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Configuration component manages how C.O.B.R.A. is set up, validated, and maintained across sessions. It covers storage, profiles, API key management, startup behavior, hot reload, and backup. Configuration is local-only and never shared externally.

---

## 1. Storage

- All configuration is stored in a **single local config file** on the user's machine
- Default location: `~/.cobra/config.yaml`
- The file is human-readable and editable directly
- Sensitive values (API keys) are stored as plain text within the config file
- The config file is never synced, uploaded, or shared externally under any circumstances

---

## 2. First-Time Setup

On first launch C.O.B.R.A. detects that no config file exists and runs a **guided setup wizard**:

1. Check for LM Studio — confirm it is installed and running
2. Select default model from available LM Studio models
3. Enter Claude API key
4. Enter Copilot API key
5. Configure MCP servers (optional at setup, can be added later)
6. Set default profile name
7. Choose wiki storage location (default: `~/.cobra/wiki/`)
8. Choose memory/vector DB location (default: `~/.cobra/memory/`)
9. Validate all settings
10. Write config file and launch C.O.B.R.A.

The wizard can be re-run at any time via a settings command.

---

## 3. Startup Validation

Every time C.O.B.R.A. starts it validates the full configuration before doing anything else:

| Check | What it validates |
|---|---|
| Config file exists | Config file is present and readable |
| Config file valid | No malformed or missing required fields |
| LM Studio reachable | API endpoint responds at configured URL |
| Model loaded | Selected model is loaded and ready in LM Studio |
| Claude API key | Key is present (format check only — not a live call) |
| Copilot API key | Key is present (format check only — not a live call) |
| Wiki directory | Wiki storage location exists and is writable |
| Memory directory | Vector DB location exists and is writable |
| Active profile | Selected profile exists in config |

If any check fails, C.O.B.R.A. reports exactly what failed and what to do to fix it before proceeding.

---

## 4. LM Studio Unavailable at Startup

If LM Studio is not running or unreachable when C.O.B.R.A. starts:

- C.O.B.R.A. notifies the user that LM Studio is not available
- Retries the connection automatically in the background at a defined interval
- Does not start until LM Studio is confirmed reachable and the model is loaded
- Never times out — keeps retrying until the connection is established
- User can cancel the wait manually at any time

---

## 5. Profiles

C.O.B.R.A. supports multiple named configuration profiles. Each profile can have its own settings for:

- Active LM Studio model
- Personality mode (e.g. professional, personal)
- Tool permissions and sandbox overrides
- Wiki and memory directories
- MCP server connections
- API keys (if different per profile)

### 5.1 Switching Profiles
- The user can switch profiles at any time via a command
- Profile switch applies immediately — no restart required
- C.O.B.R.A. re-validates the new profile's settings on switch

### 5.2 Default Profile
- One profile is designated as the default and loads automatically on startup
- The user can change the default profile at any time

---

## 6. Hot Reload

All configuration changes apply immediately without restarting C.O.B.R.A.:

- Changes to the config file are detected automatically
- C.O.B.R.A. re-validates affected settings on change
- If a change introduces an invalid setting, C.O.B.R.A. alerts the user and reverts that specific setting to its last valid value
- The user is notified of every hot reload event

---

## 7. Backup

Configuration backup is manual and user-triggered:

- User triggers a backup via a command
- C.O.B.R.A. creates a timestamped copy of the config file in `~/.cobra/backups/`
- Backups are stored locally only — never uploaded
- The user can restore any backup via a command
- C.O.B.R.A. validates the restored config before applying it

---

## 8. Config File Structure

```yaml
# C.O.B.R.A. Configuration
version: "1.0"

active_profile: default

profiles:
  default:
    name: Default
    model:
      provider: lm_studio
      endpoint: http://localhost:1234
      model_id: ""           # e.g. llama-3-8b-instruct
    api_keys:
      claude: ""
      copilot: ""
    storage:
      wiki_dir: ~/.cobra/wiki/
      memory_dir: ~/.cobra/memory/
      logs_dir: ~/.cobra/logs/
      backups_dir: ~/.cobra/backups/
    mcp_servers: []          # list of MCP server configs
    personality_mode: default
    tool_sandbox: true       # sandboxed by default

  work:
    name: Work
    # ... same structure as default
```

---

## 9. Privacy — Hard Rule

- Config file is stored locally only — never synced or uploaded
- API keys are stored as plain text locally — the user is responsible for file-level access control
- Backups follow the same local-only rule
- No configuration data is ever sent externally

---

## Open Items

- [ ] Define config file change detection mechanism (file watcher vs. polling interval)
- [ ] Define LM Studio retry interval (e.g. every 5 seconds)
- [ ] Define whether API key format validation runs on startup or only on first use
- [ ] Define maximum number of backup files retained before oldest is pruned
- [ ] Define whether profiles can inherit from a base profile to avoid duplication

---

## Component Specs

Decomposed, implementable specs live in **`specs/configuration/`**. The parent document and [configuration-flow.mermaid](configuration-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [configuration/configuration-overview.md](configuration/configuration-overview.md) | Overall configuration component index and cross-cutting rules |
| [configuration/implementation-plan.md](configuration/implementation-plan.md) | Phased implementation plan |
| [configuration/storage.md](configuration/storage.md) | Single local config file and path defaults |
| [configuration/config-file-structure.md](configuration/config-file-structure.md) | YAML schema and profile fields |
| [configuration/first-time-setup.md](configuration/first-time-setup.md) | First-time setup wizard |
| [configuration/startup-flow.md](configuration/startup-flow.md) | Startup orchestration and ready/error paths |
| [configuration/startup-validation.md](configuration/startup-validation.md) | Startup validation checks V1–V9 |
| [configuration/lm-studio-wait.md](configuration/lm-studio-wait.md) | LM Studio unavailable retry loop |
| [configuration/profiles.md](configuration/profiles.md) | Named profiles and switching |
| [configuration/hot-reload.md](configuration/hot-reload.md) | Runtime config reload |
| [configuration/backup-restore.md](configuration/backup-restore.md) | Manual backup and restore |
| [configuration/privacy.md](configuration/privacy.md) | Privacy hard rule for configuration |

---

*This spec is a living document. No implementation begins without user approval.*
