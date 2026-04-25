"""Orchestrator wiring tests.

We don't depend on real Gemini / Gradium SDKs here. Instead we plug in
in-process mocks that satisfy the orchestrator's protocols, drive a
turn through, and assert the boundary effects:

* Caller PCM is fed to STT.
* STT final → LLM is invoked with a transcript ending in the user turn.
* LLM text deltas → TTS.send_text.
* TTS audio → outbound Twilio media frame on the WS.
* Voiced caller audio while TTS is active → tts.interrupt() is called.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.config import GRADIUM_SUPPORTED_LANGUAGES, Settings
from app.dialog.orchestrator import CallOrchestrator
from app.dialog.session import Session
from app.llm.client import LLMDelta
from app.stt.gemini_stt import STTResult
from app.tts.gradium_tts import WordTiming
from app.utils.audio import (
    GRADIUM_RATE,
    PCM_SAMPLE_WIDTH,
    pcm16_to_mulaw,
)

# Belt-and-suspenders: keep the orchestrator's TTS audio iterator under a
# bounded duration so a stuck pump doesn't hang CI.
_TEST_TIMEOUT_S = 3.0


# ---------------------------------------------------------------------------
# Mock provider implementations
# ---------------------------------------------------------------------------


class MockSTT:
    def __init__(self) -> None:
        self.fed: list[bytes] = []
        self.started_with: str | None = None
        self.closed = False
        self._results: asyncio.Queue[STTResult | None] = asyncio.Queue()

    async def start(self, language: str | None = None) -> None:
        self.started_with = language

    async def feed_audio(self, pcm_16k: bytes) -> None:
        self.fed.append(pcm_16k)

    def results(self) -> AsyncIterator[STTResult]:
        async def _gen() -> AsyncIterator[STTResult]:
            while True:
                item = await self._results.get()
                if item is None:
                    return
                yield item

        return _gen()

    async def close(self) -> None:
        self.closed = True
        await self._results.put(None)

    # Test helpers
    async def emit(self, text: str, *, is_final: bool = True, language: str | None = "en") -> None:
        await self._results.put(STTResult(text=text, is_final=is_final, language=language))


class MockLLM:
    def __init__(self, deltas: list[LLMDelta] | None = None) -> None:
        self.deltas = deltas or [LLMDelta(text="Got it. "), LLMDelta(text="Bye."), LLMDelta(finish=True)]
        self.calls: list[dict[str, Any]] = []

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]:
        self.calls.append({"messages": list(messages), "language": language})
        for d in self.deltas:
            yield d


class MockTTS:
    def __init__(self) -> None:
        self.connected: tuple[str, str] | None = None
        self.text_received: list[str] = []
        self.interrupt_count = 0
        self.closed = False
        self._audio: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._words: asyncio.Queue[WordTiming | None] = asyncio.Queue()

    async def connect(self, voice_id: str, language: str) -> None:
        self.connected = (voice_id, language)

    async def send_text(self, text: str) -> None:
        self.text_received.append(text)

    def iter_audio(self) -> AsyncIterator[bytes]:
        async def _gen() -> AsyncIterator[bytes]:
            while True:
                item = await self._audio.get()
                if item is None:
                    return
                yield item

        return _gen()

    def iter_word_timings(self) -> AsyncIterator[WordTiming]:
        async def _gen() -> AsyncIterator[WordTiming]:
            while True:
                item = await self._words.get()
                if item is None:
                    return
                yield item

        return _gen()

    async def interrupt(self) -> None:
        self.interrupt_count += 1
        # Mimic the real TTS draining the audio queue on interrupt.
        while not self._audio.empty():
            self._audio.get_nowait()

    async def close(self) -> None:
        self.closed = True
        await self._audio.put(None)
        await self._words.put(None)

    # Test helpers
    async def push_audio(self, pcm_24k: bytes) -> None:
        await self._audio.put(pcm_24k)

    async def push_word(self, text: str, start_s: float, stop_s: float) -> None:
        await self._words.put(WordTiming(text=text, start_s=start_s, stop_s=stop_s))


class MockWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_settings() -> Settings:
    return Settings(
        twilio_account_sid="AC" + "x" * 32,
        twilio_api_key_sid="SK" + "x" * 32,
        twilio_api_key_secret="secret",
        twilio_phone_number="+10000000000",
        gemini_api_key="g",
        gradium_api_key="r",
        gradium_voice_id="voice_default",
        database_url="postgresql+asyncpg://x/y",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://example.test",
        default_language="en",
        supported_languages=list(GRADIUM_SUPPORTED_LANGUAGES),
    )


@pytest.fixture
def session() -> Session:
    return Session(call_sid="CA_test", stream_sid="MZ_test")


@pytest.fixture
def settings() -> Settings:
    return _make_settings()


def _silence_pcm_24k(seconds: float = 0.02) -> bytes:
    """24 kHz s16le silence — used as TTS audio."""
    n_samples = int(GRADIUM_RATE * seconds)
    return b"\x00\x00" * n_samples


def _voiced_mulaw_payload(seconds: float = 0.02) -> bytes:
    """Synthesize a tone, μ-law-encode it: triggers VAD as voiced."""
    import math

    rate = 8_000
    n = int(rate * seconds)
    pcm = bytearray()
    for i in range(n):
        val = int(0.5 * 32767 * math.sin(2 * math.pi * 300 * i / rate))
        pcm += val.to_bytes(2, "little", signed=True)
    return pcm16_to_mulaw(bytes(pcm))


def _silent_mulaw_payload(seconds: float = 0.02) -> bytes:
    rate = 8_000
    n = int(rate * seconds)
    return pcm16_to_mulaw(b"\x00\x00" * n)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_caller_audio_is_forwarded_to_stt(session: Session, settings: Settings) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        await orch.feed_caller_audio(_silent_mulaw_payload())
        assert len(stt.fed) == 1
        # Upsampled from 8k to 16k → roughly double the byte count.
        assert len(stt.fed[0]) > 0
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_stt_final_dispatches_to_llm_and_tts(session: Session, settings: Settings) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        await stt.emit("Hello there.", is_final=True, language="en")

        # Wait for the LLM call to land + TTS to receive both deltas.
        async def _wait() -> None:
            while not (llm.calls and len(tts.text_received) >= 2):
                await asyncio.sleep(0.01)

        await asyncio.wait_for(_wait(), timeout=_TEST_TIMEOUT_S)

        assert llm.calls[0]["messages"][-1] == {"role": "user", "content": "Hello there."}
        assert llm.calls[0]["language"] == "en"
        assert tts.text_received == ["Got it. ", "Bye."]
        # Caller turn captured on the session.
        assert any(t.speaker == "caller" and t.text == "Hello there." for t in session.transcript)
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_tts_audio_is_resampled_and_sent_as_media_frame(
    session: Session, settings: Settings
) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        # Push enough 24 kHz silence to produce at least one 160-byte μ-law frame.
        # 0.04 s @ 24k → 0.04 s @ 8k → 320 μ-law bytes → 2 frames of 160.
        await tts.push_audio(_silence_pcm_24k(seconds=0.04))

        async def _wait() -> None:
            while not ws.sent:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(_wait(), timeout=_TEST_TIMEOUT_S)

        frame = json.loads(ws.sent[0])
        assert frame["event"] == "media"
        assert frame["streamSid"] == "MZ_test"
        payload = base64.b64decode(frame["media"]["payload"])
        # Each outbound frame is 160 μ-law bytes (~20 ms @ 8 kHz).
        assert len(payload) == 160
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_barge_in_calls_interrupt_and_truncates_transcript(
    session: Session, settings: Settings
) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        # Set up an in-flight assistant turn with two spoken words so we
        # have something to truncate to.
        session.add_turn("agent", "Hello there friend")
        session.transcript[-1].word_timings = [
            ("Hello", 0.0, 0.30),
            ("there", 0.31, 0.60),
        ]
        # Force the orchestrator to think TTS is mid-stream.
        async with orch._tts_active_lock:  # type: ignore[attr-defined]
            orch._tts_active = True  # type: ignore[attr-defined]

        # A voiced frame from the caller while TTS is "active".
        await orch.feed_caller_audio(_voiced_mulaw_payload(seconds=0.04))

        assert tts.interrupt_count == 1
        assert session.transcript[-1].text == "Hello there"
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_silent_caller_audio_does_not_interrupt(
    session: Session, settings: Settings
) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        async with orch._tts_active_lock:  # type: ignore[attr-defined]
            orch._tts_active = True  # type: ignore[attr-defined]
        await orch.feed_caller_audio(_silent_mulaw_payload(seconds=0.04))
        assert tts.interrupt_count == 0
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_word_timings_attach_to_latest_agent_turn(
    session: Session, settings: Settings
) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    try:
        session.add_turn("agent", "Hi.")
        await tts.push_word("Hi", 0.0, 0.2)

        async def _wait() -> None:
            while not session.transcript[-1].word_timings:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(_wait(), timeout=_TEST_TIMEOUT_S)
        assert session.transcript[-1].word_timings[0] == ("Hi", 0.0, 0.2)
    finally:
        await orch.stop()


@pytest.mark.asyncio
async def test_stop_closes_stt_and_tts(session: Session, settings: Settings) -> None:
    stt, llm, tts, ws = MockSTT(), MockLLM(), MockTTS(), MockWebSocket()
    orch = CallOrchestrator(
        session=session, settings=settings, websocket=ws, stt=stt, llm=llm, tts=tts
    )
    await orch.start()
    await orch.stop()
    assert stt.closed is True
    assert tts.closed is True
