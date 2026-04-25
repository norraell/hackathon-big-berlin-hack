"""Application configuration.

Loads environment variables (see ``.env.example`` and ``CLAUDE.md`` §8) into a
typed :class:`Settings` object via ``pydantic-settings``. Required keys are
validated at process start so a misconfigured deployment fails loudly instead
of crashing mid-call.

Constraints enforced here:

* ``GRADIUM_VOICE_ID`` must be set, **or** ``LANGUAGE_VOICE_MAP`` must cover
  every entry in ``SUPPORTED_LANGUAGES`` (CLAUDE.md §6).
* ``SUPPORTED_LANGUAGES`` must be a subset of Gradium's supported TTS
  languages: ``{"en", "fr", "de", "es", "pt"}``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Gradium TTS currently supports exactly this set; STT may detect more
# languages, but we cannot synthesize a reply outside this set. See CLAUDE.md
# §6.
GRADIUM_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "fr", "de", "es", "pt"})


def _parse_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [v.strip().lower() for v in value if v and v.strip()]
    return [v.strip().lower() for v in value.split(",") if v and v.strip()]


def _parse_voice_map(value: str | dict[str, str] | None) -> dict[str, str]:
    """Parse ``LANGUAGE_VOICE_MAP`` from ``en=abc,de=xyz`` or JSON-ish dict."""
    if not value:
        return {}
    if isinstance(value, dict):
        return {k.strip().lower(): v.strip() for k, v in value.items() if k and v}
    out: dict[str, str] = {}
    for pair in value.split(","):
        if "=" not in pair:
            continue
        lang, voice = pair.split("=", 1)
        lang = lang.strip().lower()
        voice = voice.strip()
        if lang and voice:
            out[lang] = voice
    return out


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Twilio. We use API Key auth (SK + Secret) instead of the Auth Token.
    # The Account SID (AC...) is still required because it identifies which
    # account the API key belongs to — see Twilio's REST docs.
    twilio_account_sid: str
    twilio_api_key_sid: str
    twilio_api_key_secret: str
    twilio_phone_number: str

    # Provider API keys. Gemini handles both STT and the dialog LLM, so a
    # single ``GEMINI_API_KEY`` covers both call sites.
    gemini_api_key: str
    gradium_api_key: str

    # Gemini model overrides. Defaults are the current GA / general-purpose
    # IDs, but Google rotates these often — overridable without a code change.
    gemini_live_model: str | None = None  # STT (bidiGenerateContent)
    gemini_llm_model: str | None = None  # dialog LLM (generate_content)

    # Gradium voice configuration. Either GRADIUM_VOICE_ID is set as the
    # default, or LANGUAGE_VOICE_MAP must cover SUPPORTED_LANGUAGES.
    gradium_voice_id: str | None = None
    gradium_endpoint: str | None = None  # only override for staging
    language_voice_map: Annotated[dict[str, str], NoDecode, Field(default_factory=dict)]

    # Storage
    database_url: str
    redis_url: str

    # Public URL (used by Twilio to reach our webhook)
    public_base_url: str

    # Locale
    default_language: str = "de"
    supported_languages: Annotated[list[str], NoDecode, Field(default_factory=lambda: ["en"])]

    # Misc
    log_level: str = "INFO"
    sla_hours: int = 24
    company_name: str = "the company"

    # ----- validators ---------------------------------------------------

    @field_validator("supported_languages", mode="before")
    @classmethod
    def _split_supported(cls, v: str | list[str]) -> list[str]:
        return _parse_csv(v)

    @field_validator("language_voice_map", mode="before")
    @classmethod
    def _split_voice_map(cls, v: str | dict[str, str] | None) -> dict[str, str]:
        return _parse_voice_map(v)

    @field_validator("default_language")
    @classmethod
    def _normalize_default_language(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _validate_languages_and_voices(self) -> Settings:
        # SUPPORTED_LANGUAGES must be a subset of Gradium's set.
        unsupported = sorted(set(self.supported_languages) - GRADIUM_SUPPORTED_LANGUAGES)
        if unsupported:
            raise ValueError(
                f"SUPPORTED_LANGUAGES contains languages not supported by Gradium TTS: "
                f"{unsupported}. Allowed: {sorted(GRADIUM_SUPPORTED_LANGUAGES)}"
            )
        if self.default_language not in self.supported_languages:
            raise ValueError(
                f"DEFAULT_LANGUAGE={self.default_language!r} is not in "
                f"SUPPORTED_LANGUAGES={self.supported_languages!r}"
            )

        # Voice config: at least one of GRADIUM_VOICE_ID or a complete map.
        if not self.gradium_voice_id:
            missing = sorted(set(self.supported_languages) - set(self.language_voice_map))
            if missing:
                raise ValueError(
                    "GRADIUM_VOICE_ID is unset and LANGUAGE_VOICE_MAP is missing "
                    f"voice IDs for languages: {missing}"
                )
        return self

    # ----- helpers ------------------------------------------------------

    def voice_for(self, language: str) -> str:
        """Return the Gradium voice ID to use for ``language``.

        Falls back to ``GRADIUM_VOICE_ID`` if no per-language entry is present.
        Raises ``KeyError`` if neither is configured for the language.
        """
        lang = language.strip().lower()
        if lang in self.language_voice_map:
            return self.language_voice_map[lang]
        if self.gradium_voice_id:
            return self.gradium_voice_id
        raise KeyError(f"No Gradium voice configured for language {lang!r}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings` singleton."""
    return Settings()  # type: ignore[call-arg]
