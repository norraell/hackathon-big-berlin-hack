"""Telephony layer.

* ``twilio_handler.py`` — turns the inbound voice webhook into TwiML that
  plays the greeting/disclosure/consent and connects the call to the WS
  Media Stream.
* ``media_stream.py`` — async WebSocket handler that receives Twilio's
  μ-law frames, decodes them, holds the per-call :class:`Session`, and
  (in later tasks) fans audio out to STT/LLM/TTS.
"""
