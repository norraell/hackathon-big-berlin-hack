"""Gradium streaming Text-to-Speech over WebSocket."""

import asyncio
import base64
import json
import logging
from typing import Optional, Callable

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from app.config import settings

logger = logging.getLogger(__name__)


class GradiumTTSHandler:
    """Handles streaming text-to-speech using Gradium WebSocket API.
    
    This class manages:
    - Persistent WebSocket connection to Gradium
    - Streaming text input and receiving audio output
    - Word-level timestamps for barge-in support
    - Connection multiplexing across conversation turns
    """

    def __init__(
        self,
        voice_id: Optional[str] = None,
        language: str = "en",
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_word_boundary: Optional[Callable[[str, float, float], None]] = None,
    ) -> None:
        """Initialize the Gradium TTS handler.
        
        Args:
            voice_id: Gradium voice ID (None uses default for language)
            language: Language code
            on_audio: Callback for audio chunks (PCM bytes)
            on_word_boundary: Callback for word boundaries (word, start_s, stop_s)
        """
        self.language = language
        self.voice_id = voice_id or settings.get_voice_for_language(language)
        self.on_audio = on_audio
        self.on_word_boundary = on_word_boundary
        
        # WebSocket connection
        self.ws: Optional[ClientConnection] = None
        self.is_connected = False
        self.is_speaking = False
        
        # Audio configuration
        self.sample_rate = 24000  # 24 kHz PCM
        self.output_format = "pcm_s16le"
        
        # Word-level tracking for barge-in
        self.current_words: list[tuple[str, float, float]] = []
        self.last_word_time = 0.0
        
        # Text queue for streaming
        self.text_queue: asyncio.Queue[str] = asyncio.Queue()
        
        logger.info(
            f"GradiumTTSHandler initialized - Voice: {self.voice_id}, "
            f"Language: {language}"
        )

    async def connect(self) -> None:
        """Establish WebSocket connection to Gradium."""
        if self.is_connected:
            logger.warning("Already connected to Gradium")
            return
        
        try:
            logger.info(f"Connecting to Gradium at {settings.gradium_tts_endpoint}")
            
            # Connect with API key in header
            self.ws = await connect(
                settings.gradium_tts_endpoint,
                extra_headers={
                    "x-api-key": settings.gradium_api_key,
                },
            )
            
            # Send setup message
            setup_message = {
                "type": "setup",
                "voice_id": self.voice_id,
                "model_name": "gradium-tts-v1",
                "output_format": self.output_format,
                "sample_rate": self.sample_rate,
            }
            
            await self.ws.send(json.dumps(setup_message))
            
            # Wait for ready message
            response = await self.ws.recv()
            response_data = json.loads(response)
            
            if response_data.get("type") == "ready":
                self.is_connected = True
                logger.info("Gradium TTS connection established and ready")
                
                # Start receive task
                asyncio.create_task(self._receive_audio())
            else:
                raise Exception(f"Unexpected response from Gradium: {response_data}")
                
        except Exception as e:
            logger.error(f"Error connecting to Gradium: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection to Gradium."""
        if not self.is_connected:
            return
        
        try:
            if self.ws:
                await self.ws.close()
            
            self.is_connected = False
            self.is_speaking = False
            self.ws = None
            
            logger.info("Disconnected from Gradium")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Gradium: {e}", exc_info=True)

    async def finalize_current_utterance(self) -> None:
        """Mark the current utterance complete without closing the connection.
        
        Gradium uses ``end_of_stream`` as a terminal signal for the session, so
        sending it after every first assistant response closes the TTS stream and
        can cascade into the phone call ending. This method is intended to be
        used at turn boundaries while keeping the WebSocket open for follow-up
        assistant messages in the same call.
        """
        if not self.is_connected or not self.ws:
            return

        try:
            await self.ws.send(json.dumps({"type": "flush"}))
            logger.debug("Sent utterance flush to Gradium")
        except Exception as e:
            logger.error(f"Error finalizing utterance: {e}", exc_info=True)

    async def synthesize_text(self, text: str) -> None:
        """Send text to Gradium for synthesis.
        
        Args:
            text: Text to synthesize
        """
        if not self.is_connected:
            await self.connect()
        
        if not self.ws:
            raise RuntimeError("Gradium WebSocket is not connected")
        
        try:
            # Send text message
            text_message = {
                "type": "text",
                "text": text,
            }
            
            await self.ws.send(json.dumps(text_message))
            self.is_speaking = True
            
            logger.info(f"Sent text to Gradium: {text[:100]}...")
            
        except Exception as e:
            logger.error(f"Error sending text to Gradium: {e}", exc_info=True)
            raise

    async def stream_text(self, text: str) -> None:
        """Stream text token by token to Gradium.
        
        This enables lower latency by starting synthesis before
        the complete text is available.
        
        Args:
            text: Text token to stream
        """
        await self.text_queue.put(text)

    async def _stream_text_worker(self) -> None:
        """Worker task to stream text from queue to Gradium."""
        try:
            while self.is_connected:
                text = await self.text_queue.get()
                await self.synthesize_text(text)
                
        except asyncio.CancelledError:
            logger.info("Text streaming worker cancelled")
        except Exception as e:
            logger.error(f"Error in text streaming worker: {e}", exc_info=True)

    async def _receive_audio(self) -> None:
        """Receive audio and word boundaries from Gradium."""
        try:
            while self.is_connected and self.ws:
                message = await self.ws.recv()
                data = json.loads(message)
                
                message_type = data.get("type")
                
                if message_type == "audio":
                    await self._handle_audio(data)
                elif message_type == "text":
                    await self._handle_word_boundary(data)
                elif message_type == "done":
                    self.is_speaking = False
                    logger.info("Gradium synthesis complete")
                elif message_type == "error":
                    logger.error(f"Gradium error: {data.get('message')}")
                    
        except ConnectionClosed:
            logger.info("Gradium connection closed")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error receiving from Gradium: {e}", exc_info=True)

    async def _handle_audio(self, data: dict) -> None:
        """Handle audio message from Gradium.
        
        Args:
            data: Audio message data
        """
        # Decode base64 PCM audio
        audio_base64 = data.get("audio", "")
        if not audio_base64:
            return
        
        try:
            audio_bytes = base64.b64decode(audio_base64)
            
            # Send to callback
            if self.on_audio:
                self.on_audio(audio_bytes)
            
            logger.debug(f"Received {len(audio_bytes)} bytes of audio from Gradium")
            
        except Exception as e:
            logger.error(f"Error handling audio: {e}", exc_info=True)

    async def _handle_word_boundary(self, data: dict) -> None:
        """Handle word boundary message from Gradium.
        
        Args:
            data: Word boundary data with text, start_s, stop_s
        """
        text = data.get("text", "")
        start_s = data.get("start_s", 0.0)
        stop_s = data.get("stop_s", 0.0)
        
        if not text:
            return
        
        # Store word boundary
        self.current_words.append((text, start_s, stop_s))
        self.last_word_time = stop_s
        
        # Send to callback
        if self.on_word_boundary:
            self.on_word_boundary(text, start_s, stop_s)
        
        logger.debug(f"Word boundary: '{text}' at {start_s:.2f}s - {stop_s:.2f}s")

    async def stop_synthesis(self) -> None:
        """Stop current synthesis (for barge-in)."""
        if not self.is_speaking:
            return
        
        logger.info("Stopping Gradium synthesis")
        
        try:
            # Send stop message
            if self.ws and self.is_connected:
                await self.ws.send(json.dumps({"type": "stop"}))
            
            self.is_speaking = False
            
        except Exception as e:
            logger.error(f"Error stopping synthesis: {e}", exc_info=True)

    def get_words_spoken(self) -> list[tuple[str, float, float]]:
        """Get the list of words spoken so far.
        
        Returns:
            List of tuples (word, start_s, stop_s)
        """
        return self.current_words.copy()

    def truncate_at_time(self, time_s: float) -> str:
        """Truncate the spoken text at a specific time (for barge-in).
        
        Args:
            time_s: Time in seconds to truncate at
            
        Returns:
            Text that was actually spoken before truncation
        """
        spoken_words = []
        
        for word, start_s, stop_s in self.current_words:
            if start_s < time_s:
                spoken_words.append(word)
            else:
                break
        
        return " ".join(spoken_words)

    def clear_word_history(self) -> None:
        """Clear word boundary history (start of new turn)."""
        self.current_words = []
        self.last_word_time = 0.0

    async def change_voice(self, voice_id: str, language: str) -> None:
        """Change voice by reconnecting with new voice ID.
        
        Args:
            voice_id: New voice ID
            language: New language code
        """
        logger.info(f"Changing voice from {self.voice_id} to {voice_id}")
        
        # Disconnect current connection
        await self.disconnect()
        
        # Update voice and language
        self.voice_id = voice_id
        self.language = language
        
        # Reconnect with new voice
        await self.connect()