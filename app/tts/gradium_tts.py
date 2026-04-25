"""Streaming Gradium TTS client.

Constraints from CLAUDE.md §6 honored here:

* **One persistent connection per :class:`Session`** across conversation
  turns — saves ~50 ms TTFA per turn vs reconnecting. Only close on call
  hangup, language change, or unrecoverable error (Gradium ``setup`` is
  one-shot per connection).
* **Request raw PCM (``pcm_24000``)**; resample + μ-law-encode in
  :mod:`app.utils.audio` before sending to Twilio.
* **Voice-per-language** via :meth:`app.config.Settings.voice_for`.
* **Word-level timestamps** (``start_s`` / ``stop_s``) surfaced through
  :meth:`iter_word_timings` — the orchestrator records them on the
  Session so barge-in can truncate at the actual interruption point.
* **End-to-end streaming**: :meth:`send_text` is safe to call repeatedly
  with partial LLM tokens; the SDK chunks and synthesizes as they arrive.

The actual Gradium SDK surface is wrapped behind a small adapter
(``_GradiumStreamAdapter``) so the public class is testable with a
``MagicMock`` stream object and so the real SDK call sites are confined
to one place.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WordTiming:
    """A single word with its start/stop offsets in the audio stream."""

    text: str
    start_s: float
    stop_s: float


class GradiumTTSClient:
    """Async streaming TTS client built on the official ``gradium`` SDK."""

    def __init__(self, api_key: str, *, endpoint: str | None = None) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

        self._client: Any = None
        self._stream: _GradiumStreamAdapter | None = None
        self._connected_voice: str | None = None
        self._connected_language: str | None = None

        self._audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._words_q: asyncio.Queue[WordTiming | None] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None

    # ----- lifecycle ----------------------------------------------------

    async def connect(self, voice_id: str, language: str) -> None:
        """Open (or reopen) the underlying SDK connection.

        Idempotent if already connected to the same ``voice_id`` /
        ``language``. Reconnects if either has changed.
        """
        if (
            self._stream is not None
            and self._connected_voice == voice_id
            and self._connected_language == language
        ):
            return

        await self._teardown_stream()

        if self._client is None:
            self._client = _build_client(self.api_key, endpoint=self.endpoint)

        # TODO(verify-sdk): replace ``stream_tts`` with the actual SDK
        # entrypoint once verified. The contract we lean on:
        #   * returns an async context manager / awaitable yielding a
        #     stream object with: ``send_text``, ``end_of_stream``,
        #     ``close``, and an async iterator of events with
        #     ``type ∈ {"audio","text","error"}``.
        self._stream = await _open_stream(
            self._client,
            voice_id=voice_id,
            language=language,
            output_format="pcm_24000",
            json_config={
                # Per CLAUDE.md §6 — rewrite rules dramatically improve
                # readback accuracy of dates, numbers, and claim IDs.
                "rewrite_rules": True,
                "language": language,
            },
        )
        self._connected_voice = voice_id
        self._connected_language = language

        # Drain queues from any previous turn before starting the new
        # reader; keeps stale audio out of the next outbound stream.
        _drain_queue_sync(self._audio_q)
        _drain_queue_sync(self._words_q)

        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info(
            "gradium_tts_connected", extra={"voice_id": voice_id, "language": language}
        )

    async def send_text(self, text: str) -> None:
        """Push text into the synthesis stream."""
        if not text or self._stream is None:
            return
        await self._stream.send_text(text)

    def iter_audio(self) -> AsyncIterator[bytes]:
        """Async-iterate raw 24 kHz s16le PCM chunks as they're synthesized."""
        return _drain_queue(self._audio_q)

    def iter_word_timings(self) -> AsyncIterator[WordTiming]:
        """Async-iterate word-level (text, start_s, stop_s) tuples."""
        return _drain_queue(self._words_q)

    async def interrupt(self) -> None:
        """Cut the current synthesis (barge-in).

        Must complete in ≤ 200 ms (CLAUDE.md §5.2). The cheapest way is to
        flush the outbound queue immediately and tell the SDK to abort —
        the SDK's own cancellation may not be instant, so we bias toward
        not playing any more buffered audio rather than waiting for ack.
        """
        _drain_queue_sync(self._audio_q)
        _drain_queue_sync(self._words_q)
        if self._stream is None:
            return
        try:
            await self._stream.interrupt()
        except Exception:  # noqa: BLE001
            logger.exception("gradium_tts_interrupt_error")

    async def close(self) -> None:
        """Close the SDK connection."""
        await self._teardown_stream()
        # Signal the public iterators that no more events are coming.
        await self._audio_q.put(None)
        await self._words_q.put(None)

    # ----- internals ----------------------------------------------------

    async def _teardown_stream(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reader_task = None

        if self._stream is not None:
            try:
                await self._stream.close()
            except Exception:  # noqa: BLE001
                logger.exception("gradium_tts_close_error")
            self._stream = None
        self._connected_voice = None
        self._connected_language = None

    async def _read_loop(self) -> None:
        """Drain the SDK event stream into the audio + word-timing queues."""
        assert self._stream is not None
        try:
            async for event in self._stream.events():
                etype = event.get("type")
                if etype == "audio":
                    audio = event.get("audio")
                    if audio:
                        await self._audio_q.put(audio)
                elif etype == "text":
                    word = event.get("text", "")
                    start = float(event.get("start_s", 0.0))
                    stop = float(event.get("stop_s", start))
                    await self._words_q.put(WordTiming(text=word, start_s=start, stop_s=stop))
                elif etype == "error":
                    logger.warning(
                        "gradium_tts_event_error",
                        extra={"detail": event.get("detail")},
                    )
                # Unknown event types are silently dropped — Gradium may
                # add new event types and we shouldn't crash on them.
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("gradium_tts_read_error")


# ---------------------------------------------------------------------------
# SDK adapter — every real ``gradium`` import lives here.
# ---------------------------------------------------------------------------


class _GradiumStreamAdapter:
    """Adapts whatever shape the Gradium SDK stream object has to the
    methods the client expects.

    Methods we rely on:

    * ``async send_text(text: str)`` — push text fragment.
    * ``events() -> AsyncIterator[dict]`` — async iterate event dicts
      with at least ``{"type": "audio"|"text"|"error", ...}``.
    * ``async interrupt()`` — abort current synthesis (barge-in).
    * ``async close()`` — tear down.

    The constructor stores the raw SDK objects so subclasses / tests can
    monkeypatch as needed.
    """

    def __init__(self, sdk_stream: Any) -> None:
        self._raw = sdk_stream

    async def send_text(self, text: str) -> None:
        # TODO(verify-sdk): real method name. Common candidates:
        # ``send_text(text)``, ``send(text)``, ``write(text)``.
        send = getattr(self._raw, "send_text", None) or getattr(self._raw, "send", None)
        if send is None:
            raise RuntimeError("Gradium SDK stream has no send_text/send method")
        await send(text)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        # TODO(verify-sdk): real iterator method. ``events()``,
        # ``__aiter__``, or ``receive()`` are all plausible.
        for attr in ("events", "receive"):
            method = getattr(self._raw, attr, None)
            if method is not None:
                async for event in method():
                    yield _normalize_event(event)
                return
        async for event in self._raw:  # ``async for stream``
            yield _normalize_event(event)

    async def interrupt(self) -> None:
        for attr in ("interrupt", "cancel", "abort"):
            method = getattr(self._raw, attr, None)
            if method is not None:
                await method()
                return

    async def close(self) -> None:
        for attr in ("end_of_stream", "close"):
            method = getattr(self._raw, attr, None)
            if method is not None:
                await method()
                return


def _normalize_event(event: Any) -> dict[str, Any]:
    """Coerce SDK events (dataclass / dict / pydantic) to a plain dict."""
    if isinstance(event, dict):
        return event
    # pydantic v2
    dump = getattr(event, "model_dump", None)
    if callable(dump):
        return dump()  # type: ignore[no-any-return]
    # dataclass
    if hasattr(event, "__dataclass_fields__"):
        from dataclasses import asdict  # noqa: PLC0415 — local import is fine here

        return asdict(event)
    # Fallback: read named attrs.
    return {k: getattr(event, k, None) for k in ("type", "audio", "text", "start_s", "stop_s", "detail")}


def _build_client(api_key: str, *, endpoint: str | None) -> Any:
    """Construct the underlying ``gradium`` SDK client."""
    try:
        from gradium.client import GradiumClient  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "gradium SDK is not installed; install it or supply a mock TTS client"
        ) from exc

    kwargs: dict[str, Any] = {"api_key": api_key}
    if endpoint:
        kwargs["endpoint"] = endpoint
    return GradiumClient(**kwargs)


async def _open_stream(
    client: Any,
    *,
    voice_id: str,
    language: str,
    output_format: str,
    json_config: dict[str, Any],
) -> _GradiumStreamAdapter:
    """Open a streaming TTS session against the SDK client."""
    # TODO(verify-sdk): replace this resolution with the actual entrypoint.
    # We probe a few plausible names so the wrapper survives minor SDK churn.
    entry_candidates = (
        ("text_to_speech", "stream"),
        ("speech", "stream_tts"),
        (None, "stream_tts"),
    )
    for ns, method in entry_candidates:
        target = client if ns is None else getattr(client, ns, None)
        if target is None:
            continue
        fn = getattr(target, method, None)
        if fn is None:
            continue
        result = fn(
            voice_id=voice_id,
            language=language,
            output_format=output_format,
            json_config=json_config,
        )
        # Result may be an awaitable returning a stream, or an async ctx mgr.
        if hasattr(result, "__aenter__"):
            stream = await result.__aenter__()
        else:
            stream = await result
        return _GradiumStreamAdapter(stream)
    raise RuntimeError(
        "Could not locate the Gradium streaming TTS entrypoint; "
        "update _open_stream() to match the installed SDK."
    )


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------


async def _drain_queue(queue: asyncio.Queue[Any]) -> AsyncIterator[Any]:
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item


def _drain_queue_sync(queue: asyncio.Queue[Any]) -> None:
    """Pull every pending item off ``queue`` without awaiting."""
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
