"""Google Gemini streaming Speech-to-Text wrapper."""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable
from contextlib import asynccontextmanager

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
        self._session = None
        self._session_ctx = None
        
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
            # Import and configure Gemini
            try:
                from google import genai
                from google.genai import types
                from google.genai.types import Modality
            except ImportError as e:
                logger.error(f"Failed to import google.genai: {e}")
                raise RuntimeError(
                    "google-generativeai package not properly installed. "
                    "Please ensure you have the correct version installed."
                ) from e
            
            # Configure the client
            try:
                self.client = genai.Client(api_key=settings.gemini_api_key)
            except Exception as e:
                logger.error(f"Failed to create Gemini client: {e}")
                raise RuntimeError(
                    f"Failed to initialize Gemini client. Check your API key. Error: {e}"
                ) from e
            
            # Configure live session with proper error handling
            try:
                config = types.LiveConnectConfig(
                    response_modalities=[Modality.AUDIO],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Puck"
                            )
                        )
                    ),
                )
                
                # Create session context
                self._session_ctx = self.client.aio.live.connect(
                    model="models/gemini-2.5-flash-native-audio-latest",
                    config=config
                )
                
                # Enter the context to get the session
                self._session = await self._session_ctx.__aenter__()
                
            except Exception as e:
                logger.error(f"Failed to create Gemini Live session: {e}", exc_info=True)
                
                # Check for common error causes
                error_msg = str(e)
                if "1011" in error_msg or "Internal error" in error_msg:
                    raise RuntimeError(
                        "Gemini Live API returned internal error (1011). This may be due to:\n"
                        "1. API not available in your region\n"
                        "2. Invalid API key or insufficient permissions\n"
                        "3. Model 'gemini-2.5-flash-native-audio-latest' not accessible\n"
                        "4. Live API not enabled for your account\n"
                        "Please check your Gemini API configuration and try:\n"
                        "- Verifying your API key at https://aistudio.google.com/apikey\n"
                        "- Ensuring Live API access is enabled\n"
                        "- Trying a different model if available"
                    ) from e
                else:
                    raise RuntimeError(f"Failed to connect to Gemini Live API: {e}") from e
            
            self.is_streaming = True
            
            # Start processing tasks
            send_task = asyncio.create_task(self._send_audio())
            receive_task = asyncio.create_task(self._receive_transcripts())
            
            # Store tasks for cleanup
            self.tasks = [send_task, receive_task]
            
            logger.info("Gemini STT stream started successfully")
            
        except Exception as e:
            logger.error(f"Error starting Gemini STT: {e}", exc_info=True)
            # Clean up on error
            await self._cleanup()
            raise

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
        
        # Close session
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Gemini session: {e}")
            finally:
                self._session = None
                self._session_ctx = None

    async def stop(self) -> None:
        """Stop the STT streaming session."""
        logger.info("Stopping Gemini STT stream")
        await self._cleanup()
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
            while self.is_streaming and self._session:
                try:
                    audio_chunk = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=1.0
                    )
                    
                    # Send audio to Gemini session
                    # Note: The Gemini Live API is experimental and the exact method signature
                    # may vary. Using type: ignore for compatibility with different API versions.
                    await self._session.send(audio_chunk)  # type: ignore[call-arg]
                    logger.debug(f"Sent {len(audio_chunk)} bytes to Gemini STT")
                    
                except asyncio.TimeoutError:
                    # No audio in queue, continue
                    continue
                    
        except asyncio.CancelledError:
            logger.info("Audio sending task cancelled")
        except Exception as e:
            logger.error(f"Error sending audio to Gemini: {e}", exc_info=True)
            self.is_streaming = False

    async def _receive_transcripts(self) -> None:
        """Internal task to receive transcripts from Gemini."""
        try:
            if not self._session:
                logger.error("No active session for receiving transcripts")
                return
                
            async for response in self._session.receive():
                if not self.is_streaming:
                    break
                    
                # Process the response
                await self._process_gemini_response(response)
                
        except asyncio.CancelledError:
            logger.info("Transcript receiving task cancelled")
        except Exception as e:
            logger.error(f"Error receiving transcripts from Gemini: {e}", exc_info=True)
            self.is_streaming = False

    async def _process_gemini_response(self, response) -> None:
        """Process a transcription response from Gemini Live API.
        
        Args:
            response: Response from Gemini Live API
        """
        try:
            # Extract transcript from Gemini Live response
            # The response structure may vary, so we handle it carefully
            transcript = ""
            is_final = False
            confidence = 0.8  # Default confidence
            language = self.language
            
            # Check if response has server_content
            if hasattr(response, 'server_content'):
                server_content = response.server_content
                
                # Check for turn_complete (indicates final transcript)
                if hasattr(server_content, 'turn_complete'):
                    is_final = server_content.turn_complete
                
                # Extract text from model_turn
                if hasattr(server_content, 'model_turn'):
                    model_turn = server_content.model_turn
                    if hasattr(model_turn, 'parts'):
                        for part in model_turn.parts:
                            if hasattr(part, 'text'):
                                transcript += part.text
            
            # Also check for text in response directly
            elif hasattr(response, 'text'):
                transcript = response.text
                is_final = getattr(response, 'is_final', False)
            
            # Log the raw response for debugging
            logger.debug(f"Gemini response type: {type(response)}, has text: {bool(transcript)}")
            
            if not transcript:
                return
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}", exc_info=True)
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