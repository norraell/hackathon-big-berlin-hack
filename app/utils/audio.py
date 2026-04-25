"""Audio processing utilities for μ-law ↔ PCM conversion and resampling."""

import audioop
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def ulaw_to_pcm(ulaw_data: bytes, sample_width: int = 2) -> bytes:
    """Convert μ-law encoded audio to PCM.
    
    Twilio sends μ-law 8 kHz audio. We need to convert it to PCM
    for processing by STT services.
    
    Args:
        ulaw_data: μ-law encoded audio bytes
        sample_width: Target sample width in bytes (2 = 16-bit)
        
    Returns:
        PCM audio bytes
    """
    try:
        # Convert μ-law to linear PCM
        pcm_data = audioop.ulaw2lin(ulaw_data, sample_width)
        return pcm_data
    except Exception as e:
        logger.error(f"Error converting μ-law to PCM: {e}", exc_info=True)
        raise


def pcm_to_ulaw(pcm_data: bytes, sample_width: int = 2) -> bytes:
    """Convert PCM audio to μ-law encoding.
    
    TTS services return PCM audio. We need to convert it to μ-law
    for sending back to Twilio.
    
    Args:
        pcm_data: PCM audio bytes
        sample_width: Sample width in bytes (2 = 16-bit)
        
    Returns:
        μ-law encoded audio bytes
    """
    try:
        # Convert linear PCM to μ-law
        ulaw_data = audioop.lin2ulaw(pcm_data, sample_width)
        return ulaw_data
    except Exception as e:
        logger.error(f"Error converting PCM to μ-law: {e}", exc_info=True)
        raise


def resample_audio(
    audio_data: bytes,
    from_rate: int,
    to_rate: int,
    sample_width: int = 2,
) -> bytes:
    """Resample audio from one sample rate to another.
    
    Args:
        audio_data: Input audio bytes
        from_rate: Source sample rate (Hz)
        to_rate: Target sample rate (Hz)
        sample_width: Sample width in bytes (2 = 16-bit)
        
    Returns:
        Resampled audio bytes
    """
    if from_rate == to_rate:
        return audio_data
    
    try:
        # Use audioop for resampling
        resampled, _ = audioop.ratecv(
            audio_data,
            sample_width,
            1,  # mono
            from_rate,
            to_rate,
            None,
        )
        return resampled
    except Exception as e:
        logger.error(
            f"Error resampling audio from {from_rate}Hz to {to_rate}Hz: {e}",
            exc_info=True,
        )
        raise


def convert_twilio_to_stt(ulaw_data: bytes) -> bytes:
    """Convert Twilio audio (μ-law 8kHz) to STT format (PCM 16kHz).
    
    This is a convenience function that combines μ-law decoding
    and resampling in one step.
    
    Args:
        ulaw_data: μ-law encoded audio from Twilio
        
    Returns:
        PCM 16kHz audio for STT
    """
    # Convert μ-law to PCM
    pcm_8khz = ulaw_to_pcm(ulaw_data)
    
    # Resample from 8kHz to 16kHz
    pcm_16khz = resample_audio(pcm_8khz, 8000, 16000)
    
    return pcm_16khz


def convert_tts_to_twilio(pcm_data: bytes, tts_rate: int = 24000) -> bytes:
    """Convert TTS audio (PCM 24kHz) to Twilio format (μ-law 8kHz).
    
    This is a convenience function that combines resampling
    and μ-law encoding in one step.
    
    Args:
        pcm_data: PCM audio from TTS
        tts_rate: TTS sample rate (default 24kHz for Gradium)
        
    Returns:
        μ-law 8kHz audio for Twilio
    """
    # Resample from TTS rate to 8kHz
    pcm_8khz = resample_audio(pcm_data, tts_rate, 8000)
    
    # Convert PCM to μ-law
    ulaw_data = pcm_to_ulaw(pcm_8khz)
    
    return ulaw_data


def calculate_audio_duration(
    audio_data: bytes,
    sample_rate: int,
    sample_width: int = 2,
) -> float:
    """Calculate the duration of audio data in seconds.
    
    Args:
        audio_data: Audio bytes
        sample_rate: Sample rate in Hz
        sample_width: Sample width in bytes (2 = 16-bit)
        
    Returns:
        Duration in seconds
    """
    num_samples = len(audio_data) // sample_width
    duration = num_samples / sample_rate
    return duration


def detect_silence(
    audio_data: bytes,
    sample_width: int = 2,
    threshold: int = 500,
) -> bool:
    """Detect if audio data is mostly silence.
    
    Args:
        audio_data: Audio bytes
        sample_width: Sample width in bytes
        threshold: RMS threshold for silence detection
        
    Returns:
        True if audio is silent
    """
    try:
        rms = audioop.rms(audio_data, sample_width)
        return rms < threshold
    except Exception as e:
        logger.error(f"Error detecting silence: {e}", exc_info=True)
        return False


def apply_gain(
    audio_data: bytes,
    sample_width: int,
    gain_factor: float,
) -> bytes:
    """Apply gain to audio data.
    
    Args:
        audio_data: Audio bytes
        sample_width: Sample width in bytes
        gain_factor: Gain multiplier (1.0 = no change, 2.0 = double volume)
        
    Returns:
        Audio with gain applied
    """
    try:
        return audioop.mul(audio_data, sample_width, gain_factor)
    except Exception as e:
        logger.error(f"Error applying gain: {e}", exc_info=True)
        raise


def mix_audio(
    audio1: bytes,
    audio2: bytes,
    sample_width: int = 2,
) -> bytes:
    """Mix two audio streams together.
    
    Args:
        audio1: First audio stream
        audio2: Second audio stream
        sample_width: Sample width in bytes
        
    Returns:
        Mixed audio
    """
    try:
        # Ensure both streams are the same length
        min_len = min(len(audio1), len(audio2))
        audio1 = audio1[:min_len]
        audio2 = audio2[:min_len]
        
        return audioop.add(audio1, audio2, sample_width)
    except Exception as e:
        logger.error(f"Error mixing audio: {e}", exc_info=True)
        raise


class AudioBuffer:
    """Buffer for accumulating audio chunks."""
    
    def __init__(self, sample_rate: int = 8000, sample_width: int = 2) -> None:
        """Initialize audio buffer.
        
        Args:
            sample_rate: Sample rate in Hz
            sample_width: Sample width in bytes
        """
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.buffer = bytearray()
    
    def add(self, audio_data: bytes) -> None:
        """Add audio data to buffer.
        
        Args:
            audio_data: Audio bytes to add
        """
        self.buffer.extend(audio_data)
    
    def get(self, num_bytes: Optional[int] = None) -> bytes:
        """Get audio data from buffer.
        
        Args:
            num_bytes: Number of bytes to get (None = all)
            
        Returns:
            Audio bytes
        """
        if num_bytes is None:
            data = bytes(self.buffer)
            self.buffer.clear()
            return data
        else:
            data = bytes(self.buffer[:num_bytes])
            self.buffer = self.buffer[num_bytes:]
            return data
    
    def get_duration(self) -> float:
        """Get duration of buffered audio in seconds.
        
        Returns:
            Duration in seconds
        """
        return calculate_audio_duration(
            bytes(self.buffer),
            self.sample_rate,
            self.sample_width,
        )
    
    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()
    
    def __len__(self) -> int:
        """Get buffer size in bytes."""
        return len(self.buffer)