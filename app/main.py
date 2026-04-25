"""FastAPI application entry point.

Wires the three public surfaces:

* ``GET /health`` — liveness probe.
* ``POST /twilio/voice`` — Twilio Programmable Voice webhook; returns TwiML.
* ``WS /twilio/stream`` — Twilio Media Streams bidirectional WebSocket.

This module deliberately stays thin: routing only. All business logic lives
in :mod:`app.telephony`, :mod:`app.dialog`, and the provider modules.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Response, WebSocket
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dialog.session import default_store
from app.telephony.media_stream import handle_media_stream
from app.telephony.twilio_handler import build_voice_response

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    app = FastAPI(title="Voice Intake Agent", version="0.1.0")

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.post("/twilio/voice")
    async def twilio_voice() -> Response:
        twiml = build_voice_response(settings)
        return Response(content=twiml, media_type="application/xml")

    @app.websocket("/twilio/stream")
    async def twilio_stream(websocket: WebSocket) -> None:
        await handle_media_stream(websocket, default_store(), settings=settings)

    return app


# Uvicorn entry point: ``uvicorn app.main:app``.
# We instantiate lazily inside ``create_app`` so tests can override settings
# before the app is built.
try:
    app = create_app()
except Exception:  # pragma: no cover — surfaced loudly at import time
    logger.exception("failed_to_create_app")
    raise
