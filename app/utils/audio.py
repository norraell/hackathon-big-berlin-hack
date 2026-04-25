"""Audio codec, resampling, and voice-activity helpers.

The voice path crosses three sample rates:

* **Twilio Media Streams**: μ-law @ 8 kHz mono (G.711)
* **Gemini STT**: 16-bit PCM @ 16 kHz mono
* **Gradium TTS**: 16-bit PCM @ 24 kHz mono (we request ``pcm_24000``)

This module is the only place that knows about codec/sample-rate conversion;
everything else operates on PCM ``bytes`` (16-bit signed little-endian) or
ndarray buffers. ``audioop`` is preferred where available; a NumPy fallback
covers Python 3.13+ where ``audioop`` was removed from the stdlib.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

try:  # Python 3.13 removed audioop from the stdlib.
    import audioop  # type: ignore[import-not-found]

    _HAVE_AUDIOOP = True
except ImportError:  # pragma: no cover — exercised only on 3.13+
    audioop = None  # type: ignore[assignment]
    _HAVE_AUDIOOP = False


PCM_SAMPLE_WIDTH: Final[int] = 2  # 16-bit signed
TWILIO_RATE: Final[int] = 8_000
STT_RATE: Final[int] = 16_000
GRADIUM_RATE: Final[int] = 24_000


# ---------------------------------------------------------------------------
# μ-law ↔ PCM
# ---------------------------------------------------------------------------

def mulaw_to_pcm16(mulaw: bytes) -> bytes:
    """Decode μ-law (G.711) bytes to 16-bit signed-LE PCM."""
    if _HAVE_AUDIOOP:
        return audioop.ulaw2lin(mulaw, PCM_SAMPLE_WIDTH)  # type: ignore[union-attr]
    return _mulaw_to_pcm_numpy(mulaw)


def pcm16_to_mulaw(pcm: bytes) -> bytes:
    """Encode 16-bit signed-LE PCM bytes to μ-law (G.711)."""
    if _HAVE_AUDIOOP:
        return audioop.lin2ulaw(pcm, PCM_SAMPLE_WIDTH)  # type: ignore[union-attr]
    return _pcm_to_mulaw_numpy(pcm)


def _mulaw_to_pcm_numpy(mulaw: bytes) -> bytes:
    # ITU-T G.711 μ-law expansion. Standard reference implementation.
    mu = np.frombuffer(mulaw, dtype=np.uint8).astype(np.int16)
    mu = ~mu & 0xFF
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = ((mantissa.astype(np.int32) << 3) + 0x84) << exponent.astype(np.int32)
    sample = sample - 0x84
    sample = np.where(sign != 0, -sample, sample)
    return sample.astype("<i2").tobytes()


def _pcm_to_mulaw_numpy(pcm: bytes) -> bytes:
    BIAS = 0x84
    CLIP = 32635
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.int32)
    sign = ((samples >> 8) & 0x80).astype(np.uint8)
    samples = np.where(sign != 0, -samples, samples)
    samples = np.clip(samples, 0, CLIP) + BIAS
    # exponent = floor(log2(sample >> 7)) clipped into [0, 7]
    shifted = (samples >> 7).astype(np.int32)
    exponent = np.zeros_like(shifted, dtype=np.uint8)
    for exp in range(7, 0, -1):
        mask = shifted >= (1 << exp)
        exponent = np.where((exponent == 0) & mask, exp, exponent)
    mantissa = ((samples >> (exponent.astype(np.int32) + 3)) & 0x0F).astype(np.uint8)
    ulaw = ~(sign | (exponent << 4) | mantissa) & 0xFF
    return ulaw.astype(np.uint8).tobytes()


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------

def resample_pcm16(pcm: bytes, *, src_rate: int, dst_rate: int) -> bytes:
    """Resample 16-bit signed-LE PCM between sample rates.

    Uses ``audioop.ratecv`` when available (high-quality, low-overhead),
    otherwise a linear-interpolation NumPy fallback. The fallback is good
    enough for telephony (8 kHz target) but not audiophile-grade.
    """
    if src_rate == dst_rate:
        return pcm
    if _HAVE_AUDIOOP:
        converted, _state = audioop.ratecv(  # type: ignore[union-attr]
            pcm, PCM_SAMPLE_WIDTH, 1, src_rate, dst_rate, None
        )
        return converted
    return _resample_linear_numpy(pcm, src_rate, dst_rate)


def _resample_linear_numpy(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    if samples.size == 0:
        return b""
    duration = samples.size / src_rate
    n_out = max(1, int(math.floor(duration * dst_rate)))
    src_idx = np.linspace(0.0, samples.size - 1.0, num=n_out, dtype=np.float32)
    lo = np.floor(src_idx).astype(np.int32)
    hi = np.minimum(lo + 1, samples.size - 1)
    frac = src_idx - lo
    out = (1.0 - frac) * samples[lo] + frac * samples[hi]
    return np.clip(out, -32768, 32767).astype("<i2").tobytes()


# Convenience aliases for the two paths we actually use.
def upsample_8k_to_16k(pcm: bytes) -> bytes:
    """Upsample 8 kHz PCM → 16 kHz PCM (Twilio → Gemini STT)."""
    return resample_pcm16(pcm, src_rate=TWILIO_RATE, dst_rate=STT_RATE)


def downsample_24k_to_8k(pcm: bytes) -> bytes:
    """Downsample 24 kHz PCM → 8 kHz PCM (Gradium TTS → Twilio)."""
    return resample_pcm16(pcm, src_rate=GRADIUM_RATE, dst_rate=TWILIO_RATE)


# ---------------------------------------------------------------------------
# Voice activity detection
# ---------------------------------------------------------------------------

# Default RMS threshold for 16-bit PCM. Calibrated empirically against quiet
# Twilio frames (background hiss is ~150–250 RMS); 500 catches voiced audio
# without firing on line noise. Tune via the function arg in handler code.
_DEFAULT_VAD_RMS_THRESHOLD: Final[float] = 500.0


def is_voiced(pcm: bytes, *, threshold: float = _DEFAULT_VAD_RMS_THRESHOLD) -> bool:
    """Energy-based VAD over a PCM frame.

    Returns ``True`` if the RMS amplitude exceeds ``threshold``. Cheap and
    good enough for barge-in detection on a telephony stream; replace with
    ``webrtcvad`` if false positives become a problem.
    """
    if not pcm:
        return False
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    if samples.size == 0:
        return False
    rms = float(np.sqrt(np.mean(np.square(samples))))
    return rms >= threshold
