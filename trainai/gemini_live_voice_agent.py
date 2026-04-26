"""
gemini_voice/gemini_live_voice_agent.py
Real-time voice agent using the Gemini Live (Multimodal Live) API.

Architecture:
  Microphone → PCM audio chunks → Gemini Live WebSocket
                                       ↓
                              Gemini processes audio + tools
                                       ↓
                         PCM audio response → Speaker

Requirements:
  - GEMINI_API_KEY in .env
  - pyaudio: pip install pyaudio
  - On macOS: brew install portaudio first
  - On Linux: sudo apt-get install portaudio19-dev

Usage:
  python gemini_voice/gemini_live_voice_agent.py

Press CTRL+C to stop.
"""

import asyncio
import json
import os
import sys
import signal
import traceback
from typing import Optional

import pyaudio
from dotenv import load_dotenv
from loguru import logger

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.insurance_tools import INSURANCE_TOOLS, handle_tool_call

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY",   "YOUR_GEMINI_API_KEY_HERE")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.0-flash-exp")

# Audio settings expected by Gemini Live
SEND_SAMPLE_RATE   = 16_000   # input: 16kHz mono
RECEIVE_SAMPLE_RATE = 24_000  # output: 24kHz mono
CHANNELS           = 1
CHUNK_SIZE         = 1_024
AUDIO_FORMAT       = pyaudio.paInt16

# Gemini Live API endpoint
LIVE_API_URL = (
    f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha"
    f".GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
)

SYSTEM_PROMPT = """
You are a warm, professional insurance customer service voice assistant.
- Speak naturally, clearly, and at a comfortable pace.
- Keep answers to 2–3 sentences unless the customer needs more detail.
- Use available tools to look up real policy, claim, and billing data.
- NEVER reveal, fabricate, or guess personal data, passwords, or financial details.
- If you cannot help, escalate to a human agent using the escalate_to_human tool.
""".strip()


# ── Audio helpers ─────────────────────────────────────────────────────────────

class AudioPlayer:
    """Plays audio bytes received from Gemini Live."""

    def __init__(self):
        self.pa     = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )

    def play(self, data: bytes) -> None:
        self.stream.write(data)

    def close(self) -> None:
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()


class AudioRecorder:
    """Captures microphone audio and yields raw PCM chunks."""

    def __init__(self):
        self.pa     = pyaudio.PyAudio()
        self.stream = self.pa.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

    def read_chunk(self) -> bytes:
        return self.stream.read(CHUNK_SIZE, exception_on_overflow=False)

    def close(self) -> None:
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()


# ── Gemini Live agent ─────────────────────────────────────────────────────────

class InsuranceVoiceAgent:
    """
    Manages the WebSocket session with Gemini Live.
    Handles:
      • Streaming audio in from microphone
      • Receiving audio + text responses from Gemini
      • Executing insurance tool calls
    """

    def __init__(self):
        self.player:   Optional[AudioPlayer]   = None
        self.recorder: Optional[AudioRecorder] = None
        self._running  = False

    # ── Session setup ─────────────────────────────────────────────────────────

    def _build_setup_message(self) -> dict:
        """
        Initial config message sent to Gemini Live.
        See: https://ai.google.dev/api/multimodal-live
        """
        return {
            "setup": {
                "model": f"models/{GEMINI_LIVE_MODEL}",
                "system_instruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "tools": [{"function_declarations": INSURANCE_TOOLS}],
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": "Aoede"}
                        }
                    },
                },
            }
        }

    # ── Message senders ───────────────────────────────────────────────────────

    async def _send_audio_chunk(self, ws, pcm_bytes: bytes) -> None:
        import base64
        msg = {
            "realtime_input": {
                "media_chunks": [
                    {
                        "data": base64.b64encode(pcm_bytes).decode("utf-8"),
                        "mime_type": f"audio/pcm;rate={SEND_SAMPLE_RATE}",
                    }
                ]
            }
        }
        await ws.send(json.dumps(msg))

    async def _send_tool_result(self, ws, call_id: str, result: dict) -> None:
        msg = {
            "tool_response": {
                "function_responses": [
                    {
                        "id":       call_id,
                        "response": {"result": json.dumps(result)},
                    }
                ]
            }
        }
        await ws.send(json.dumps(msg))

    # ── Receiver loop ─────────────────────────────────────────────────────────

    async def _receive_loop(self, ws) -> None:
        """Process all incoming messages from Gemini Live."""
        import base64

        async for raw in ws:
            if not self._running:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # ── Audio output ──────────────────────────────────────────────────
            server_content = msg.get("serverContent", {})
            for part in server_content.get("modelTurn", {}).get("parts", []):
                if "inlineData" in part:
                    audio_bytes = base64.b64decode(part["inlineData"]["data"])
                    if self.player:
                        self.player.play(audio_bytes)

                if "text" in part:
                    logger.info(f"[Gemini] {part['text']}")

            # ── Tool calls ────────────────────────────────────────────────────
            for tool_call in msg.get("toolCall", {}).get("functionCalls", []):
                name    = tool_call["name"]
                args    = tool_call.get("args", {})
                call_id = tool_call.get("id", "")

                logger.info(f"[Tool] {name}({args})")
                result = handle_tool_call(name, args)
                await self._send_tool_result(ws, call_id, result)

            # ── Interruption / turn complete signals ──────────────────────────
            if server_content.get("interrupted"):
                logger.debug("Turn interrupted by user speech.")
            if server_content.get("turnComplete"):
                logger.debug("Turn complete.")

    # ── Sender loop ───────────────────────────────────────────────────────────

    async def _send_loop(self, ws) -> None:
        """Continuously read microphone and stream to Gemini Live."""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                # Read mic in executor to avoid blocking the event loop
                chunk = await loop.run_in_executor(None, self.recorder.read_chunk)
                await self._send_audio_chunk(ws, chunk)
            except Exception as e:
                logger.error(f"Send error: {e}")
                break

    # ── Main run ──────────────────────────────────────────────────────────────

    async def run(self) -> None:
        try:
            import websockets
        except ImportError:
            logger.error("websockets not installed. Run: pip install websockets")
            return

        self.player   = AudioPlayer()
        self.recorder = AudioRecorder()
        self._running = True

        logger.info(f"Connecting to Gemini Live ({GEMINI_LIVE_MODEL}) …")

        async with websockets.connect(LIVE_API_URL) as ws:
            # 1. Send setup
            await ws.send(json.dumps(self._build_setup_message()))

            # Wait for setup confirmation
            setup_resp = json.loads(await ws.recv())
            if "setupComplete" not in setup_resp:
                logger.warning(f"Unexpected setup response: {setup_resp}")
            else:
                logger.success("Gemini Live session ready. Speak now …")
                print("\n🎙  Insurance Voice Agent is listening. Press CTRL+C to stop.\n")

            # 2. Run send + receive concurrently
            await asyncio.gather(
                self._send_loop(ws),
                self._receive_loop(ws),
            )

    def stop(self) -> None:
        self._running = False
        if self.player:
            self.player.close()
        if self.recorder:
            self.recorder.close()
        logger.info("Agent stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    agent = InsuranceVoiceAgent()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, agent.stop)

    try:
        await agent.run()
    except Exception:
        traceback.print_exc()
    finally:
        agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
