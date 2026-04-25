# Audio pipeline

The voice path crosses **three sample rates** and **two codecs**, with a
hard real-time constraint (≤ 1500 ms p95 end-of-user-speech →
start-of-agent-audio). All codec and resampling logic is centralized in
`app/utils/audio.py` so the rest of the codebase only ever sees raw
16-bit signed-LE PCM bytes.

## Sample rates and codecs

| Hop | Codec | Sample rate |
|---|---|---|
| Twilio Media Streams (caller ↔ us) | μ-law (G.711) | 8 kHz mono |
| Gemini STT input | 16-bit signed-LE PCM | 16 kHz mono |
| Gradium TTS output | 16-bit signed-LE PCM | 24 kHz mono |

Conversions:

```
inbound  : Twilio μ-law 8 kHz ──ulaw2lin──► PCM 8 kHz ──upsample──► PCM 16 kHz ──► Gemini STT
outbound : Gradium PCM 24 kHz ──downsample──► PCM 8 kHz ──lin2ulaw──► μ-law 8 kHz ──► Twilio
```

## API surface

| Function | Purpose |
|---|---|
| `mulaw_to_pcm16(mulaw)` | Decode G.711 μ-law → PCM16-LE |
| `pcm16_to_mulaw(pcm)` | Encode PCM16-LE → G.711 μ-law |
| `resample_pcm16(pcm, src_rate, dst_rate)` | Generic resample |
| `upsample_8k_to_16k(pcm)` | Convenience: Twilio → STT |
| `downsample_24k_to_8k(pcm)` | Convenience: TTS → Twilio |
| `is_voiced(pcm, *, threshold=500.0)` | Energy-based VAD over a PCM frame |

Constants:

- `PCM_SAMPLE_WIDTH = 2` (16-bit)
- `TWILIO_RATE = 8_000`, `STT_RATE = 16_000`, `GRADIUM_RATE = 24_000`

## Backends

`audioop` is preferred (high-quality, zero-allocation). Python 3.13
removed `audioop` from the stdlib; we ship a NumPy fallback for both
μ-law transcoding and resampling. The fallback resampler is
linear-interpolation — good enough for telephony (8 kHz target, narrow
band) but not audiophile.

```python
try:
    import audioop
    _HAVE_AUDIOOP = True
except ImportError:
    _HAVE_AUDIOOP = False
```

The public functions transparently pick the backend.

## Voice activity detection (barge-in)

`is_voiced(pcm, threshold=500.0)` is the cheapest VAD that works on
telephony audio: RMS over a frame, compared to a threshold. Calibrated
against Twilio frames empirically — background hiss is ~150–250 RMS, so
500 catches voiced audio without firing on line noise.

The orchestrator runs VAD on every inbound frame **only while TTS is
active**. If a frame is voiced while TTS is producing, we treat it as a
barge-in:

1. `tts.interrupt()` — Gradium-side abort.
2. Drain the outbound audio queue immediately (do not play any more
   buffered audio).
3. Truncate the in-flight agent turn at the **last completed word**
   (using the word timings recorded by `_pump_word_timings`). The
   resulting `Turn.text` reflects what the caller actually heard.

The 200 ms barge-in budget (CLAUDE.md §5.2) is met by biasing toward
flush-and-truncate rather than waiting for SDK ack on `interrupt()`.

If false positives become a problem on noisier lines, swap `is_voiced`
for `webrtcvad` — same one-call interface, better discrimination.

## Frame sizing

Outbound audio is sent in **160-byte μ-law chunks (~20 ms)**, defined as
`_OUTBOUND_FRAME_BYTES` in the orchestrator:

- Smaller (e.g. 80 bytes / 10 ms) — more WS-frame overhead, more CPU.
- Larger (e.g. 320 bytes / 40 ms) — perceptible jitter under load.

A trailing partial chunk at end-of-utterance is sent as-is (Twilio
tolerates short final frames).

## Round-trip fidelity

μ-law is lossy. The audio test (`tests/test_audio.py`) asserts only that
round-trips preserve **shape and amplitude within tolerance**:

- μ-law round-trip: RMS shift < 10% of original.
- 24 kHz → 8 kHz downsample: sample count within ±4 of `n / 3`; energy
  preserved (a 300 Hz tone is well below the 4 kHz Nyquist of 8 kHz).
- 8 kHz → 16 kHz upsample: sample count within ±4 of `2n`.

Sample-accurate fidelity is **not** a requirement.

## Why centralize?

Codec and rate conversions are easy to get wrong (endianness, sample
width, off-by-one on rate boundaries). One file, one set of tests, one
place to swap implementations (e.g. moving to `webrtcvad` for VAD or
`librosa` for high-quality resampling) is the right tradeoff for a
real-time voice pipeline.
