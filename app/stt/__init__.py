"""Speech-to-text layer.

Streaming Gemini STT wrapper. Receives 16 kHz PCM frames (after
:mod:`app.utils.audio` upsampling) and yields incremental transcripts plus a
detected language code.
"""
