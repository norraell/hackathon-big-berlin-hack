"""Twilio Media Streams WebSocket handler.

Stays thin — parses Twilio's four JSON frame types (``connected``,
``start``, ``media``, ``stop``) and delegates the audio/dialog pipeline
to :class:`app.dialog.orchestrator.CallOrchestrator`. Provider clients
(STT/LLM/TTS) are constructed via small factories so tests can substitute
mocks without touching the WS layer.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.config import Settings, get_settings
from app.dialog.orchestrator import CallOrchestrator
from app.dialog.session import Session, SessionStore
from app.llm.client import EchoLLMClient
from app.stt.gemini_stt import GeminiSTTClient
from app.tts.gradium_tts import GradiumTTSClient

logger = logging.getLogger(__name__)


# A factory builds the orchestrator for a given session. Default factory
# wires the real provider clients; tests inject a mock factory.
OrchestratorFactory = Callable[[Session, WebSocket, Settings], CallOrchestrator]


def default_orchestrator_factory(
    session: Session, websocket: WebSocket, settings: Settings
) -> CallOrchestrator:
    """Build a CallOrchestrator with the real provider clients."""
    stt_kwargs: dict[str, Any] = {"api_key": settings.gemini_api_key}
    if settings.gemini_live_model:
        stt_kwargs["model"] = settings.gemini_live_model
    stt = GeminiSTTClient(**stt_kwargs)
    # LLM stays the echo stub until task 4 lands. Swap to GeminiLLMClient
    # in one line once the real client is implemented.
    llm = EchoLLMClient()
    tts = GradiumTTSClient(api_key=settings.gradium_api_key, endpoint=settings.gradium_endpoint)
    return CallOrchestrator(
        session=session,
        settings=settings,
        websocket=websocket,
        stt=stt,
        llm=llm,
        tts=tts,
    )


async def handle_media_stream(
    websocket: WebSocket,
    store: SessionStore,
    *,
    settings: Settings | None = None,
    orchestrator_factory: OrchestratorFactory | None = None,
) -> None:
    """Run a single Media Streams WS connection to completion."""
    settings = settings or get_settings()
    factory = orchestrator_factory or default_orchestrator_factory

    # Twilio Media Streams does not negotiate a subprotocol — we accept
    # plain. Earlier we passed ``subprotocol="audio.twilio.com"`` and Twilio
    # closed the WS immediately because it never requested that protocol.
    await websocket.accept()
    session: Session | None = None
    orchestrator: CallOrchestrator | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                frame: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("twilio_ws_bad_json", extra={"raw_len": len(raw)})
                continue

            event = frame.get("event")
            if event == "connected":
                logger.info("twilio_ws_connected", extra={"protocol": frame.get("protocol")})
            elif event == "start":
                session = _on_start(frame, store, settings)
                orchestrator = factory(session, websocket, settings)
                await orchestrator.start()
            elif event == "media":
                if orchestrator is None:
                    logger.warning("twilio_ws_media_before_start")
                    continue
                await _on_media(frame, orchestrator)
            elif event == "stop":
                _on_stop(frame, session)
                break
            else:
                logger.debug("twilio_ws_unknown_event", extra={"event": event})
    except WebSocketDisconnect:
        logger.info(
            "twilio_ws_disconnected",
            extra={"call_sid": session.call_sid if session else None},
        )
    finally:
        if orchestrator is not None:
            await orchestrator.stop()
        if session is not None:
            store.pop(session.call_sid)


def _on_start(frame: dict[str, Any], store: SessionStore, settings: Settings) -> Session:
    start = frame.get("start", {})
    call_sid = start.get("callSid", "unknown")
    stream_sid = start.get("streamSid")
    media_format = start.get("mediaFormat", {})
    codec = media_format.get("encoding")

    session = Session(
        call_sid=call_sid,
        stream_sid=stream_sid,
        codec=codec,
        language=settings.default_language,
    )
    store.put(session)
    logger.info(
        "twilio_ws_start",
        extra={
            "call_sid": call_sid,
            "stream_sid": stream_sid,
            "codec": codec,
            "sample_rate": media_format.get("sampleRate"),
            "channels": media_format.get("channels"),
        },
    )
    return session


async def _on_media(frame: dict[str, Any], orchestrator: CallOrchestrator) -> None:
    media = frame.get("media", {})
    payload_b64 = media.get("payload", "")
    if not payload_b64:
        return
    mulaw = base64.b64decode(payload_b64)
    await orchestrator.feed_caller_audio(mulaw)


def _on_stop(frame: dict[str, Any], session: Session | None) -> None:
    logger.info(
        "twilio_ws_stop",
        extra={
            "call_sid": session.call_sid if session else None,
            "stream_sid": session.stream_sid if session else None,
            "total_frames": session.media_frames if session else 0,
        },
    )
