"""WebSocket handler for Twilio Media Streams - bidirectional audio processing."""

import asyncio
import base64
import json
import logging
from typing import Optional

from fastapi import WebSocket

from app.config import settings

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
        
        # Control flags
        self.is_streaming = False
        self.is_agent_speaking = False
        
        # Component references (to be initialized)
        self.stt_handler = None
        self.llm_handler = None
        self.tts_handler = None
        self.session = None
        
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
            
            # Wait for any task to complete (usually means disconnection)
            done, pending = await asyncio.wait(
                [receive_task, send_task, process_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
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
        
        # TODO: Initialize session
        # TODO: Initialize STT handler
        # TODO: Initialize LLM handler
        # TODO: Initialize TTS handler
        # TODO: Start greeting

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
            
            # If agent is speaking and user starts speaking, trigger barge-in
            if self.is_agent_speaking:
                await self._handle_barge_in()
                
        except Exception as e:
            logger.error(f"Error handling media: {e}", exc_info=True)

    async def _handle_stop(self, data: dict) -> None:
        """Handle stream stop event from Twilio.
        
        Args:
            data: Stop event data
        """
        logger.info(f"Stream stopped - StreamSID: {self.stream_sid}")
        self.is_streaming = False
        
        # TODO: Save final transcript
        # TODO: Close session

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
            while self.is_streaming:
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
                
        except Exception as e:
            logger.error(f"Error sending to Twilio: {e}", exc_info=True)

    async def _process_audio(self) -> None:
        """Process incoming audio through the STT → LLM → TTS pipeline.
        
        This is the main audio processing loop that:
        1. Takes audio from incoming queue
        2. Sends to STT for transcription
        3. Sends transcription to LLM for response
        4. Sends LLM response to TTS for synthesis
        5. Puts synthesized audio in outgoing queue
        """
        try:
            while self.is_streaming:
                # Get audio chunk from queue
                audio_chunk = await self.incoming_audio_queue.get()
                
                # TODO: Convert μ-law to PCM
                # TODO: Send to STT
                # TODO: Process STT results
                # TODO: Send to LLM when turn is complete
                # TODO: Stream LLM response to TTS
                # TODO: Put TTS audio in outgoing queue
                
                # Placeholder: just log for now
                logger.debug(f"Processing audio chunk of {len(audio_chunk)} bytes")
                
                # Small delay to prevent tight loop
                await asyncio.sleep(0.01)
                
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
        
        # TODO: Close STT connection
        # TODO: Close LLM connection
        # TODO: Close TTS connection
        # TODO: Save session data
        
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