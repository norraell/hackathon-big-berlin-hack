"""FastAPI application entry point with Twilio webhooks and WebSocket endpoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from app.config import settings
from app.telephony.twilio_handler import handle_incoming_call
from app.telephony.media_stream import MediaStreamHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None during application runtime
    """
    # Startup
    logger.info("Starting AI Claims Intake System")
    logger.info(f"Supported languages: {settings.supported_languages}")
    logger.info(f"Default language: {settings.default_language}")
    
    # TODO: Initialize database connection pool
    # TODO: Initialize Redis connection
    # TODO: Warm up AI service connections
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Claims Intake System")
    # TODO: Close database connections
    # TODO: Close Redis connections
    # TODO: Close AI service connections


# Create FastAPI application
app = FastAPI(
    title="AI Claims Intake System",
    description="AI-powered phone claims intake using Twilio, Gemini STT, Groq LLM, and Gradium TTS",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for health check.
    
    Returns:
        Status message
    """
    return {
        "status": "ok",
        "service": "AI Claims Intake System",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.
    
    Returns:
        Health status
    """
    # TODO: Add checks for database, Redis, and AI services
    return {
        "status": "healthy",
        "database": "ok",
        "redis": "ok",
        "ai_services": "ok",
    }


@app.post("/twilio/voice")
async def twilio_voice_webhook() -> Response:
    """Twilio voice webhook endpoint for incoming calls.
    
    This endpoint is called by Twilio when an incoming call is received.
    It returns TwiML instructions to establish a Media Stream.
    
    Returns:
        TwiML response with Media Stream configuration
    """
    logger.info("Received incoming call from Twilio")
    twiml_response = await handle_incoming_call()
    return Response(content=twiml_response, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for Twilio Media Streams.
    
    This endpoint handles bidirectional audio streaming with Twilio.
    It receives μ-law encoded audio from the caller and sends back
    synthesized speech from the AI agent.
    
    Args:
        websocket: WebSocket connection from Twilio
    """
    await websocket.accept()
    logger.info("Media stream WebSocket connection established")
    
    handler = MediaStreamHandler(websocket)
    
    try:
        await handler.handle_stream()
    except WebSocketDisconnect:
        logger.info("Media stream WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in media stream: {e}", exc_info=True)
    finally:
        await handler.cleanup()
        logger.info("Media stream handler cleaned up")


@app.post("/twilio/status")
async def twilio_status_callback() -> dict[str, str]:
    """Twilio status callback endpoint for call events.
    
    This endpoint receives status updates about calls (e.g., completed, failed).
    
    Returns:
        Acknowledgment response
    """
    # TODO: Process call status updates
    logger.info("Received status callback from Twilio")
    return {"status": "received"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )