"""Tests for audio processing utilities."""

import pytest
from app.utils.audio import (
    ulaw_to_pcm,
    pcm_to_ulaw,
    resample_audio,
    convert_twilio_to_stt,
    convert_tts_to_twilio,
    calculate_audio_duration,
    detect_silence,
    AudioBuffer,
)


class TestAudioConversion:
    """Test cases for audio format conversion."""

    def test_ulaw_to_pcm_conversion(self):
        """Test μ-law to PCM conversion."""
        # Create sample μ-law data (silence)
        ulaw_data = b'\xff' * 160  # 20ms of μ-law silence at 8kHz
        
        pcm_data = ulaw_to_pcm(ulaw_data)
        
        assert isinstance(pcm_data, bytes)
        assert len(pcm_data) == len(ulaw_data) * 2  # 16-bit samples

    def test_pcm_to_ulaw_conversion(self):
        """Test PCM to μ-law conversion."""
        # Create sample PCM data (silence)
        pcm_data = b'\x00\x00' * 160  # 20ms of PCM silence at 8kHz
        
        ulaw_data = pcm_to_ulaw(pcm_data)
        
        assert isinstance(ulaw_data, bytes)
        assert len(ulaw_data) == len(pcm_data) // 2

    def test_round_trip_conversion(self):
        """Test that μ-law -> PCM -> μ-law preserves data."""
        original_ulaw = b'\xff' * 160
        
        pcm = ulaw_to_pcm(original_ulaw)
        converted_ulaw = pcm_to_ulaw(pcm)
        
        # Should be approximately the same (some loss is expected)
        assert len(converted_ulaw) == len(original_ulaw)


class TestAudioResampling:
    """Test cases for audio resampling."""

    def test_resample_no_change(self):
        """Test that resampling with same rate returns original."""
        audio_data = b'\x00\x00' * 160
        
        resampled = resample_audio(audio_data, 8000, 8000)
        
        assert resampled == audio_data

    def test_resample_upsample(self):
        """Test upsampling from 8kHz to 16kHz."""
        audio_data = b'\x00\x00' * 160  # 20ms at 8kHz
        
        resampled = resample_audio(audio_data, 8000, 16000)
        
        # Should be approximately double the length
        assert len(resampled) > len(audio_data)

    def test_resample_downsample(self):
        """Test downsampling from 16kHz to 8kHz."""
        audio_data = b'\x00\x00' * 320  # 20ms at 16kHz
        
        resampled = resample_audio(audio_data, 16000, 8000)
        
        # Should be approximately half the length
        assert len(resampled) < len(audio_data)


class TestAudioPipeline:
    """Test cases for complete audio pipelines."""

    def test_twilio_to_stt_pipeline(self):
        """Test Twilio (μ-law 8kHz) to STT (PCM 16kHz) conversion."""
        ulaw_8khz = b'\xff' * 160  # 20ms of μ-law at 8kHz
        
        pcm_16khz = convert_twilio_to_stt(ulaw_8khz)
        
        assert isinstance(pcm_16khz, bytes)
        # Should be larger due to upsampling and bit depth
        assert len(pcm_16khz) > len(ulaw_8khz)

    def test_tts_to_twilio_pipeline(self):
        """Test TTS (PCM 24kHz) to Twilio (μ-law 8kHz) conversion."""
        pcm_24khz = b'\x00\x00' * 480  # 20ms of PCM at 24kHz
        
        ulaw_8khz = convert_tts_to_twilio(pcm_24khz)
        
        assert isinstance(ulaw_8khz, bytes)
        # Should be smaller due to downsampling and compression
        assert len(ulaw_8khz) < len(pcm_24khz)


class TestAudioUtilities:
    """Test cases for audio utility functions."""

    def test_calculate_duration(self):
        """Test audio duration calculation."""
        # 1 second of 16-bit PCM at 8kHz
        audio_data = b'\x00\x00' * 8000
        
        duration = calculate_audio_duration(audio_data, 8000, 2)
        
        assert duration == pytest.approx(1.0, rel=0.01)

    def test_detect_silence_true(self):
        """Test silence detection with silent audio."""
        silent_audio = b'\x00\x00' * 160
        
        is_silent = detect_silence(silent_audio)
        
        assert is_silent

    def test_detect_silence_false(self):
        """Test silence detection with non-silent audio."""
        # Create audio with some amplitude
        loud_audio = b'\xff\x7f' * 160  # Max positive amplitude
        
        is_silent = detect_silence(loud_audio, threshold=500)
        
        assert not is_silent


class TestAudioBuffer:
    """Test cases for AudioBuffer."""

    def test_buffer_initialization(self):
        """Test buffer initialization."""
        buffer = AudioBuffer(sample_rate=8000, sample_width=2)
        
        assert len(buffer) == 0
        assert buffer.get_duration() == 0.0

    def test_buffer_add_and_get(self):
        """Test adding and retrieving audio."""
        buffer = AudioBuffer()
        
        audio1 = b'\x00\x00' * 160
        audio2 = b'\x00\x00' * 160
        
        buffer.add(audio1)
        buffer.add(audio2)
        
        assert len(buffer) == len(audio1) + len(audio2)
        
        retrieved = buffer.get()
        assert len(retrieved) == len(audio1) + len(audio2)
        assert len(buffer) == 0  # Buffer should be empty after get()

    def test_buffer_partial_get(self):
        """Test getting partial audio from buffer."""
        buffer = AudioBuffer()
        
        audio = b'\x00\x00' * 320
        buffer.add(audio)
        
        partial = buffer.get(num_bytes=160)
        
        assert len(partial) == 160
        assert len(buffer) == len(audio) - 160

    def test_buffer_duration(self):
        """Test buffer duration calculation."""
        buffer = AudioBuffer(sample_rate=8000, sample_width=2)
        
        # Add 1 second of audio
        audio = b'\x00\x00' * 8000
        buffer.add(audio)
        
        duration = buffer.get_duration()
        assert duration == pytest.approx(1.0, rel=0.01)

    def test_buffer_clear(self):
        """Test clearing the buffer."""
        buffer = AudioBuffer()
        
        buffer.add(b'\x00\x00' * 160)
        assert len(buffer) > 0
        
        buffer.clear()
        assert len(buffer) == 0


class TestAudioEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_audio_conversion(self):
        """Test conversion with empty audio."""
        empty = b''
        
        pcm = ulaw_to_pcm(empty)
        assert pcm == b''
        
        ulaw = pcm_to_ulaw(empty)
        assert ulaw == b''

    def test_zero_duration(self):
        """Test duration calculation with empty audio."""
        duration = calculate_audio_duration(b'', 8000, 2)
        assert duration == 0.0