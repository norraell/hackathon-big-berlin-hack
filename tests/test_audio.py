"""Audio codec / resampling tests.

We do *not* require sample-accurate fidelity — μ-law is lossy and
``audioop.ratecv`` introduces small artifacts. The bar is "round-trip
preserves shape and amplitude within tolerance".
"""

from __future__ import annotations

import math

import numpy as np

from app.utils import audio as au


def _sine_pcm(rate: int, freq: float = 440.0, dur_s: float = 0.05, amplitude: float = 0.5) -> bytes:
    """Return ``dur_s`` of a sine wave as 16-bit signed-LE PCM bytes."""
    n = int(rate * dur_s)
    t = np.arange(n, dtype=np.float64) / rate
    samples = np.sin(2 * math.pi * freq * t) * amplitude * 32767.0
    return samples.astype("<i2").tobytes()


def _rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    s = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    return float(np.sqrt(np.mean(np.square(s))))


def test_mulaw_roundtrip_preserves_amplitude_within_tolerance() -> None:
    pcm = _sine_pcm(au.TWILIO_RATE, freq=300.0)
    encoded = au.pcm16_to_mulaw(pcm)
    decoded = au.mulaw_to_pcm16(encoded)

    # Same number of samples.
    assert len(decoded) == len(pcm)

    # μ-law is lossy; RMS shift should be small relative to original.
    orig_rms = _rms(pcm)
    new_rms = _rms(decoded)
    assert orig_rms > 0
    assert abs(new_rms - orig_rms) / orig_rms < 0.10  # within 10%


def test_downsample_24k_to_8k_produces_third_the_samples() -> None:
    pcm = _sine_pcm(au.GRADIUM_RATE, freq=300.0, dur_s=0.1)
    out = au.downsample_24k_to_8k(pcm)

    in_samples = len(pcm) // au.PCM_SAMPLE_WIDTH
    out_samples = len(out) // au.PCM_SAMPLE_WIDTH
    expected = in_samples // 3

    # ratecv may differ by a small handful of samples around the edges.
    assert abs(out_samples - expected) <= 4

    # Energy should survive the downsample (a 300 Hz tone is well below the
    # 4 kHz Nyquist of 8 kHz, so no significant content is lost).
    assert _rms(out) > 0.5 * _rms(pcm)


def test_upsample_8k_to_16k_doubles_the_samples() -> None:
    pcm = _sine_pcm(au.TWILIO_RATE, freq=300.0, dur_s=0.05)
    out = au.upsample_8k_to_16k(pcm)

    in_samples = len(pcm) // au.PCM_SAMPLE_WIDTH
    out_samples = len(out) // au.PCM_SAMPLE_WIDTH
    assert abs(out_samples - 2 * in_samples) <= 4


def test_vad_detects_voiced_audio_and_rejects_silence() -> None:
    voiced = _sine_pcm(au.TWILIO_RATE, freq=300.0, amplitude=0.5)
    silence = (np.zeros(400, dtype="<i2")).tobytes()
    assert au.is_voiced(voiced) is True
    assert au.is_voiced(silence) is False
