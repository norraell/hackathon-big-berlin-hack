"""Streaming Gemini STT wrapper.

Uses the ``google-genai`` Live API in transcription-only mode: we send raw
16-bit PCM @ 16 kHz frames and receive incremental transcripts. The Live
API is the only Gemini surface that streams *audio in*, *text out* with
sub-second latency, which is what the call loop needs.

The Live API also supports full conversational turn-taking (audio in,
audio out from a built-in voice). We deliberately *don't* use that — TTS
is Gradium, dialog policy is the LLM module. Configuring
``response_modalities=[TEXT]`` and enabling input transcription gives us
exactly what we want: transcripts, no LLM response audio.

Real call-site detail: the Live API session expects an open async context.
We expose a small async-iterator interface so the orchestrator can push
PCM frames in via :meth:`feed_audio` while consuming results in a separate
task via :meth:`results`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Gemini Live model ID. The "-live-" segment is the path that streams audio
# via the bidiGenerateContent endpoint. Google rotates / renames Live model
# IDs frequently, so this is overridable via the GEMINI_LIVE_MODEL env var
# (see ``app.config.Settings``). Default is the current GA model in v1beta.
DEFAULT_GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"


@dataclass
class STTResult:
    """One incremental STT result.

    ``is_final`` distinguishes Gemini's interim "in-progress" transcripts
    from the segment-final transcript. Only finals advance the dialog
    state machine; interims feed the barge-in / latency-watchdog logic.
    """

    text: str
    is_final: bool
    language: str | None = None
    confidence: float | None = None


class GeminiSTTClient:
    """Streaming Gemini STT client.

    Lifecycle:

    1. ``await client.start(language)`` — opens the Live session.
    2. ``await client.feed_audio(pcm_16k)`` — push frames as they arrive.
    3. ``async for r in client.results(): ...`` — consume transcripts.
    4. ``await client.close()`` — tear down.

    All three pumps run concurrently; the SDK handles the underlying WS.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GEMINI_LIVE_MODEL,
        sample_rate: int = 16_000,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate

        self._results: asyncio.Queue[STTResult | None] = asyncio.Queue()
        self._session_ctx: Any = None  # SDK context manager
        self._session: Any = None  # active session inside the context
        self._reader_task: asyncio.Task[None] | None = None
        self._language_hint: str | None = None
        self._closed = False

    # ----- lifecycle ----------------------------------------------------

    async def start(self, language: str | None = None) -> None:
        """Open the Gemini Live session."""
        self._language_hint = language

        # Lazy SDK import — we don't want a hard import-time dependency on
        # google-genai for unit tests that mock this class.
        # TODO(verify-sdk): the live API surface has been moving across
        # google-genai versions. Pin to a known-good version in
        # pyproject.toml once we settle on one in CI.
        try:
            from google import genai  # type: ignore[import-not-found]
            from google.genai import types  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "google-genai is not installed; install it or supply a mock STT client"
            ) from exc

        client = genai.Client(api_key=self.api_key)

        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.TEXT],
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )

        self._session_ctx = client.aio.live.connect(model=self.model, config=config)
        self._session = await self._session_ctx.__aenter__()
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info("gemini_stt_started", extra={"model": self.model, "language": language})

    async def feed_audio(self, pcm_16k: bytes) -> None:
        """Push a PCM frame (16 kHz, 16-bit signed-LE, mono) into the session."""
        if self._closed or self._session is None:
            return
        try:
            from google.genai import types  # type: ignore[import-not-found]
        except ImportError:  # pragma: no cover
            return

        # TODO(verify-sdk): newer SDKs use ``send_realtime_input`` with a
        # ``Blob`` payload; older ones used ``send`` with a different shape.
        # Wrap defensively.
        blob = types.Blob(data=pcm_16k, mime_type=f"audio/pcm;rate={self.sample_rate}")
        send = getattr(self._session, "send_realtime_input", None)
        if send is not None:
            await send(audio=blob)
        else:  # pragma: no cover — older SDK
            await self._session.send(input=blob)

    def results(self) -> AsyncIterator[STTResult]:
        """Async-iterate transcripts as they arrive."""
        return _drain_queue(self._results)

    async def close(self) -> None:
        """Close the Live session and stop the reader task."""
        if self._closed:
            return
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                logger.exception("gemini_stt_close_error")
        await self._results.put(None)  # signal to consumers
        logger.info("gemini_stt_closed")

    # ----- internals ----------------------------------------------------

    async def _read_loop(self) -> None:
        """Drain server messages and translate them into STTResult."""
        assert self._session is not None
        try:
            async for response in self._session.receive():  # SDK iterator
                for result in self._extract_results(response):
                    await self._results.put(result)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("gemini_stt_read_error")
            await self._results.put(None)

    def _extract_results(self, response: Any) -> list[STTResult]:
        """Map an SDK response object to zero or more :class:`STTResult`.

        The shape of ``response`` depends on the SDK version, so we probe
        defensively. The two paths we expect are:

        * ``response.server_content.input_transcription.text`` — interim
          transcript of caller audio.
        * Final transcripts arrive with the same text and an explicit
          ``is_final``-ish marker (``output_transcription`` flush, or a
          ``server_content.turn_complete`` boundary). We treat
          ``turn_complete=True`` as the segment-final signal.
        """
        out: list[STTResult] = []
        server_content = getattr(response, "server_content", None)
        if server_content is None:
            return out

        transcription = getattr(server_content, "input_transcription", None)
        text = getattr(transcription, "text", None) if transcription is not None else None
        turn_complete = bool(getattr(server_content, "turn_complete", False))

        if text:
            out.append(
                STTResult(
                    text=text,
                    is_final=turn_complete,
                    language=self._language_hint,
                    confidence=None,
                )
            )
        elif turn_complete:
            # Empty text + turn_complete — emit a final marker so the
            # orchestrator knows the user finished speaking. This is the
            # signal that drives barge-in unwinding and LLM dispatch.
            out.append(STTResult(text="", is_final=True, language=self._language_hint))
        return out


async def _drain_queue(queue: asyncio.Queue[STTResult | None]) -> AsyncIterator[STTResult]:
    """Async generator that yields items off the queue until ``None``."""
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item
