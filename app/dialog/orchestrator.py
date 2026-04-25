"""Per-call orchestrator.

Owns the audio pipeline for one phone call:

* Inbound: Twilio μ-law frames → 8 kHz PCM → 16 kHz PCM → STT.
* Per turn: STT final transcript → LLM → text deltas → TTS.
* Outbound: TTS 24 kHz PCM → 8 kHz PCM → μ-law → base64 → Twilio media frame.
* Barge-in: VAD on inbound while TTS is producing → ``tts.interrupt()``,
  flush outbound queue, truncate assistant transcript at last word boundary.

The :mod:`app.telephony.media_stream` WS handler is intentionally thin —
it parses Twilio JSON frames and delegates everything else to this class.
That keeps the WS protocol concerns separate from the dialog concerns.

The provider clients (STT, LLM, TTS) are injected. In production they're
the real :class:`GeminiSTTClient`, :class:`GeminiLLMClient`, and
:class:`GradiumTTSClient`; tests inject mocks.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from app.config import Settings
from app.dialog.session import Session
from app.utils.audio import (
    downsample_24k_to_8k,
    is_voiced,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    upsample_8k_to_16k,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.llm.client import LLMDelta
    from app.stt.gemini_stt import STTResult
    from app.tts.gradium_tts import WordTiming

logger = logging.getLogger(__name__)


# Outbound audio is sent in ~20 ms μ-law chunks (160 bytes) to match what
# Twilio Media Streams expects. Larger chunks add jitter; smaller ones
# add WS-frame overhead.
_OUTBOUND_FRAME_BYTES = 160


# ---------------------------------------------------------------------------
# Provider Protocols (loose, so mocks satisfy them without inheritance).
# ---------------------------------------------------------------------------


class _STTLike(Protocol):
    async def start(self, language: str | None = None) -> None: ...
    async def feed_audio(self, pcm_16k: bytes) -> None: ...
    def results(self) -> AsyncIterator[STTResult]: ...
    async def close(self) -> None: ...


class _LLMLike(Protocol):
    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]: ...


class _TTSLike(Protocol):
    async def connect(self, voice_id: str, language: str) -> None: ...
    async def send_text(self, text: str) -> None: ...
    def iter_audio(self) -> AsyncIterator[bytes]: ...
    def iter_word_timings(self) -> AsyncIterator[WordTiming]: ...
    async def interrupt(self) -> None: ...
    async def close(self) -> None: ...


class _WSLike(Protocol):
    async def send_text(self, data: str) -> None: ...


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class _TurnBuffer:
    """Accumulates one user turn's STT text before dispatching to the LLM."""

    text: str = ""

    def append(self, more: str) -> None:
        if more:
            self.text = (self.text + " " + more).strip() if self.text else more

    def take(self) -> str:
        out, self.text = self.text, ""
        return out


class CallOrchestrator:
    """Coordinates STT, LLM, and TTS for the lifetime of one call.

    Construct one per WS connection and call :meth:`start` on the Twilio
    ``start`` frame, :meth:`feed_caller_audio` on each ``media`` frame,
    and :meth:`stop` on disconnect.
    """

    def __init__(
        self,
        *,
        session: Session,
        settings: Settings,
        websocket: _WSLike,
        stt: _STTLike,
        llm: _LLMLike,
        tts: _TTSLike,
    ) -> None:
        self.session = session
        self.settings = settings
        self.websocket = websocket
        self.stt = stt
        self.llm = llm
        self.tts = tts

        self._turn_buffer = _TurnBuffer()
        self._tts_active = False
        self._tts_active_lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []
        self._stopped = False

    # ----- lifecycle ----------------------------------------------------

    async def start(self) -> None:
        """Open provider connections and spawn the pump tasks."""
        language = self.session.language or self.settings.default_language
        await self.stt.start(language=language)
        await self.tts.connect(
            voice_id=self.settings.voice_for(language), language=language
        )

        self._tasks.extend(
            [
                asyncio.create_task(self._pump_stt_results(), name="orchestrator.stt"),
                asyncio.create_task(self._pump_tts_audio(), name="orchestrator.tts_audio"),
                asyncio.create_task(self._pump_word_timings(), name="orchestrator.timings"),
            ]
        )

    async def stop(self) -> None:
        """Cancel pumps and close provider connections."""
        if self._stopped:
            return
        self._stopped = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._tasks.clear()

        await asyncio.gather(self.stt.close(), self.tts.close(), return_exceptions=True)

    # ----- inbound (caller → STT) --------------------------------------

    async def feed_caller_audio(self, mulaw_payload: bytes) -> None:
        """Process one Twilio ``media`` frame's μ-law payload."""
        if not mulaw_payload:
            return
        pcm_8k = mulaw_to_pcm16(mulaw_payload)

        if self._tts_active and is_voiced(pcm_8k):
            # The caller is talking over us. Cut TTS hard, then keep
            # forwarding their audio to STT so the next transcript captures
            # what they're saying.
            await self._barge_in()

        pcm_16k = upsample_8k_to_16k(pcm_8k)
        await self.stt.feed_audio(pcm_16k)
        self.session.media_frames += 1

    # ----- pumps --------------------------------------------------------

    async def _pump_stt_results(self) -> None:
        """Drain STT results; on each final, dispatch a turn to the LLM."""
        try:
            async for result in self.stt.results():
                if not result.is_final:
                    self._turn_buffer.append(result.text)
                    continue
                # Final marker — combine any in-flight interim text with
                # this segment's text and dispatch.
                self._turn_buffer.append(result.text)
                user_text = self._turn_buffer.take().strip()
                if not user_text:
                    continue
                self.session.add_turn("caller", user_text)
                logger.info(
                    "stt_final",
                    extra={
                        "call_sid": self.session.call_sid,
                        "len": len(user_text),
                        "language": result.language,
                    },
                )
                await self._handle_user_turn(user_text, language=result.language)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("stt_pump_error", extra={"call_sid": self.session.call_sid})

    async def _handle_user_turn(self, user_text: str, *, language: str | None) -> None:
        """Stream an LLM response for ``user_text`` and pipe text into TTS."""
        # Prepare a transcript for the LLM. The orchestrator owns the
        # message history — it's the source of truth, not the LLM.
        messages = [
            {"role": ("user" if t.speaker == "caller" else "assistant"), "content": t.text}
            for t in self.session.transcript
            if t.speaker in ("caller", "agent")
        ]

        agent_buffer: list[str] = []
        async with self._tts_active_lock:
            self._tts_active = True
        try:
            async for delta in self.llm.stream_completion(
                messages,
                language=language or self.session.language,
            ):
                if delta.text:
                    agent_buffer.append(delta.text)
                    await self.tts.send_text(delta.text)
                if delta.tool_call is not None:
                    # TODO(task-4): dispatch tool calls (create_claim, etc.).
                    logger.info(
                        "llm_tool_call_received",
                        extra={"name": delta.tool_call.get("name")},
                    )
                if delta.finish:
                    break
        finally:
            if agent_buffer:
                self.session.add_turn("agent", "".join(agent_buffer))
            # Don't flip _tts_active off here — the audio is still draining.
            # _pump_tts_audio flips it off when the queue is empty.

    async def _pump_tts_audio(self) -> None:
        """Drain TTS PCM → resample → μ-law → base64 → Twilio media frame."""
        leftover = b""
        try:
            async for pcm_24k in self.tts.iter_audio():
                pcm_8k = downsample_24k_to_8k(pcm_24k)
                mulaw = pcm16_to_mulaw(pcm_8k)
                buf = leftover + mulaw
                while len(buf) >= _OUTBOUND_FRAME_BYTES:
                    chunk, buf = buf[:_OUTBOUND_FRAME_BYTES], buf[_OUTBOUND_FRAME_BYTES:]
                    await self._send_media_frame(chunk)
                leftover = buf
                async with self._tts_active_lock:
                    self._tts_active = True
            # Flush partial trailing chunk (Twilio tolerates short frames).
            if leftover:
                await self._send_media_frame(leftover)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("tts_pump_error", extra={"call_sid": self.session.call_sid})
        finally:
            async with self._tts_active_lock:
                self._tts_active = False

    async def _pump_word_timings(self) -> None:
        """Append Gradium word timings to the most recent agent turn.

        The barge-in handler reads the most-recent timing to figure out
        where to truncate the transcript.
        """
        try:
            async for timing in self.tts.iter_word_timings():
                if self.session.transcript and self.session.transcript[-1].speaker == "agent":
                    self.session.transcript[-1].word_timings.append(
                        (timing.text, timing.start_s, timing.stop_s)
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("timings_pump_error", extra={"call_sid": self.session.call_sid})

    # ----- barge-in -----------------------------------------------------

    async def _barge_in(self) -> None:
        """Cut TTS within the latency budget and truncate the transcript."""
        async with self._tts_active_lock:
            if not self._tts_active:
                return
            self._tts_active = False

        logger.info("barge_in", extra={"call_sid": self.session.call_sid})
        await self.tts.interrupt()

        # Truncate the in-flight assistant turn to whatever the caller had
        # actually heard at interruption (the last completed word).
        if self.session.transcript and self.session.transcript[-1].speaker == "agent":
            last_turn = self.session.transcript[-1]
            if last_turn.word_timings:
                spoken = " ".join(w[0] for w in last_turn.word_timings).strip()
                last_turn.text = spoken

    # ----- outbound helper ---------------------------------------------

    async def _send_media_frame(self, mulaw: bytes) -> None:
        """Wrap a μ-law chunk into a Twilio Media Streams ``media`` frame."""
        if self._stopped or not self.session.stream_sid:
            return
        frame = {
            "event": "media",
            "streamSid": self.session.stream_sid,
            "media": {"payload": base64.b64encode(mulaw).decode("ascii")},
        }
        await self.websocket.send_text(json.dumps(frame))
