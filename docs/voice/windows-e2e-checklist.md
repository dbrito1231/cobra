# Windows Voice E2E Validation Checklist

Manual gate before declaring Tier 2 Windows support for cloned TTS (PS-6).

## Prerequisites

- [ ] Python 3.9+ installed
- [ ] LM Studio running with a loaded model
- [ ] `pip install -r requirements.txt`
- [ ] `pip install -r requirements-voice.txt` succeeds
- [ ] ffmpeg on PATH (for WebM enrollment transcoding)
- [ ] Microphone permission granted to browser and Python

## First-run onboarding

- [ ] Config wizard completes
- [ ] Voice enrollment overlay appears
- [ ] Coqui unavailable shows install instructions (no silent stub pass)
- [ ] Record 15+ minutes of prompts (or lower threshold in dev config)
- [ ] Train model succeeds
- [ ] Test playback sounds intelligible
- [ ] Approve advances to personality interview
- [ ] Complete seed interview S1–S5
- [ ] Normal chat pipeline unblocks

## Runtime voice

- [ ] Transcript wake word works without openwakeword
- [ ] Whisper transcription works (if faster-whisper installed)
- [ ] TTS output uses cloned voice in chat responses

## Sign-off

| Field | Value |
|-------|-------|
| Tester | |
| Date | |
| Windows version | |
| Python version | |
| Coqui TTS version | |
| Result | PASS / FAIL |

Update [specs/platform-support.md](../specs/platform-support.md) Windows voice tier when PASS.
