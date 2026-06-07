# Pre-Start Onboarding — PASS Review

**Date:** 2026-06-06  
**Reviewer:** Lead Developer  
**Scope:** Voice enrollment → seed interview (S1–S5) hard gate before operational use

## Verdict: PASS

## Spec compliance

| Spec | Status |
|------|--------|
| `specs/onboarding/first-run-sequence.md` | Implemented — config → voice → seed → complete |
| `specs/voice/voice-cloning.md` | Tiered duration (15 min gate / 1 hr recommended) |
| `specs/seed-document/minimum-viable-seed.md` | Hard gate on S1–S5 |
| `specs/orchestrator/startup-phases.md` | Post-READY onboarding mode |
| `specs/configuration/first-time-setup.md` | W10 handoff to onboarding shell |

## Implementation summary

- **`OnboardingManager`** — persists `~/.cobra/onboarding_state.json`, syncs voice + seed completion
- **Voice enrollment** — expanded prompts, tiered duration, REST APIs, Chat UI panel, CL4 test playback
- **Brain gate** — blocks pipeline until voice approved; seed gate until S1–S5 stored
- **Bootstrap** — wires handlers, skips LM wait when wizard needed, auto-starts seed after voice approve
- **Chat UI** — onboarding overlay with step indicator (Config → Voice → Personality → Ready)

## Tests

- `tests/orchestrator/test_onboarding.py` — gate progression, pipeline block
- Updated `tests/brain/test_brain.py`, `tests/voice/test_voice.py`, `tests/voice/test_output.py`
- 84 related tests passing

## Known limitations (deferred)

- Browser sends WebM samples; server uses client-reported duration when WAV parse fails
- Full 1-hour voice collection encouraged post-gate, not enforced on day one
- Wiki browser inline override for You page (seed Phase 6) still open

## Drift notes

- Agent status tables in `agents/brain-agent.md` / `agents/voice-agent.md` should be synced separately
