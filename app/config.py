"""Application configuration using pydantic-settings."""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Twilio Configuration
    twilio_account_sid: str = Field(..., description="Twilio Account SID")
    twilio_api_key_sid: str = Field(..., description="Twilio API key SID")
    twilio_phone_number: str = Field(..., description="Twilio Phone Number")

    # AI Service API Keys
    gemini_api_key: str = Field(..., description="Google Gemini API Key")
    gradium_api_key: str = Field(..., description="Gradium API Key")

    # Gradium TTS Configuration
    gradium_tts_voice_id: str = Field(..., description="Default Gradium voice ID")
    gradium_tts_endpoint: str = Field(
        default="wss://api.gradium.ai/api/speech/tts",
        description="Gradium TTS WebSocket endpoint",
    )

    # Database Configuration
    database_url: str = Field(..., description="PostgreSQL database URL")

    # Application Configuration
    public_base_url: str = Field(..., description="Public base URL for webhooks")
    default_language: str = Field(default="en", description="Default language code")
    supported_languages: str = Field(
        default="en,de,es,fr,pt",
        description="Comma-separated list of supported language codes",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    
    # STT Provider Configuration
    stt_provider: str = Field(
        default="google_cloud",
        description="STT provider: 'gemini' (requires Live API access) or 'google_cloud' (production-ready)"
    )

    # Security
    secret_key: str = Field(..., description="Secret key for encryption")

    # Data Retention (days)
    audio_retention_days: int = Field(
        default=30,
        description="Number of days to retain audio recordings",
    )
    transcript_retention_days: int = Field(
        default=90,
        description="Number of days to retain transcripts",
    )

    # Latency Configuration
    max_llm_timeout_seconds: float = Field(
        default=3.0,
        description="Maximum LLM call timeout in seconds",
    )
    max_stt_confidence_threshold: float = Field(
        default=0.7,
        description="Minimum STT confidence threshold",
    )
    barge_in_cutoff_ms: int = Field(
        default=200,
        description="Barge-in cutoff time in milliseconds",
    )

    # Language-specific voice mapping
    language_voice_map: dict[str, str] = Field(
        default_factory=lambda: {
            "en": "default_en_voice",
            "de": "default_de_voice",
            "es": "default_es_voice",
            "fr": "default_fr_voice",
            "pt": "default_pt_voice",
        },
        description="Mapping of language codes to Gradium voice IDs",
    )

    @field_validator("supported_languages")
    @classmethod
    def parse_supported_languages(cls, v: str) -> List[str]:
        """Parse comma-separated supported languages into a list."""
        return [lang.strip() for lang in v.split(",")]

    def get_voice_for_language(self, language: str) -> str:
        """Get the appropriate voice ID for a given language.
        
        Args:
            language: Language code (e.g., 'en', 'de')
            
        Returns:
            Voice ID for the language, or default voice if not found
        """
        return self.language_voice_map.get(language, self.gradium_tts_voice_id)


# Global settings instance
# Settings are automatically loaded from environment variables via pydantic-settings
settings = Settings()  # type: ignore[call-arg]

 
