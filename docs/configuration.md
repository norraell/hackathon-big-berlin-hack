# Configuration

Configuration is loaded by `app/config.py` from `.env` (and process
environment) via `pydantic-settings`. Validation runs at process start so
a misconfigured deployment fails loudly instead of crashing mid-call.

## Files

- `.env.example` — template, checked in. Copy to `.env` for local dev.
- `.env` — your real values. **Git-ignored.**
- `app/config.py` — the `Settings` model and validators.

## Required variables

### Twilio

We use API Key auth (SK + Secret), not the legacy Auth Token. Create a
key in **Console → Account → API keys & tokens**; the secret is shown
**once at creation**.

| Variable | Format | Notes |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | `AC` + 32 hex | Identifies which account the API key belongs to |
| `TWILIO_API_KEY_SID` | `SK` + 32 hex | The API key |
| `TWILIO_API_KEY_SECRET` | opaque | Shown once — recreate the key if you lose it |
| `TWILIO_PHONE_NUMBER` | E.164, e.g. `+15551234567` | The number you bought / ported |

### Provider API keys

Gemini handles **both** STT (Live API) and the dialog LLM, so a single
`GEMINI_API_KEY` covers both call sites.

| Variable | Notes |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key |
| `GRADIUM_API_KEY` | Gradium TTS key |

### Optional model overrides

Google rotates Live model IDs aggressively. Override without redeploying:

| Variable | Default | Notes |
|---|---|---|
| `GEMINI_LIVE_MODEL` | `gemini-2.5-flash-native-audio-latest` | STT (Live API, `bidiGenerateContent`) |
| `GEMINI_LLM_MODEL` | `gemini-2.5-flash` | Dialog LLM (`generate_content`) |

### Voice configuration

Either `GRADIUM_VOICE_ID` is set as the global default, **or**
`LANGUAGE_VOICE_MAP` covers every entry in `SUPPORTED_LANGUAGES`. If
neither is satisfied for some language, `Settings` raises at startup.

| Variable | Format | Notes |
|---|---|---|
| `GRADIUM_VOICE_ID` | opaque ID | Copied from Gradium Studio (like an ElevenLabs voice ID) |
| `GRADIUM_ENDPOINT` | URL | Optional; only set to point at staging |
| `LANGUAGE_VOICE_MAP` | `lang=voiceId,lang=voiceId` | Per-language overrides; wins over `GRADIUM_VOICE_ID` |

Lookup is in `Settings.voice_for(language)`:

1. `LANGUAGE_VOICE_MAP[language]` if present
2. `GRADIUM_VOICE_ID` if set
3. `KeyError` otherwise

### Storage

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://intake:intake@localhost:5432/intake` | Async driver required |
| `REDIS_URL` | `redis://localhost:6379/0` | Used for session state in prod |

### Public URL

`PUBLIC_BASE_URL` is the host Twilio reaches. In dev that's your ngrok
HTTPS URL; in prod it's the ALB hostname (or your custom domain via ACM).
The Twilio handler converts `https://...` to `wss://.../twilio/stream`
automatically.

### Locale

| Variable | Default | Notes |
|---|---|---|
| `DEFAULT_LANGUAGE` | `en` | Spoken in the initial greeting; must be in `SUPPORTED_LANGUAGES` |
| `SUPPORTED_LANGUAGES` | `en,de,es,fr,pt` | CSV; **must** be a subset of Gradium's supported set |

`GRADIUM_SUPPORTED_LANGUAGES = {"en", "fr", "de", "es", "pt"}`. If STT
detects a language outside this set, the agent apologizes in English and
offers a human callback (see `app/llm/prompts.py` →
`UNSUPPORTED_LANGUAGE_FALLBACK_EN`).

### Misc

| Variable | Default | Notes |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Standard Python log level |
| `SLA_HOURS` | `24` | Read aloud at close ("a human will follow up within … hours") |
| `COMPANY_NAME` | `the company` | Substituted into greeting/system prompt |

## Validators (`app/config.py`)

The model validator enforces:

1. `SUPPORTED_LANGUAGES ⊆ {"en", "fr", "de", "es", "pt"}`. Anything else
   raises `ValueError` at startup.
2. `DEFAULT_LANGUAGE ∈ SUPPORTED_LANGUAGES`.
3. Voice config completeness: `GRADIUM_VOICE_ID` set, **or**
   `LANGUAGE_VOICE_MAP` covers every entry in `SUPPORTED_LANGUAGES`.

These run in `_validate_languages_and_voices`. Failures surface at the
first call to `get_settings()` (typically `app.main:create_app`).

## Reading settings in code

```python
from app.config import get_settings

settings = get_settings()        # cached singleton
voice_id = settings.voice_for("de")
```

`get_settings()` is `lru_cache(1)`. In tests you can override env vars
before the first call, or reset the cache with
`get_settings.cache_clear()`.

## Sample `.env`

See [`.env.example`](../.env.example). The shipping template includes
inline comments that match this document.
