"""Text-to-speech layer (Gradium).

Holds one persistent SDK connection per :class:`Session` for connection
multiplexing (CLAUDE.md §6). Output is 24 kHz PCM, resampled and μ-law
encoded by :mod:`app.utils.audio` before being framed back to Twilio.
"""
