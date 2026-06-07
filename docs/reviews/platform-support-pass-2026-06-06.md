# Platform Support — PASS Review

**Date:** 2026-06-06  
**Reviewer:** Lead Developer  
**Scope:** Phase A spec + Phase B1–B4 implementation per platform support plan

## Verdict: PASS

## Spec compliance

| Spec | Status |
|------|--------|
| `specs/platform-support.md` | Created — tiers, paths, capability matrix, backlog PS-1–PS-11 |
| Parent specs (7) | Cross-references added |
| High-priority sub-specs (12) | Cross-references added |
| `agents/AGENTS.md` §2 + §7 | Platform support + onboarding indexed |

## Implementation summary

### B1 — Critical cross-platform hygiene

- **`src/security/path_redaction.py`** — shared `redact_home_paths()` for macOS, Linux, Windows, tilde
- Wired into security, brain, tools, mcp, and chat_ui privacy modules
- **`src/cobra_platform/env.py`** — subprocess env forwards `HOME` and `USERPROFILE`
- **`src/tools/sandbox.py`**, **`code_execution.py`** — use platform env helper
- **`src/voice/cloning.py`** — enrollment completion requires Coqui (`tts_available`); `install_instructions()` added
- **`src/chat_ui/static/js/app.js`** — blocks record/train when TTS unavailable

### B2 — Voice Tier 2

- **`src/voice/recorder.py`** — `normalize_enrollment_audio()` WebM→WAV via ffmpeg
- **`docs/voice/windows-e2e-checklist.md`** — manual Windows validation gate (PS-6)

### B3 — Tools Tier 2

- **`src/tools/builtin/system_control.py`** — Linux volume (`pactl`/`amixer`), Windows volume (`nircmd` or partial), explicit unsupported for `notifications`/`settings`
- **`tests/tools/test_system_control_tier2.py`**, Windows cases in **`test_calendar_app_control.py`**

### B4 — Validation

- **`.github/workflows/test.yml`** — matrix macOS, ubuntu-latest, windows-latest
- **`agents/spec-sync-agent.md`** — platform-support drift checklist
- **`tests/security/test_path_redaction.py`**

## Tests

- Platform-related: 14 tests passing (path redaction, onboarding gate, system_control tier2, Windows app_control)
- Full suite: 198 passed, 6 failed (pre-existing: LM Studio unreachable in config backup/profile tests; unrelated flaky chain tests on this host)

## Known limitations (documented in spec)

- Windows cloned TTS **unsupported until E2E checklist passes** (Tier 2)
- Windows volume without `nircmd` returns partial status only
- `notifications` / `settings` system_control ops explicitly unsupported on all OSes
- Native launch artifacts (`.app`, service) remain PS-11 open item

## Drift notes

- Component matrix row for system control updated to “status + volume” on Tier 2
- Windows voice tier promotion requires manual sign-off on `docs/voice/windows-e2e-checklist.md`
