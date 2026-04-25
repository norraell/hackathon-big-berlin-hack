"""Speech-to-Text module with support for multiple providers."""

from typing import Optional, Callable
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def get_stt_handler(
    language: Optional[str] = None,
    on_transcript: Optional[Callable[[str, float, str], None]] = None,
    on_final: Optional[Callable[[str, float, str], None]] = None,
):
    """Factory function to get the appropriate STT handler based on configuration.
    
    Args:
        language: Target language code (None for auto-detect)
        on_transcript: Callback for interim transcripts (text, confidence, language)
        on_final: Callback for final transcripts (text, confidence, language)
        
    Returns:
        STT handler instance (GeminiSTTHandler or GoogleCloudSTTHandler)
        
    Raises:
        ValueError: If unknown STT provider is configured
        RuntimeError: If the selected provider is not available
    """
    provider = settings.stt_provider.lower()
    
    if provider == "gemini":
        try:
            from app.stt.gemini_stt import GeminiSTTHandler
            logger.info("Using Gemini STT provider")
            return GeminiSTTHandler(language, on_transcript, on_final)
        except ImportError as e:
            raise RuntimeError(
                f"Gemini STT provider not available: {e}. "
                "Install with: pip install google-genai"
            ) from e
            
    elif provider == "google_cloud":
        try:
            from app.stt.google_cloud_stt import GoogleCloudSTTHandler
            logger.info("Using Google Cloud STT provider")
            return GoogleCloudSTTHandler(language, on_transcript, on_final)
        except ImportError as e:
            raise RuntimeError(
                f"Google Cloud STT provider not available: {e}. "
                "Install with: pip install google-cloud-speech"
            ) from e
            
    else:
        raise ValueError(
            f"Unknown STT provider: {provider}. "
            f"Valid options: 'gemini', 'google_cloud'"
        )


__all__ = ["get_stt_handler"]