"""Twilio voice webhook → TwiML.

Returns the TwiML document that:

1. Speaks the greeting + AI disclosure + recording-consent prompt in the
   default language (text comes from :mod:`app.llm.prompts` so it stays
   localizable).
2. Opens a bidirectional Media Stream pointed at our WS endpoint so the
   rest of the conversation runs over our own pipeline.

We intentionally do not try to read the caller's first utterance with
``<Gather>`` / DTMF — STT runs over the Media Stream once it's connected.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from twilio.twiml.voice_response import Connect, Stream, VoiceResponse

from app.config import Settings
from app.llm.prompts import render_preamble


def build_voice_response(settings: Settings) -> str:
    """Build the TwiML returned from ``POST /twilio/voice``.

    The greeting/disclosure/consent text is spoken by Twilio's built-in
    ``<Say>`` here (no Gradium round-trip needed before the Media Stream is
    even connected). Once the WS is up, all subsequent audio flows through
    Gradium TTS.
    """
    response = VoiceResponse()

    preamble = render_preamble(
        language=settings.default_language,
        company_name=settings.company_name,
        default_language=settings.default_language,
    )
    # ``language`` on <Say> is locale-specific (en-US, de-DE…). Map the ISO
    # 639-1 code to a sensible Polly locale.
    response.say(preamble, language=_polly_locale(settings.default_language))

    connect = Connect()
    connect.append(Stream(url=_stream_url(settings.public_base_url)))
    response.append(connect)

    return str(response)


def _stream_url(public_base_url: str) -> str:
    """Convert ``https://host`` → ``wss://host/twilio/stream``."""
    parsed = urlparse(public_base_url)
    scheme = "wss" if parsed.scheme in ("https", "wss") else "ws"
    return urlunparse((scheme, parsed.netloc, "/twilio/stream", "", "", ""))


_POLLY_LOCALES: dict[str, str] = {
    "en": "en-US",
    "de": "de-DE",
    "es": "es-ES",
    "fr": "fr-FR",
    "pt": "pt-PT",
}


def _polly_locale(language: str) -> str:
    return _POLLY_LOCALES.get(language.lower(), "en-US")
