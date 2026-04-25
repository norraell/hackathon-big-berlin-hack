"""Twilio webhook handler for incoming calls and TwiML generation."""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


async def handle_incoming_call(
    from_number: Optional[str] = None,
    to_number: Optional[str] = None,
    call_sid: Optional[str] = None,
) -> str:
    """Handle incoming call from Twilio and generate TwiML response.
    
    This function generates TwiML that instructs Twilio to:
    1. Greet the caller (optional)
    2. Establish a bidirectional Media Stream to our WebSocket endpoint
    
    Args:
        from_number: Caller's phone number
        to_number: Called phone number (our Twilio number)
        call_sid: Unique identifier for this call
        
    Returns:
        TwiML XML string with Media Stream configuration
    """
    logger.info(
        f"Handling incoming call - From: {from_number}, To: {to_number}, SID: {call_sid}"
    )
    
    # Construct the WebSocket URL for Media Streams
    # Replace http:// with ws:// and https:// with wss://
    # Remove trailing slash to avoid double slashes
    base_url = settings.public_base_url.rstrip("/")
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    media_stream_url = f"{ws_url}/media-stream"
    
    # Generate TwiML response
    # The <Stream> verb establishes a bidirectional WebSocket connection
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{media_stream_url}">
            <Parameter name="callSid" value="{call_sid or 'unknown'}" />
            <Parameter name="from" value="{from_number or 'unknown'}" />
            <Parameter name="to" value="{to_number or 'unknown'}" />
        </Stream>
    </Connect>
</Response>"""
    
    logger.debug(f"Generated TwiML: {twiml}")
    return twiml


def generate_say_twiml(text: str, language: str = "en", voice: str = "Polly.Joanna") -> str:
    """Generate TwiML for text-to-speech (fallback mechanism).
    
    This is used as a fallback when the streaming TTS fails.
    
    Args:
        text: Text to speak
        language: Language code
        voice: Twilio voice name
        
    Returns:
        TwiML XML string with Say verb
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}" language="{language}">{text}</Say>
</Response>"""


def generate_hangup_twiml(message: Optional[str] = None) -> str:
    """Generate TwiML to end the call gracefully.
    
    Args:
        message: Optional message to speak before hanging up
        
    Returns:
        TwiML XML string with optional Say and Hangup verbs
    """
    if message:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{message}</Say>
    <Hangup/>
</Response>"""
    else:
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup/>
</Response>"""


def generate_redirect_twiml(url: str) -> str:
    """Generate TwiML to redirect to another URL.
    
    Args:
        url: URL to redirect to
        
    Returns:
        TwiML XML string with Redirect verb
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect>{url}</Redirect>
</Response>"""