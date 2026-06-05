# Voice Agent — C.O.B.R.A.

**Component:** Voice
**Phase:** 3 (parallel with Chat UI)
**Reports to:** Lead Developer ([[AGENTS]])

---

## 1. Owned Specs
- [[specs/voice]]
- `specs/voice/` — all files:
  - `voice-overview.md`, `wake-word.md`, `session-lifecycle.md`
  - `voice-input-pipeline.md`, `mood-inference.md`, `voice-cloning.md`
  - `voice-output.md`, `interruption-handling.md`, `configuration.md`
  - `privacy.md`, `implementation-plan.md`

You own every section in these files. No section is shared with another agent.

## 2. Builds
- Wake word detection: local, configurable, passive listening (`wake-word.md`)
- Session lifecycle state machine: passive → listening → responding → passive (`session-lifecycle.md`)
- Voice input pipeline: capture → Whisper transcription → confidence check → clean text (`voice-input-pipeline.md`)
- Mood inference from speech patterns: pace, pauses — not text length (`mood-inference.md`)
- Voice cloning: guided recording session, local XTTS training, test playback approval (`voice-cloning.md`)
- Voice output: cloned TTS + text simultaneously, speed adaptation by mood (`voice-output.md`)
- Interruption queue: finish response, then process queued input (`interruption-handling.md`)
- Audio privacy: raw audio never written to disk (`privacy.md`)

## 3. Exposes to Other Agents
- **`transcribed_text` events** → Brain Input Mode Layer (cleaned text + mood metadata, no raw audio)
- **Voice output subscriber** → subscribes to Brain response events for cloned TTS playback

## 4. Depends On
- **[[config-agent]]** — voice config (`voice/configuration.md`) via Config reader API
- **[[brain-agent]]** — `process_input` and response events

## 5. Communication Rules
- Route all questions through the Lead Developer, never to peer agents.
- Report blockers immediately — do not guess transcription or mood-inference behavior.
- Only rely on contracts the Lead Developer has confirmed in writing.
- The `transcribed_text` event schema and voice-output subscription are shared contracts with Brain; coordinate changes through the Lead Developer.

## 6. Review Checklist (Lead Developer gate)
- [ ] Wake word detection runs locally, configurable, in passive listening
- [ ] Session lifecycle state machine matches passive→listening→responding→passive
- [ ] Input pipeline: capture → Whisper → confidence check → clean text
- [ ] Mood inferred from pace/pauses, not text length
- [ ] Voice cloning: guided recording, local XTTS training, test-playback approval
- [ ] Output: cloned TTS + text simultaneously, speed adapts to mood
- [ ] Interruption queue finishes current response before processing queued input
- [ ] **Audio privacy:** raw audio never written to disk
- [ ] `transcribed_text` + voice-output contracts match Brain expectations
- [ ] Open Items flagged to Damian if blocking

## 7. Current Status
| Spec area | Status |
|---|---|
| Wake word | Not started |
| Session lifecycle | Not started |
| Voice input pipeline | Not started |
| Mood inference | Not started |
| Voice cloning | Not started |
| Voice output | Not started |
| Interruption handling | Not started |
| Audio privacy | Not started |

> Update status as work progresses. Work is complete only after a PASS verdict from the Lead Developer.

## Related Agents
- [[AGENTS]] — Lead Developer
- [[config-agent]] · [[brain-agent]]
- Consumers: [[chat-ui-agent]]
