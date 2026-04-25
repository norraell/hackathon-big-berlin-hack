"""Speech-to-Text module."""

import logging
from typing import Callable, Optional, Protocol

from app.config import settings
from app.stt.gemini_stt import GeminiSTTHandler
from app.stt.google_cloud_stt import GoogleCloudSTTHandler

logger = logging.getLogger(__name__)


class STTHandler(Protocol):
    """Protocol for supported STT handlers."""

    is_streaming: bool

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_audio(self, audio_chunk: bytes) -> None: ...


def get_stt_handler(
    language: Optional[str] = None,
    on_transcript: Optional[Callable[[str, float, str], None]] = None,
    on_final: Optional[Callable[[str, float, str], None]] = None,
) -> STTHandler:
    """Factory function to get the configured STT handler."""
    provider = settings.stt_provider.lower()
    
    if provider == "gemini":
        logger.info("Using Gemini STT provider")
        return GeminiSTTHandler(language, on_transcript, on_final)
    elif provider == "google_cloud":
        logger.info("Using Google Cloud STT provider")
        return GoogleCloudSTTHandler(language, on_transcript, on_final)
    else:
        logger.warning(f"Unknown STT provider '{provider}', defaulting to Gemini")
        return GeminiSTTHandler(language, on_transcript, on_final)


__all__ = ["GeminiSTTHandler", "GoogleCloudSTTHandler", "STTHandler", "get_stt_handler"]