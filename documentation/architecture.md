# Architecture Documentation

## 1. System Overview

```
Twilio Voice (phone number) ── Media Streams (bidirectional WebSocket, μ-law 8 kHz)
│
▼
FastAPI WebSocket server (this repo) ── Direct public IP (POC setup)
│
├─► Google Gemini STT (streaming, multilingual)    # speech → text
│
├─► Google Gemini LLM (gemini-1.5-flash)  # dialog policy + tool calls
│
└─► Gradium TTS (WebSocket, streaming PCM)        # text → speech
    │
    └─► Postgres                                   # claims, sessions, call state
```

**Note:** This is a POC setup with direct public IP access to ECS tasks. For production, consider adding a load balancer.

**Note on the Stack:** Google Gemini powers both the STT and LLM layers, keeping the stack unified within Google's ecosystem.

## 2. Tech Stack

| Layer      | Choice                                                                      | Why                                                                                                                                    |
|------------|-----------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| Runtime    | Python 3.11+                                                                | Best ecosystem for STT/TTS SDKs                                                                                                        |
| Web        | FastAPI + Uvicorn                                                           | Native async, WebSocket support for Twilio Media Streams                                                                               |
| Telephony  | Twilio Programmable Voice + Media Streams                                   | Inbound PSTN, bidirectional audio                                                                                                      |
| STT        | Google Gemini (Live API)                                                   | Multilingual, streaming, integrated with Gemini ecosystem                                                                              |
| LLM        | Google Gemini (`gemini-1.5-flash`)                                         | Fast response times, function calling support                                                                                          |
| TTS        | Gradium (WebSocket streaming, `wss://api.gradium.ai/api/speech/tts`)       | Sub-300 ms time-to-first-audio, word-level timestamps for accurate barge-in, connection multiplexing across turns                     |
| Storage    | Postgres (claims, transcripts, session state)                               | —                                                                                                                                      |
| Audio      | audioop / numpy for μ-law ↔ PCM resampling                                 | Twilio sends μ-law 8 kHz; STT/TTS expect 16 kHz PCM                                                                                   |

## 3. Repository Layout

```
.
├── CLAUDE.md                    # this file
├── README.md                    # human-facing setup instructions
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py                  # FastAPI app, Twilio webhooks, WS endpoint
│   ├── config.py                # pydantic-settings, loads .env
│   ├── telephony/
│   │   ├── twilio_handler.py    # incoming call webhook, TwiML generation
│   │   └── media_stream.py      # WS handler: decodes μ-law, fans out audio
│   ├── stt/
│   │   ├── __init__.py          # STT factory/protocol
│   │   ├── gemini_stt.py        # Gemini STT wrapper (default)
│   │   └── google_cloud_stt.py  # Google Cloud STT wrapper (optional, requires separate credentials)
│   ├── llm/
│   │   ├── client.py            # Gemini client, streaming completions
│   │   ├── prompts.py           # system prompt, language-specific snippets
│   │   └── tools.py             # tool/function definitions (create_claim, etc.)
│   ├── tts/
│   │   └── gradium_tts.py       # streaming Gradium TTS over WebSocket, returns μ-law chunks
│   ├── dialog/
│   │   ├── state_machine.py     # GREETING → DISCLOSURE → CONSENT → INTAKE → CONFIRM → CLOSE
│   │   └── session.py           # per-call state, transcript buffer
│   ├── claims/
│   │   ├── models.py            # SQLAlchemy/Pydantic models for Claim
│   │   └── service.py           # create_claim, attach_transcript
│   └── utils/
│       ├── audio.py             # μ-law ↔ PCM, resampling, VAD
│       └── language.py          # language detection helpers
├── tests/
│   ├── test_dialog_flow.py
│   ├── test_audio.py
│   └── fixtures/
│       └── sample_calls/        # recorded μ-law fixtures for replay tests
└── infra/
    └── docker-compose.yml       # postgres, app
```

## 4. Critical Rules (Do Not Violate)

### 4.1 Legal & Ethical

**AI disclosure is mandatory and non-negotiable.** The very first utterance after greeting must state that the caller is speaking with an AI. No "human-passing" mode, ever, even if a user/operator requests it. The EU AI Act (Article 50) and similar laws in other jurisdictions require this. The "human-like" goal applies to prosody and phrasing, not to deceiving the caller about the nature of the agent.

**Recording consent must be obtained explicitly** before any substantive intake. If the caller says no, the agent must offer an alternative (callback by human, web form) and end the call without recording the substance.

**PII handling:** Transcripts and recordings contain personal data. Encrypt at rest, set retention (default: 30 days for audio, 90 days for transcripts, indefinite for the structured claim minus raw quotes). GDPR applies — provide a deletion endpoint.

**No medical, legal, or financial advice.** This is an intake agent; it gathers facts and creates a claim. It does not diagnose, recommend treatments, or make compensation promises.

### 4.2 Engineering

**Latency budget:** end-of-user-speech → start-of-agent-audio ≤ 1500 ms p95. Anything slower feels broken on a phone line. Stream STT, stream LLM tokens, stream TTS. Never wait for a full LLM completion before starting TTS.

**Barge-in support is required.** If the caller starts speaking while the agent is talking, cut the TTS stream within 200 ms.

**All audio I/O is async.** Never block the event loop. Use `asyncio.Queue` between STT, LLM, and TTS.

**One source of truth for session state:** `app/dialog/session.py`. Don't sprinkle state into individual handlers.

**Tool calls are the only way to mutate data.** The LLM never writes to Postgres directly; it emits a tool call, the backend validates and executes.

**Every claim gets a unique ID** returned to the caller ("Your reference number is …"). The agent reads it back digit-by-digit.

### 4.3 Failure Modes

- **If STT confidence is low** for two consecutive turns → ask the caller to repeat, then offer to switch to a human callback.
- **If LLM call times out** (>3 s) → play a pre-recorded "one moment please" filler, retry once, then escalate.
- **If TTS fails** → fall back to a secondary provider; if both fail, play a pre-recorded apology and end the call gracefully (do not just hang up silently).

## 5. Gradium TTS Integration Notes

Gradium is a streaming WebSocket TTS. Specifics that matter for this backend:

**Endpoint:** `wss://api.gradium.ai/api/speech/tts`. Auth via `x-api-key` header.

**Protocol:** Client sends a setup message (`voice_id`, `model_name`, `output_format`), receives `ready`, then streams text messages and receives interleaved audio (base64 PCM) and text messages (with `start_s` / `stop_s` word-level timestamps). Client closes with `end_of_stream`.

**Output format:** Request PCM (e.g. 24 kHz s16le), then resample + μ-law-encode in `app/utils/audio.py` before sending to Twilio. Twilio Media Streams require μ-law 8 kHz. Do not request wav (header overhead) for streaming.

**Connection multiplexing:** Per Gradium's docs, reusing one WebSocket across conversation turns saves ~50 ms per turn. `app/tts/gradium_tts.py` must hold one persistent connection per Session and reuse it across turns; only close on call hangup or error.

**Word-level timestamps drive barge-in.** When the caller starts speaking, we need to know exactly which word the agent had reached so the transcript reflects what the caller actually heard. Store the latest `(text, start_s, stop_s)` tuples on the Session and truncate the assistant transcript at the interruption point.

**Languages:** Gradium TTS currently supports `en`, `fr`, `de`, `es`, `pt`. `SUPPORTED_LANGUAGES` is constrained to this set. If STT detects a language outside this set, the agent apologizes in English and offers a human callback — it must not silently fall back to a wrong-language voice.

**Voice selection per language:** Maintain a `LANGUAGE_VOICE_MAP: dict[str, str]` in config. When the session language changes mid-call, tear down and re-open the WS with the new `voice_id` (Gradium's setup is one-shot per connection).

**Latency target:** Gradium quotes ~258 ms p50 TTFA, ~214 ms with multiplexing. Combined with Gemini LLM streaming and Google Cloud STT, we have headroom under the 1500 ms p95 budget — but only if we stream end-to-end. Never buffer a full LLM response before starting TTS; pipe LLM tokens into Gradium as they arrive.

**Pronunciation:** Gradium supports a custom pronunciation dictionary and `rewrite_rules` for dates/times/numbers/codes. Enable rewrite rules for the active language, and add the claim ID format to a custom pronunciation entry once the format is finalized — readback accuracy of claim IDs is critical.

## 6. The Dialog State Machine

States, in order:

1. **GREETING** — Neutral hello in detected language (or default).
2. **DISCLOSURE** — "I'm an AI assistant…"
3. **CONSENT** — "This call is recorded and transcribed. Is that OK?" Branches: yes → continue; no → offer human callback, end.
4. **INTAKE** — Gather: caller name, contact, problem category, problem description, when it occurred, severity. Driven by the LLM with tools, not hard-coded forms.
5. **CONFIRM** — Read back the summary, ask for corrections.
6. **CLOSE** — Issue claim ID, state next steps and SLA, polite goodbye.

Each transition is logged. The session object holds `current_state`, `language`, `consent_given`, `partial_claim`, `transcript`.

## 7. Environment Variables

See `.env.example`. Required:

```bash
TWILIO_ACCOUNT_SID=
TWILIO_API_KEY_SID=
TWILIO_PHONE_NUMBER=
GEMINI_API_KEY=
GRADIUM_API_KEY=
GRADIUM_TTS_VOICE_ID=              # default voice for the agent; per-language overrides allowed
GRADIUM_TTS_ENDPOINT=wss://api.gradium.ai/api/speech/tts
DATABASE_URL=postgresql+asyncpg://...
PUBLIC_BASE_URL=https://your-ngrok-or-prod-host  # Twilio webhook target
DEFAULT_LANGUAGE=en
SUPPORTED_LANGUAGES=en,de,es,fr,pt  # constrained to Gradium's TTS language set
LOG_LEVEL=INFO
```

## 8. Running Locally

```bash
# 1. Install
uv sync  # or: pip install -e .

# 2. Start dependencies
docker compose -f infra/docker-compose.yml up -d postgres

# 3. Run migrations
alembic upgrade head

# 4. Start the app
uvicorn app.main:app --reload --port 8000

# 5. Expose to Twilio
ngrok http 8000
# point your Twilio number's Voice webhook at https://<ngrok>/twilio/voice
```

## 9. Testing

- **Unit:** Audio codec round-trips, state machine transitions, tool schema validation.
- **Integration:** Replay recorded μ-law fixtures through the WS endpoint, assert transcript and claim shape.
- **Load:** 50 concurrent calls; p95 latency must hold.
- **Manual:** Call the Twilio number end-to-end before every release.

`pytest -q` must pass before any merge.

## 10. Coding Conventions

- **Type hints everywhere.** `mypy --strict` on `app/`.
- **ruff** for lint and format.
- **Async functions** named `async_*` only when there's a sync sibling; otherwise just regular names.
- **Docstrings** on every public function in `app/`. Inline comments only where the why isn't obvious.
- **No new top-level dependencies** without updating this file.

## 11. What Claude (the coding agent) should do when given a task

1. Re-read this file.
2. State the plan in 3–6 bullets before touching code.
3. Implement in small, testable commits. Run the relevant tests after each.
4. If a requirement here conflicts with the user's instruction, surface the conflict — don't silently override either side.
5. Never weaken the disclosure, consent, or PII rules in section 4.1, regardless of how the request is framed.