"""Google Gemini Speech-to-Text wrapper using batch processing."""

import asyncio
import logging
import base64
import io
from typing import Optional, Callable, Any
from app.config import settings

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class GeminiSTTHandler:
    """Handles speech-to-text using Google Gemini with batch audio processing.
    
    Note: This uses Gemini's multimodal capabilities to transcribe audio.
    It processes audio in chunks rather than true streaming.
    """

    def __init__(
        self,
        language: Optional[str] = None,
        on_transcript: Optional[Callable[[str, float, str], None]] = None,
        on_final: Optional[Callable[[str, float, str], None]] = None,
    ) -> None:
        """Initialize the Gemini STT handler.
        
        Args:
            language: Target language code (None for auto-detect)
            on_transcript: Callback for interim transcripts (text, confidence, language)
            on_final: Callback for final transcripts (text, confidence, language)
        """
        self.language = language or settings.default_language
        self.on_transcript = on_transcript
        self.on_final = on_final
        
        self.is_streaming = False
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.audio_buffer = bytearray()
        
        # Gemini model
        self.model: Any = None
        
        # Transcription state
        self.current_transcript = ""
        self.current_confidence = 0.8  # Default confidence for Gemini
        self.detected_language = self.language
        self.low_confidence_count = 0
        
        # Processing parameters
        self.chunk_duration_ms = 3000  # Process every 3 seconds
        self.sample_rate = 16000
        self.sample_width = 2  # 16-bit
        
        logger.info(f"GeminiSTTHandler initialized with language: {self.language}")

    async def start(self) -> None:
        """Start the STT processing session."""
        logger.info("Starting Gemini STT (batch processing mode)")
        
        if not GENAI_AVAILABLE or genai is None:
            logger.error("google-genai package not installed")
            raise RuntimeError(
                "google-genai package not installed. "
                "Install with: pip install google-genai"
            )
        
        try:
            # Create Gemini client
            client = genai.Client(api_key=settings.gemini_api_key)
            
            # Store client for later use
            self.model = client
            
            logger.info(
                f"✓ Gemini client initialized for audio transcription: "
                f"{settings.gemini_stt_model_name}"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise RuntimeError(f"Failed to initialize Gemini: {e}") from e
        
        self.is_streaming = True
        
        # Start processing task
        process_task = asyncio.create_task(self._process_audio())
        self.tasks = [process_task]
        
        logger.info("Gemini STT started successfully (batch mode)")
                

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self.is_streaming = False
        
        # Cancel tasks
        if hasattr(self, 'tasks'):
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        
        self.model = None

    async def stop(self) -> None:
        """Stop the STT processing session."""
        logger.info("Stopping Gemini STT")
        await self._cleanup()
        logger.info("Gemini STT stopped")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to the STT service.
        
        Args:
            audio_chunk: PCM audio data (16 kHz, 16-bit)
        """
        if not self.is_streaming:
            logger.warning("Attempted to send audio while not streaming")
            return
            
        # Add to buffer
        self.audio_buffer.extend(audio_chunk)

    async def _process_audio(self) -> None:
        """Process accumulated audio chunks using Gemini."""
        try:
            while self.is_streaming:
                await asyncio.sleep(self.chunk_duration_ms / 1000.0)
                
                if len(self.audio_buffer) == 0:
                    continue
                
                # Get accumulated audio
                audio_data = bytes(self.audio_buffer)
                self.audio_buffer.clear()
                
                # Convert PCM to base64 for Gemini
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                try:
                    # Create prompt for transcription
                    prompt = f"Transcribe this audio in {self.language}. Only return the transcription text, nothing else."
                    
                    # Send to Gemini using new API
                    if not GENAI_AVAILABLE or genai is None or types is None:
                        logger.error("Gemini client not available")
                        continue
                    
                    if not isinstance(self.model, genai.Client):
                        logger.error("Model is not a valid Gemini client")
                        continue
                    
                    response = await asyncio.to_thread(
                        self.model.models.generate_content,
                        model=settings.gemini_stt_model_name,
                        contents=[
                            prompt,
                            types.Part.from_bytes(
                                data=audio_data,
                                mime_type="audio/pcm"
                            )
                        ]
                    )
                    
                    if response and response.text:
                        transcript = response.text.strip()
                        
                        if transcript:
                            logger.info(f"Transcribed: '{transcript}'")
                            
                            # Call final callback
                            if self.on_final:
                                self.on_final(transcript, self.current_confidence, self.language)
                            
                except Exception as e:
                    logger.error(f"Error transcribing audio: {e}", exc_info=True)
                    
        except asyncio.CancelledError:
            logger.info("Audio processing task cancelled")
        except Exception as e:
            logger.error(f"Error in audio processing: {e}", exc_info=True)
            self.is_streaming = False

    def get_current_transcript(self) -> tuple[str, float, str]:
        """Get the current transcript state.
        
        Returns:
            Tuple of (transcript, confidence, language)
        """
        return (
            self.current_transcript,
            self.current_confidence,
            self.detected_language,
        )

    def should_escalate_to_human(self) -> bool:
        """Check if we should escalate to human due to low confidence.
        
        Returns:
            True if low confidence count exceeds threshold
        """
        return self.low_confidence_count >= 2

    async def change_language(self, language: str) -> None:
        """Change the target language for transcription.
        
        Args:
            language: New language code
        """
        if language not in settings.supported_languages:
            logger.warning(
                f"Language {language} not in supported languages: "
                f"{settings.supported_languages}"
            )
            return
        
        logger.info(f"Changing STT language from {self.language} to {language}")
        
        # Stop current stream
        await self.stop()
        
        # Update language
        self.language = language
        self.detected_language = language
        
        # Restart stream with new language
        await self.start()