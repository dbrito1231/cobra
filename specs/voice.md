# C.O.B.R.A. Voice Layer — Specification
*Cognitive Optimized Brain for Retrieval and Action*

**Status:** Draft  
**Version:** 1.0  
**Last Updated:** 2026-06-03  
**Owner:** Damian  

---

## Overview

The Voice Layer handles all audio input and output for C.O.B.R.A. It covers wake word detection, voice input transcription via Whisper, text-to-speech output using a cloned voice, session lifecycle management, and audio privacy. All voice processing runs locally — no audio data is ever sent externally.

---

## 1. Wake Word

- C.O.B.R.A. listens passively for a **custom wake word** defined by the user during setup
- The wake word is configurable and stored in the config file
- Upon detecting the wake word, C.O.B.R.A. plays a **short audio cue** (a subtle tone or chime) to confirm it is now listening
- Wake word detection runs locally at all times — no cloud service used

### 1.1 Session End Phrase
- C.O.B.R.A. stays active and listening continuously after activation
- The session ends when the user says: **"That's all for now C.O.B.R.A."**
- Upon hearing the session end phrase, C.O.B.R.A. acknowledges and returns to passive wake word listening mode
- No timeout — C.O.B.R.A. never auto-ends a session

---

## 2. Voice Input Pipeline

Once activated, all spoken input passes through the following steps:

1. **Audio capture** — microphone input captured locally
2. **Whisper transcription** — audio converted to text locally via Whisper
3. **Confidence check** — if transcription confidence is low, C.O.B.R.A. plays the audio cue again and asks the user to repeat
4. **Clean text output** — transcribed text passed to the brain's Input Mode Layer
5. **Audio discarded** — raw audio is never stored, only the transcription is kept

### 2.1 Mood Inference from Voice
- Mood and energy are inferred from **speech patterns** — pace, pauses, volume — not from transcribed text length
- Inferences feed into the brain's shared context state
- Audio used for inference is processed in memory only and immediately discarded — never written to disk

---

## 3. Voice Output — Voice Cloning

C.O.B.R.A. speaks back in a voice cloned from the user. The output voice sounds like the user themselves.

### 3.1 Voice Cloning Setup
- Requires **1 hour or more** of recorded voice samples from the user
- Samples are recorded locally via a guided recording session
- A local TTS model (Coqui TTS / XTTS or equivalent) trains on the samples locally
- Voice samples and the trained model are stored locally only — never uploaded or sent externally
- The cloned voice model is saved to `~/.cobra/voice/`

### 3.2 Output Behavior
- Every C.O.B.R.A. response is delivered as **both voice and text simultaneously**
- Voice output uses the cloned voice model at all times
- Text output appears in the Chat UI in sync with the spoken response

### 3.3 Speaking Speed Adaptation
- Speaking speed adapts automatically based on mood inference:
  - Busy/stressed → faster pace
  - Relaxed/exploratory → slower, more deliberate pace
- Speed adaptation is applied at TTS generation time — no post-processing

---

## 4. Interruption Handling

- C.O.B.R.A. **always finishes its full response** before listening again
- If the user speaks while C.O.B.R.A. is responding, the input is queued
- Once the response completes, C.O.B.R.A. processes the queued input immediately
- No mid-response cut-off under any circumstances

---

## 5. Session Lifecycle

```
Passive listening (wake word only)
    ↓ Wake word detected
Audio cue plays → C.O.B.R.A. listening
    ↓ User speaks
Whisper transcription → Brain processes → Voice + text response
    ↓ Response complete
C.O.B.R.A. continues listening (no wake word needed)
    ↓ Repeat until...
User says "That's all for now C.O.B.R.A."
    ↓
C.O.B.R.A. acknowledges → Returns to passive listening
```

---

## 6. Audio Privacy — Hard Rule

- **Raw audio is never stored** — only transcriptions are kept
- Voice samples collected for cloning are stored locally only — never uploaded
- The cloned voice model is stored locally only — never shared
- Audio used for mood inference is processed in memory and immediately discarded
- No audio processing service, cloud API, or external model is used at any point

---

## 7. Voice Cloning Recording Session

The recording session is a guided process run once during setup:

1. C.O.B.R.A. presents prompts for the user to read aloud (varied sentences, tone, pacing)
2. User records at least 1 hour of samples across multiple sessions if preferred
3. Samples are processed locally to train the cloned voice model
4. C.O.B.R.A. plays back a test response using the cloned voice for user approval
5. If the clone quality is unsatisfactory, additional recording sessions can be run to improve it
6. The model can be retrained at any time with new samples

---

## 8. Configuration

```yaml
voice:
  wake_word: ""                    # User-defined custom wake word
  session_end_phrase: "That's all for now C.O.B.R.A."
  audio_cue: true                  # Play tone on activation
  tts_model: xtts                  # Local TTS model (xtts, coqui, etc.)
  voice_model_path: ~/.cobra/voice/
  speaking_speed_adaptation: true  # Adapt speed to mood inference
  output_mode: both                # voice + text simultaneously
```

---

## Open Items

- [ ] Define specific wake word detection library (e.g. Porcupine, OpenWakeWord)
- [ ] Define minimum acceptable Whisper transcription confidence threshold
- [ ] Define audio cue sound (tone, chime, or brief spoken acknowledgment)
- [ ] Define minimum voice sample quality requirements for cloning (microphone spec, environment)
- [ ] Define behavior if cloned voice model file is missing or corrupted on startup
- [ ] Define whether additional recording sessions append to or replace existing voice samples

---

## Component Specs

Decomposed, implementable specs live in **`specs/voice/`**. The parent document and [voice-flow.mermaid](voice-flow.mermaid) remain authoritative sources; component files add boundaries and implementation detail without removing content from either source.

| Spec | Description |
|------|-------------|
| [voice/voice-overview.md](voice/voice-overview.md) | Overall voice layer index and cross-cutting rules |
| [voice/implementation-plan.md](voice/implementation-plan.md) | Phased implementation plan |
| [voice/wake-word.md](voice/wake-word.md) | Custom wake word and session end phrase |
| [voice/voice-input-pipeline.md](voice/voice-input-pipeline.md) | Whisper transcription and confidence retry |
| [voice/mood-inference.md](voice/mood-inference.md) | Speech-pattern mood for shared context |
| [voice/voice-cloning.md](voice/voice-cloning.md) | Guided recording and local TTS training |
| [voice/voice-output.md](voice/voice-output.md) | Cloned TTS, speed adaptation, dual output |
| [voice/interruption-handling.md](voice/interruption-handling.md) | Queue input during responses |
| [voice/session-lifecycle.md](voice/session-lifecycle.md) | Passive, active, and responding states |
| [voice/privacy.md](voice/privacy.md) | Local-only audio hard rules |
| [voice/configuration.md](voice/configuration.md) | `voice:` YAML configuration block |

---

*This spec is a living document. No implementation begins without user approval.*
