"""FastAPI application entry point with Twilio webhooks and WebSocket endpoint."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Form, WebSocket, WebSocketDisconnect
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
    
    # Initialize database
    try:
        from app.database import init_db
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    
    # TODO: Warm up AI service connections
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Claims Intake System")
    
    # Close database connections
    try:
        from app.database import close_db
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}", exc_info=True)
    
    # TODO: Close AI service connections


# Create FastAPI application
app = FastAPI(
    title="AI Claims Intake System",
    description="AI-powered phone claims intake using Twilio, Google Cloud STT, Gemini LLM, and Gradium TTS",
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
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "ai_services": "not_implemented",
    }
    
    # Check database connection
    try:
        from app.database import async_engine
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["database"] = "error"
        health_status["status"] = "degraded"
    
    return health_status


@app.post("/twilio/voice")
async def twilio_voice_webhook(
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    CallSid: Optional[str] = Form(None),
) -> Response:
    """Twilio voice webhook endpoint for incoming calls.
    
    This endpoint is called by Twilio when an incoming call is received.
    It returns TwiML instructions to establish a Media Stream.
    
    Args:
        From: Caller's phone number (from Twilio form data)
        To: Called phone number (from Twilio form data)
        CallSid: Unique call identifier (from Twilio form data)
    
    Returns:
        TwiML response with Media Stream configuration
    """
    logger.info(f"Received incoming call from Twilio - From: {From}, To: {To}, CallSid: {CallSid}")
    twiml_response = await handle_incoming_call(
        from_number=From,
        to_number=To,
        call_sid=CallSid,
    )
    return Response(content=twiml_response, media_type="application/xml")


@app.get("/media-stream/health")
async def media_stream_health() -> dict[str, str]:
    """Health check endpoint for media stream WebSocket.
    
    This endpoint verifies that the media stream WebSocket endpoint
    is properly configured and ready to accept connections.
    
    Returns:
        Health status of the media stream endpoint
    """
    return {
        "status": "ok",
        "endpoint": "/media-stream",
        "type": "websocket",
        "message": "Media stream WebSocket endpoint is configured and ready",
    }


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


@app.post("/api/verify-policy")
async def verify_policy_endpoint(
    request: dict,
) -> dict:
    """Verify policy and insurant information.
    
    Args:
        request: Verification request with policy identifiers
        
    Returns:
        Verification response
    """
    from app.database import get_db
    from app.claims.verification import VerificationService
    from app.claims.insurant_models import VerificationRequest
    
    try:
        from app.database import get_async_session
        
        verification_request = VerificationRequest(**request)
        
        async with get_async_session() as session:
            verification_service = VerificationService(session)
            result = await verification_service.verify_policy(verification_request)
            
        return result.model_dump()
        
    except Exception as e:
        logger.error(f"Error verifying policy: {e}", exc_info=True)
        return {
            "verified": False,
            "message": f"Verification error: {str(e)}",
            "coverage_active": False,
            "can_file_claim": False,
        }


@app.get("/api/policy/{policy_number}")
async def get_policy_endpoint(policy_number: str) -> dict:
    """Get policy information by policy number.
    
    Args:
        policy_number: Policy number
        
    Returns:
        Policy information
    """
    from app.database import get_db
    from app.claims.insurant_models import Policy
    from sqlalchemy import select
    
    try:
        from app.database import get_async_session
        
        async with get_async_session() as session:
            query = select(Policy).where(Policy.policy_number == policy_number)
            result = await session.execute(query)
            policy = result.scalar_one_or_none()
            
            if not policy:
                return {"error": "Policy not found"}
            
            return {
                "policy_id": policy.policy_id,
                "policy_number": policy.policy_number,
                "product_name": policy.product_name,
                "license_plate": policy.license_plate,
                "vehicle_make": policy.vehicle_make,
                "vehicle_model": policy.vehicle_model,
                "status": policy.status,
                "has_vollkasko": policy.has_vollkasko,
                "has_teilkasko": policy.has_teilkasko,
            }
            
    except Exception as e:
        logger.error(f"Error getting policy: {e}", exc_info=True)
        return {"error": str(e)}


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