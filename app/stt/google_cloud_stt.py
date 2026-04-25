"""Google Cloud Speech-to-Text streaming wrapper.

This is an alternative to Gemini Live API that provides real-time
speech-to-text transcription for telephony applications.
"""

import asyncio
import logging
from typing import Optional, Callable
from queue import Queue
import threading

from app.config import settings

logger = logging.getLogger(__name__)


class GoogleCloudSTTHandler:
    """Handles streaming speech-to-text using Google Cloud Speech-to-Text.
    
    This class provides similar functionality to GeminiSTTHandler but uses
    Google Cloud Speech-to-Text API which is production-ready and stable.
    """

    def __init__(
        self,
        language: Optional[str] = None,
        on_transcript: Optional[Callable[[str, float, str], None]] = None,
        on_final: Optional[Callable[[str, float, str], None]] = None,
    ) -> None:
        """Initialize the Google Cloud STT handler.
        
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
        
        # Google Cloud Speech client
        self.client = None
        self.streaming_config = None
        
        # Transcription state
        self.current_transcript = ""
        self.current_confidence = 0.0
        self.detected_language = self.language
        self.low_confidence_count = 0
        
        # Threading for sync API
        self._requests_queue = Queue()
        self._thread = None
        
        logger.info(f"GoogleCloudSTTHandler initialized with language: {self.language}")

    async def start(self) -> None:
        """Start the STT streaming session."""
        logger.info("Starting Google Cloud STT stream")
        
        try:
            # Check if credentials are configured
            import os
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            
            if not credentials_path:
                logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
                raise RuntimeError(
                    "Google Cloud STT requires GOOGLE_APPLICATION_CREDENTIALS to be set. "
                    "Please set it to the path of your service account JSON key file. "
                    "See documentation/GOOGLE_CLOUD_STT_SETUP.md for setup instructions."
                )
            
            if not os.path.exists(credentials_path):
                logger.error(f"Credentials file not found: {credentials_path}")
                raise RuntimeError(
                    f"Google Cloud credentials file not found: {credentials_path}. "
                    f"Please ensure the file exists or update GOOGLE_APPLICATION_CREDENTIALS. "
                    f"See documentation/GOOGLE_CLOUD_STT_SETUP.md for setup instructions."
                )
            
            # Import Google Cloud Speech
            try:
                from google.cloud import speech_v1p1beta1 as speech
            except ImportError as e:
                logger.error(f"Failed to import google-cloud-speech: {e}")
                raise RuntimeError(
                    "google-cloud-speech package not installed. "
                    "Install with: pip install google-cloud-speech"
                ) from e
            
            # Initialize client
            try:
                self.client = speech.SpeechClient()
                logger.info("✓ Google Cloud Speech client initialized")
            except Exception as e:
                logger.error(f"Failed to create Speech client: {e}")
                raise RuntimeError(
                    f"Failed to initialize Google Cloud Speech client: {e}. "
                    f"Please verify your credentials file is valid. "
                    f"See documentation/GOOGLE_CLOUD_STT_SETUP.md for troubleshooting."
                ) from e
            
            # Configure streaming recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self._get_language_code(self.language),
                enable_automatic_punctuation=True,
                enable_word_time_offsets=False,
                model="phone_call",  # Optimized for telephony
                use_enhanced=True,  # Use enhanced model if available
            )
            
            self.streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            self.is_streaming = True
            
            # Start processing tasks
            send_task = asyncio.create_task(self._send_audio())
            receive_task = asyncio.create_task(self._receive_transcripts())
            
            # Store tasks for cleanup
            self.tasks = [send_task, receive_task]
            
            logger.info("Google Cloud STT stream started successfully")
            
        except Exception as e:
            logger.error(f"Error starting Google Cloud STT: {e}", exc_info=True)
            await self._cleanup()
            raise

    def _get_language_code(self, lang: str) -> str:
        """Convert language code to Google Cloud format.
        
        Args:
            lang: Language code (e.g., 'en', 'de')
            
        Returns:
            Google Cloud language code (e.g., 'en-US', 'de-DE')
        """
        language_map = {
            'en': 'en-US',
            'de': 'de-DE',
            'es': 'es-ES',
            'fr': 'fr-FR',
            'pt': 'pt-BR',
        }
        return language_map.get(lang, f'{lang}-US')

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
        
        # Stop thread
        if self._thread and self._thread.is_alive():
            self._requests_queue.put(None)  # Signal to stop
            self._thread.join(timeout=2.0)
        
        self.client = None

    async def stop(self) -> None:
        """Stop the STT streaming session."""
        logger.info("Stopping Google Cloud STT stream")
        await self._cleanup()
        logger.info("Google Cloud STT stream stopped")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to the STT service.
        
        Args:
            audio_chunk: PCM audio data (16 kHz, 16-bit)
        """
        if not self.is_streaming:
            logger.warning("Attempted to send audio while not streaming")
            return
            
        await self.audio_queue.put(audio_chunk)

    def _audio_generator(self):
        """Generator that yields audio chunks from the queue."""
        while self.is_streaming:
            try:
                chunk = self._requests_queue.get(timeout=0.1)
                if chunk is None:  # Stop signal
                    break
                yield chunk
            except:
                continue

    async def _send_audio(self) -> None:
        """Internal task to send audio from queue to Google Cloud."""
        try:
            from google.cloud import speech_v1p1beta1 as speech
            
            # Ensure client is initialized
            if self.client is None:
                logger.error("Client not initialized, cannot send audio")
                return
            
            if self.streaming_config is None:
                logger.error("Streaming config not initialized, cannot send audio")
                return
            
            # Start streaming recognition in a separate thread
            def run_recognition():
                try:
                    # Type guard: we've already checked client is not None above
                    if self.client is None or self.streaming_config is None:
                        logger.error("Client or config became None during execution")
                        return
                    
                    requests = (
                        speech.StreamingRecognizeRequest(audio_content=content)
                        for content in self._audio_generator()
                    )
                    
                    responses = self.client.streaming_recognize(
                        self.streaming_config,
                        requests
                    )
                    
                    # Process responses
                    for response in responses:
                        if not self.is_streaming:
                            break
                        
                        # Schedule processing in async context
                        asyncio.run_coroutine_threadsafe(
                            self._process_response(response),
                            asyncio.get_event_loop()
                        )
                        
                except Exception as e:
                    logger.error(f"Error in recognition thread: {e}", exc_info=True)
            
            # Start recognition thread
            self._thread = threading.Thread(target=run_recognition, daemon=True)
            self._thread.start()
            
            # Feed audio to the thread
            while self.is_streaming:
                try:
                    audio_chunk = await asyncio.wait_for(
                        self.audio_queue.get(),
                        timeout=1.0
                    )
                    self._requests_queue.put(audio_chunk)
                    logger.debug(f"Queued {len(audio_chunk)} bytes for Google Cloud STT")
                except asyncio.TimeoutError:
                    continue
                    
        except asyncio.CancelledError:
            logger.info("Audio sending task cancelled")
        except Exception as e:
            logger.error(f"Error sending audio to Google Cloud: {e}", exc_info=True)
            self.is_streaming = False

    async def _receive_transcripts(self) -> None:
        """Internal task placeholder - actual receiving happens in _send_audio thread."""
        try:
            # Keep task alive while streaming
            while self.is_streaming:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Transcript receiving task cancelled")

    async def _process_response(self, response) -> None:
        """Process a transcription response from Google Cloud.
        
        Args:
            response: Response from Google Cloud Speech-to-Text
        """
        try:
            if not response.results:
                return
            
            # Get the first result
            result = response.results[0]
            
            if not result.alternatives:
                return
            
            # Get the best alternative
            alternative = result.alternatives[0]
            
            transcript = alternative.transcript
            confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.8
            is_final = result.is_final
            
            # Detect language (if available)
            language = self.language
            if hasattr(result, 'language_code'):
                language = result.language_code[:2]  # Convert 'en-US' to 'en'
            
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
                    
        except Exception as e:
            logger.error(f"Error processing Google Cloud response: {e}", exc_info=True)

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