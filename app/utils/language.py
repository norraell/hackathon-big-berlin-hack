"""Language detection helpers.

Stub for now. The real implementation will probably read the language code
out of the Gemini STT response (it returns a detected language) and fall
back to a fastText / character-ngram classifier on the partial transcript.
"""

from __future__ import annotations


def normalize_language(lang: str | None) -> str | None:
    """Return a lowercased ISO 639-1 code, or ``None`` if missing."""
    if not lang:
        return None
    return lang.strip().lower()[:2] or None
