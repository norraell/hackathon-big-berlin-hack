"""Google Gemini streaming Speech-to-Text wrapper."""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiSTTHandler:
    """Handles streaming speech-to-text using Google Gemini.
    
    This class manages:
    - Streaming audio to Gemini's STT API
    - Processing transcription results
    - Language detection
    - Confidence scoring
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
        
        # Gemini client (to be initialized)
        self.client = None
        self.stream = None
        
        # Transcription state
        self.current_transcript = ""
        self.current_confidence = 0.0
        self.detected_language = self.language
        self.low_confidence_count = 0
        
        logger.info(f"GeminiSTTHandler initialized with language: {self.language}")

    async def start(self) -> None:
        """Start the STT streaming session."""
        logger.info("Starting Gemini STT stream")
        
        try:
            # TODO: Initialize Gemini client
            # import google.generativeai as genai
            # genai.configure(api_key=settings.gemini_api_key)
            # self.client = genai.GenerativeModel('gemini-2.0-flash')
            
            self.is_streaming = True
            
            # Start processing tasks
            send_task = asyncio.create_task(self._send_audio())
            receive_task = asyncio.create_task(self._receive_transcripts())
            
            # Store tasks for cleanup
            self.tasks = [send_task, receive_task]
            
            logger.info("Gemini STT stream started")
            
        except Exception as e:
            logger.error(f"Error starting Gemini STT: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the STT streaming session."""
        logger.info("Stopping Gemini STT stream")
        
        self.is_streaming = False
        
        # Cancel tasks
        if hasattr(self, 'tasks'):
            for task in self.tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close stream
        if self.stream:
            # TODO: Close Gemini stream
            pass
        
        logger.info("Gemini STT stream stopped")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to the STT service.
        
        Args:
            audio_chunk: PCM audio data (16 kHz, 16-bit)
        """
        if not self.is_streaming:
            logger.warning("Attempted to send audio while not streaming")
            return
            
        await self.audio_queue.put(audio_chunk)

    async def _send_audio(self) -> None:
        """Internal task to send audio from queue to Gemini."""
        try:
            while self.is_streaming:
                audio_chunk = await self.audio_queue.get()
                
                # TODO: Send audio to Gemini stream
                # await self.stream.send(audio_chunk)
                
                logger.debug(f"Sent {len(audio_chunk)} bytes to Gemini STT")
                
        except asyncio.CancelledError:
            logger.info("Audio sending task cancelled")
        except Exception as e:
            logger.error(f"Error sending audio to Gemini: {e}", exc_info=True)

    async def _receive_transcripts(self) -> None:
        """Internal task to receive transcripts from Gemini."""
        try:
            while self.is_streaming:
                # TODO: Receive from Gemini stream
                # async for response in self.stream:
                #     await self._process_response(response)
                
                # Placeholder: simulate receiving transcripts
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info("Transcript receiving task cancelled")
        except Exception as e:
            logger.error(f"Error receiving transcripts from Gemini: {e}", exc_info=True)

    async def _process_response(self, response: dict) -> None:
        """Process a transcription response from Gemini.
        
        Args:
            response: Response from Gemini STT
        """
        # TODO: Parse actual Gemini response format
        # This is a placeholder structure
        
        is_final = response.get("is_final", False)
        transcript = response.get("transcript", "")
        confidence = response.get("confidence", 0.0)
        language = response.get("language", self.language)
        
        if not transcript:
            return
        
        # Update detected language
        if language != self.detected_language:
            logger.info(f"Language changed from {self.detected_language} to {language}")
            self.detected_language = language
        
        # Track low confidence
        if confidence < settings.max_stt_confidence_threshold:
            self.low_confidence_count += 1
            logger.warning(
                f"Low confidence transcript: {confidence:.2f} "
                f"(count: {self.low_confidence_count})"
            )
        else:
            self.low_confidence_count = 0
        
        if is_final:
            # Final transcript
            self.current_transcript = transcript
            self.current_confidence = confidence
            
            logger.info(
                f"Final transcript: '{transcript}' "
                f"(confidence: {confidence:.2f}, language: {language})"
            )
            
            if self.on_final:
                self.on_final(transcript, confidence, language)
                
            # Reset for next utterance
            self.current_transcript = ""
            self.current_confidence = 0.0
            
        else:
            # Interim transcript
            self.current_transcript = transcript
            self.current_confidence = confidence
            
            logger.debug(
                f"Interim transcript: '{transcript}' "
                f"(confidence: {confidence:.2f})"
            )
            
            if self.on_transcript:
                self.on_transcript(transcript, confidence, language)

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