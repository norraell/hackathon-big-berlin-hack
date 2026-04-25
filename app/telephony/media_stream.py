"""WebSocket handler for Twilio Media Streams - bidirectional audio processing."""

import asyncio
import base64
import json
import logging
import struct
from typing import Optional

from fastapi import WebSocket

from app.config import settings
from app.utils.audio import (
    pcm_to_ulaw,
    convert_twilio_to_stt,
    convert_tts_to_twilio,
    AudioBuffer,
)
from app.stt import STTHandler, get_stt_handler
from app.llm.client import GeminiLLMClient
from app.tts.gradium_tts import GradiumTTSHandler
from app.dialog.session import CallSession
from app.dialog.state_machine import DialogState

logger = logging.getLogger(__name__)


class MediaStreamHandler:
    """Handles bidirectional audio streaming with Twilio Media Streams.
    
    This class manages:
    - Receiving μ-law encoded audio from Twilio
    - Decoding and processing incoming audio
    - Encoding and sending audio back to Twilio
    - Coordinating between STT, LLM, and TTS components
    """

    def __init__(self, websocket: WebSocket) -> None:
        """Initialize the media stream handler.
        
        Args:
            websocket: WebSocket connection from Twilio
        """
        self.websocket = websocket
        self.stream_sid: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.from_number: Optional[str] = None
        self.to_number: Optional[str] = None
        
        # Audio buffers
        self.incoming_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.outgoing_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.audio_buffer = AudioBuffer(sample_rate=16000, sample_width=2)
        
        # Control flags
        self.is_streaming = False
        self.is_agent_speaking = False
        self.user_is_speaking = False
        
        # Component references (to be initialized)
        self.stt_handler: Optional[STTHandler] = None
        self.llm_handler: Optional[GeminiLLMClient] = None
        self.tts_handler: Optional[GradiumTTSHandler] = None
        self.session: Optional[CallSession] = None
        
        # Current transcript accumulation
        self.current_user_transcript = ""
        
        logger.info("MediaStreamHandler initialized")

    async def handle_stream(self) -> None:
        """Main handler for the media stream WebSocket connection.
        
        This method:
        1. Receives messages from Twilio
        2. Routes them to appropriate handlers
        3. Manages the audio processing pipeline
        """
        try:
            # Start background tasks
            receive_task = asyncio.create_task(self._receive_from_twilio())
            send_task = asyncio.create_task(self._send_to_twilio())
            process_task = asyncio.create_task(self._process_audio())
            
            # Keep the call alive until Twilio closes the inbound stream.
            # Sender/processor tasks may be idle between utterances and must
            # not end the whole call when a turn finishes.
            await receive_task
            
            self.is_streaming = False
            
            # Cancel background workers once the receive loop ends.
            for task in (send_task, process_task):
                task.cancel()
            
            for task in (send_task, process_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in media stream handler: {e}", exc_info=True)
            raise

    async def _receive_from_twilio(self) -> None:
        """Receive and process messages from Twilio Media Stream.
        
        Twilio sends three types of messages:
        - start: Stream initialization with metadata
        - media: Audio payload (μ-law encoded, base64)
        - stop: Stream termination
        """
        try:
            async for message in self.websocket.iter_text():
                data = json.loads(message)
                event = data.get("event")
                
                if event == "start":
                    await self._handle_start(data)
                elif event == "media":
                    await self._handle_media(data)
                elif event == "stop":
                    await self._handle_stop(data)
                elif event == "mark":
                    await self._handle_mark(data)
                elif event == "connected":
                    # Twilio sends this event when WebSocket connection is established
                    logger.debug("WebSocket connected event received from Twilio")
                else:
                    logger.warning(f"Unknown event type: {event}")
                    
        except Exception as e:
            logger.error(f"Error receiving from Twilio: {e}", exc_info=True)
            raise

    async def _handle_start(self, data: dict) -> None:
        """Handle stream start event from Twilio.
        
        Args:
            data: Start event data containing stream metadata
        """
        start_data = data.get("start", {})
        self.stream_sid = start_data.get("streamSid")
        self.call_sid = start_data.get("callSid")
        
        # Extract custom parameters
        custom_params = start_data.get("customParameters", {})
        self.from_number = custom_params.get("from")
        self.to_number = custom_params.get("to")
        
        logger.info(
            f"Stream started - StreamSID: {self.stream_sid}, "
            f"CallSID: {self.call_sid}, From: {self.from_number}"
        )
        
        self.is_streaming = True
        
        # Initialize session
        self.session = CallSession(
            call_sid=self.call_sid or "unknown",
            from_number=self.from_number or "unknown",
            to_number=self.to_number or "unknown",
            language=settings.default_language,
        )
        
        # Initialize STT handler with callbacks
        self.stt_handler = get_stt_handler(
            language=settings.default_language,
            on_transcript=self._on_interim_transcript,
            on_final=self._on_final_transcript,
        )
        
        # Initialize LLM handler
        self.llm_handler = GeminiLLMClient(
            language=settings.default_language,
            on_token=self._on_llm_token,
        )
        
        # Initialize TTS handler with callbacks
        self.tts_handler = GradiumTTSHandler(
            language=settings.default_language,
            on_audio=self._on_tts_audio,
            on_word_boundary=self._on_word_boundary,
        )
        
        # Start AI services
        try:
            await self.stt_handler.start()
            await self.llm_handler.initialize()
            await self.tts_handler.connect()
            logger.info("All AI services initialized successfully")
            
            # Send initial greeting
            await self._send_initial_greeting()
            
        except Exception as e:
            logger.error(f"Error initializing AI services: {e}", exc_info=True)
            # Fall back to test greeting if AI services fail
            await self._send_test_greeting()

    async def _handle_media(self, data: dict) -> None:
        """Handle incoming audio media from Twilio.
        
        Args:
            data: Media event data containing base64-encoded μ-law audio
        """
        media_data = data.get("media", {})
        payload = media_data.get("payload")
        
        if not payload:
            return
            
        # Decode base64 μ-law audio
        try:
            audio_bytes = base64.b64decode(payload)
            
            # Add to incoming audio queue for processing
            await self.incoming_audio_queue.put(audio_bytes)
            
            # Note: Barge-in detection should be handled by the audio processing
            # pipeline with proper Voice Activity Detection (VAD), not here.
            # Simply receiving audio doesn't mean the user is speaking - it could
            # be silence or background noise.
                
        except Exception as e:
            logger.error(f"Error handling media: {e}", exc_info=True)

    async def _handle_stop(self, data: dict) -> None:
        """Handle stream stop event from Twilio.
        
        Args:
            data: Stop event data
        """
        logger.info(f"Stream stopped - StreamSID: {self.stream_sid}")
        self.is_streaming = False
        
        # End session
        if self.session:
            self.session.end_session()
            logger.info(f"Session data: {self.session.to_dict()}")

    async def _handle_mark(self, data: dict) -> None:
        """Handle mark event from Twilio (used for synchronization).
        
        Args:
            data: Mark event data
        """
        mark_data = data.get("mark", {})
        mark_name = mark_data.get("name")
        logger.debug(f"Received mark: {mark_name}")

    async def _send_to_twilio(self) -> None:
        """Send audio back to Twilio from the outgoing queue.
        
        This continuously monitors the outgoing audio queue and sends
        μ-law encoded audio chunks to Twilio.
        """
        try:
            while True:
                # Get audio from outgoing queue
                audio_bytes = await self.outgoing_audio_queue.get()
                
                # Encode as base64
                payload = base64.b64encode(audio_bytes).decode("utf-8")
                
                # Send media message to Twilio
                message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": payload,
                    },
                }
                
                await self.websocket.send_text(json.dumps(message))
                
        except asyncio.CancelledError:
            logger.info("Twilio send loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error sending to Twilio: {e}", exc_info=True)

    async def _process_audio(self) -> None:
        """Process incoming audio through the STT → LLM → TTS pipeline.
        
        This is the main audio processing loop that:
        1. Takes audio from incoming queue
        2. Converts μ-law to PCM and resamples
        3. Sends to STT for transcription
        4. Processes final transcripts through LLM
        5. Streams LLM response to TTS
        6. Sends TTS audio back to Twilio
        """
        try:
            while True:
                # Get audio chunk from queue
                ulaw_chunk = await self.incoming_audio_queue.get()
                
                if not self.stt_handler or not self.stt_handler.is_streaming:
                    continue
                
                # Convert Twilio audio (μ-law 8kHz) to STT format (PCM 16kHz)
                try:
                    pcm_chunk = convert_twilio_to_stt(ulaw_chunk)
                    
                    # Send to STT
                    await self.stt_handler.send_audio(pcm_chunk)
                    
                    logger.debug(f"Sent {len(pcm_chunk)} bytes to STT")
                    
                except Exception as e:
                    logger.error(f"Error processing audio chunk: {e}", exc_info=True)
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("Audio processing loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)

    async def _handle_barge_in(self) -> None:
        """Handle barge-in when user starts speaking while agent is talking.
        
        This should:
        1. Stop TTS immediately
        2. Clear outgoing audio queue
        3. Truncate agent transcript at interruption point
        4. Resume listening to user
        """
        if not self.is_agent_speaking:
            return
            
    async def _send_initial_greeting(self) -> None:
        """Send initial greeting to the caller using TTS."""
        logger.info("Sending initial greeting")
        
        try:
            if not self.tts_handler or not self.llm_handler or not self.session:
                logger.warning("AI services not initialized, falling back to test greeting")
                await self._send_test_greeting()
                return
            
            # Get greeting based on language
            greeting_text = self._get_greeting_text()
            
            # Add to transcript
            self.session.add_transcript_entry("assistant", greeting_text)
            
            # Synthesize and send
            await self.tts_handler.synthesize_text(greeting_text)
            
            # Update state
            self.session.state_machine.transition_to(
                DialogState.GREETING,
                "initial greeting sent"
            )
            
            logger.info(f"Initial greeting sent: {greeting_text}")
            
        except Exception as e:
            logger.error(f"Error sending initial greeting: {e}", exc_info=True)
            await self._send_test_greeting()
    
    def _get_greeting_text(self) -> str:
        """Get greeting text based on current language."""
        greetings = {
            "en": "Hello! Thank you for calling. I'm here to help you file an insurance claim. How can I assist you today?",
            "de": "Hallo! Vielen Dank für Ihren Anruf. Ich bin hier, um Ihnen bei der Einreichung eines Versicherungsanspruchs zu helfen. Wie kann ich Ihnen heute helfen?",
        }
        language = self.session.language if self.session else settings.default_language
        return greetings.get(language, greetings["en"])
    
    def _on_interim_transcript(self, text: str, confidence: float, language: str) -> None:
        """Callback for interim transcripts from STT.
        
        Args:
            text: Interim transcript text
            confidence: Confidence score
            language: Detected language
        """
        self.current_user_transcript = text
        self.user_is_speaking = True
        
        logger.debug(f"Interim: '{text}' (confidence: {confidence:.2f})")
        
        # Check for barge-in if agent is speaking
        if self.is_agent_speaking:
            asyncio.create_task(self._handle_barge_in())
    
    def _on_final_transcript(self, text: str, confidence: float, language: str) -> None:
        """Callback for final transcripts from STT.
        
        Args:
            text: Final transcript text
            confidence: Confidence score
            language: Detected language
        """
        if not text.strip():
            return
        
        logger.info(f"Final transcript: '{text}' (confidence: {confidence:.2f})")
        
        self.user_is_speaking = False
        self.current_user_transcript = ""
        
        # Add to session transcript
        if self.session:
            self.session.add_transcript_entry("user", text, confidence)
        
        # Process through LLM
        asyncio.create_task(self._process_user_input(text))
    
    async def _process_user_input(self, text: str) -> None:
        """Process user input through LLM and generate response.
        
        Args:
            text: User's transcribed text
        """
        try:
            if not self.llm_handler or not self.tts_handler:
                logger.error("LLM or TTS handler not initialized")
                return
            
            # Add user message to LLM
            await self.llm_handler.add_user_message(text)
            
            # Clear TTS word history for new turn
            self.tts_handler.clear_word_history()
            
            # Stream LLM response
            response_text = ""
            async for token in self.llm_handler.stream_completion():
                response_text += token
            
            # Finalize the utterance (but keep connection open)
            await self.tts_handler.finalize_current_utterance()
            
            logger.info(f"LLM response complete: {response_text[:100]}...")
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}", exc_info=True)
    
    def _on_llm_token(self, token: str) -> None:
        """Callback for LLM tokens (for streaming to TTS).
        
        Args:
            token: Generated token from LLM
        """
        # Stream token to TTS for low-latency synthesis
        if self.tts_handler:
            asyncio.create_task(self.tts_handler.stream_text(token))
    
    def _on_tts_audio(self, pcm_audio: bytes) -> None:
        """Callback for TTS audio chunks.
        
        Args:
            pcm_audio: PCM audio from TTS (24kHz)
        """
        try:
            # Convert TTS audio (PCM 24kHz) to Twilio format (μ-law 8kHz)
            ulaw_audio = convert_tts_to_twilio(pcm_audio, tts_rate=24000)
            
            # Send to Twilio
            asyncio.create_task(self.send_audio(ulaw_audio))
            
            logger.debug(f"Sent {len(ulaw_audio)} bytes of TTS audio to Twilio")
            
        except Exception as e:
            logger.error(f"Error handling TTS audio: {e}", exc_info=True)
    
    def _on_word_boundary(self, word: str, start_s: float, stop_s: float) -> None:
        """Callback for word boundaries from TTS.
        
        Args:
            word: Word being spoken
            start_s: Start time in seconds
            stop_s: Stop time in seconds
        """
        logger.debug(f"Word boundary: '{word}' at {start_s:.2f}s - {stop_s:.2f}s")

        logger.info("Barge-in detected - stopping agent speech")
        
        # Stop agent speech
        self.is_agent_speaking = False
        
        # TODO: Stop TTS stream
        # TODO: Clear outgoing audio queue
        # TODO: Truncate transcript using word-level timestamps
        
        # Clear the outgoing queue
        while not self.outgoing_audio_queue.empty():
            try:
                self.outgoing_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _send_test_greeting(self) -> None:
        """Send a test audio greeting to verify the audio pipeline.
        
        This generates a simple tone and text-to-speech-like pattern
        to confirm audio is flowing back to Twilio correctly.
        """
        logger.info("Sending test greeting audio")
        
        try:
            # Generate a simple 440Hz tone (A4 note) for 2 seconds at 8kHz
            sample_rate = 8000
            duration = 2.0
            frequency = 440.0
            
            num_samples = int(sample_rate * duration)
            
            # Generate sine wave
            import math
            pcm_samples = []
            for i in range(num_samples):
                # Generate sine wave value between -1 and 1
                t = i / sample_rate
                value = math.sin(2 * math.pi * frequency * t)
                # Convert to 16-bit PCM (-32768 to 32767)
                sample = int(value * 32767 * 0.3)  # 30% volume
                pcm_samples.append(sample)
            
            # Pack as 16-bit little-endian PCM
            pcm_data = struct.pack(f'<{len(pcm_samples)}h', *pcm_samples)
            
            # Convert PCM to μ-law for Twilio
            ulaw_data = pcm_to_ulaw(pcm_data, sample_width=2)
            
            # Split into chunks (20ms = 160 bytes at 8kHz μ-law)
            chunk_size = 160
            for i in range(0, len(ulaw_data), chunk_size):
                chunk = ulaw_data[i:i + chunk_size]
                await self.send_audio(chunk)
                # Small delay to simulate real-time streaming
                await asyncio.sleep(0.02)  # 20ms
            
            logger.info("Test greeting audio sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending test greeting: {e}", exc_info=True)

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send audio to Twilio (called by TTS handler).
        
        Args:
            audio_bytes: μ-law encoded audio bytes
        """
        await self.outgoing_audio_queue.put(audio_bytes)
        self.is_agent_speaking = True

    async def send_mark(self, mark_name: str) -> None:
        """Send a mark message to Twilio for synchronization.
        
        Args:
            mark_name: Name of the mark
        """
        message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": mark_name,
            },
        }
        await self.websocket.send_text(json.dumps(message))

    async def cleanup(self) -> None:
        """Clean up resources when the stream ends."""
        logger.info("Cleaning up media stream handler")
        
        self.is_streaming = False
        
        # Close AI service connections
        if self.stt_handler:
            try:
                await self.stt_handler.stop()
            except Exception as e:
                logger.error(f"Error stopping STT: {e}")
        
        if self.tts_handler:
            try:
                await self.tts_handler.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting TTS: {e}")
        
        # Save session data
        if self.session:
            logger.info(f"Final session state: {self.session.to_dict()}")
        
        # Clear queues
        while not self.incoming_audio_queue.empty():
            try:
                self.incoming_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
                
        while not self.outgoing_audio_queue.empty():
            try:
                self.outgoing_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        self.audio_buffer.clear()