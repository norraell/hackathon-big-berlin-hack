"""Language detection and handling utilities."""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def is_language_supported(language: str) -> bool:
    """Check if a language is supported.
    
    Args:
        language: Language code (e.g., 'en', 'de')
        
    Returns:
        True if language is supported
    """
    return language in settings.supported_languages


def get_default_language() -> str:
    """Get the default language.
    
    Returns:
        Default language code
    """
    return settings.default_language


def normalize_language_code(language: str) -> str:
    """Normalize a language code to standard format.
    
    Args:
        language: Language code (may include region, e.g., 'en-US')
        
    Returns:
        Normalized language code (e.g., 'en')
    """
    # Extract base language code (before any dash or underscore)
    if "-" in language:
        language = language.split("-")[0]
    if "_" in language:
        language = language.split("_")[0]
    
    return language.lower()


def get_fallback_language(language: str) -> str:
    """Get a fallback language if the requested one is not supported.
    
    Args:
        language: Requested language code
        
    Returns:
        Supported language code (original or fallback)
    """
    normalized = normalize_language_code(language)
    
    if is_language_supported(normalized):
        return normalized
    
    logger.warning(
        f"Language '{language}' not supported, falling back to "
        f"{settings.default_language}"
    )
    
    return settings.default_language


def detect_language_from_text(text: str) -> Optional[str]:
    """Attempt to detect language from text content.
    
    This is a simple heuristic-based approach. For production,
    consider using a proper language detection library.
    
    Args:
        text: Text to analyze
        
    Returns:
        Detected language code or None
    """
    # Simple keyword-based detection
    # In production, use a library like langdetect or fasttext
    
    text_lower = text.lower()
    
    # German indicators
    if any(word in text_lower for word in ["ich", "der", "die", "das", "und", "ist"]):
        return "de"
    
    # Spanish indicators
    if any(word in text_lower for word in ["el", "la", "los", "las", "es", "está"]):
        return "es"
    
    # French indicators
    if any(word in text_lower for word in ["le", "la", "les", "est", "je", "tu"]):
        return "fr"
    
    # Portuguese indicators
    if any(word in text_lower for word in ["o", "a", "os", "as", "é", "está"]):
        return "pt"
    
    # Default to English
    return "en"


def get_language_name(language_code: str) -> str:
    """Get the full name of a language from its code.
    
    Args:
        language_code: Language code (e.g., 'en')
        
    Returns:
        Language name (e.g., 'English')
    """
    language_names = {
        "en": "English",
        "de": "German",
        "es": "Spanish",
        "fr": "French",
        "pt": "Portuguese",
    }
    
    return language_names.get(language_code, language_code.upper())


def format_language_list(languages: list[str]) -> str:
    """Format a list of language codes as a human-readable string.
    
    Args:
        languages: List of language codes
        
    Returns:
        Formatted string (e.g., "English, German, and Spanish")
    """
    if not languages:
        return ""
    
    if len(languages) == 1:
        return get_language_name(languages[0])
    
    names = [get_language_name(lang) for lang in languages]
    
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    
    return ", ".join(names[:-1]) + f", and {names[-1]}"


class LanguageContext:
    """Context manager for tracking language changes in a conversation."""
    
    def __init__(self, initial_language: str = "en") -> None:
        """Initialize language context.
        
        Args:
            initial_language: Starting language
        """
        self.current_language = get_fallback_language(initial_language)
        self.language_history: list[tuple[str, str]] = []  # (language, reason)
        
        logger.info(f"LanguageContext initialized with language: {self.current_language}")
    
    def change_language(self, new_language: str, reason: str = "") -> bool:
        """Change the current language.
        
        Args:
            new_language: New language code
            reason: Reason for change (for logging)
            
        Returns:
            True if language was changed
        """
        normalized = normalize_language_code(new_language)
        
        if not is_language_supported(normalized):
            logger.warning(f"Cannot change to unsupported language: {new_language}")
            return False
        
        if normalized == self.current_language:
            logger.debug(f"Language already set to {normalized}")
            return False
        
        old_language = self.current_language
        self.current_language = normalized
        self.language_history.append((normalized, reason))
        
        logger.info(
            f"Language changed from {old_language} to {normalized}"
            + (f" ({reason})" if reason else "")
        )
        
        return True
    
    def get_current_language(self) -> str:
        """Get the current language.
        
        Returns:
            Current language code
        """
        return self.current_language
    
    def get_language_history(self) -> list[tuple[str, str]]:
        """Get the history of language changes.
        
        Returns:
            List of (language, reason) tuples
        """
        return self.language_history.copy()
    
    def has_changed_language(self) -> bool:
        """Check if language has been changed during the conversation.
        
        Returns:
            True if language has changed at least once
        """
        return len(self.language_history) > 0