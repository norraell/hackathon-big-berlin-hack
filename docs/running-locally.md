# Running locally

Step-by-step bring-up for local development on Linux / macOS / WSL2.
Gives you a working phone-line voice agent reachable from a real Twilio
number, with verification at each layer.

## Prerequisites

- Python **3.11+** (check `python3 --version`).
- Docker + `docker compose` (for Postgres / Redis).
- A Twilio account with a phone number and an API key (SK + Secret).
- A Google AI Studio API key (Gemini, used for both STT and LLM).
- A Gradium API key + at least one voice ID from Gradium Studio.
- `ngrok` (or any TCP/HTTP tunnel) for exposing localhost to Twilio.

## 1. Install

```bash
git clone <this repo> && cd hackathon-big-berlin-hack
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
# or, if you use uv:
# uv sync
```

Verify:

```bash
python -c "import app.main; print('ok')"
```

## 2. Configure

```bash
cp .env.example .env
$EDITOR .env
```

Fill in at minimum:

- `TWILIO_ACCOUNT_SID`, `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`,
  `TWILIO_PHONE_NUMBER`
- `GEMINI_API_KEY`
- `GRADIUM_API_KEY`, `GRADIUM_VOICE_ID`
- `DATABASE_URL`, `REDIS_URL` — defaults work with the docker-compose
  stack below.
- `PUBLIC_BASE_URL` — leave as a placeholder; we'll fill it in after
  ngrok is up.

See [`configuration.md`](configuration.md) for the full reference.

## 3. Start dependencies

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
docker compose -f infra/docker-compose.yml ps
```

Both services have healthchecks; wait until they show `(healthy)`.

Verify Postgres + Redis are reachable:

```bash
psql "$DATABASE_URL" -c '\l'
redis-cli -u "$REDIS_URL" ping     # → PONG
```

## 4. (Future) Migrations

Once schema migrations land:

```bash
alembic upgrade head
```

Currently `app/claims/models.py` is a stub; nothing to migrate yet.

## 5. Run the app

```bash
uvicorn app.main:app --reload --port 8000
```

Verify health:

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

Verify the Twilio webhook returns valid TwiML (you'll see a `<Say>` and
a `<Connect><Stream/>`):

```bash
curl -s -X POST http://localhost:8000/twilio/voice
```

## 6. Tunnel to Twilio

```bash
ngrok http 8000
```

Note the `https://<...>.ngrok.io` URL.

Patch your Twilio number's voice webhook (and remember to update
`PUBLIC_BASE_URL` in `.env` if you re-read it from disk):

```bash
./scripts/update-ngrok.sh                         # auto-detects ngrok
# or, explicit:
./scripts/update-ngrok.sh https://abcd.ngrok.io
```

The script reads Twilio creds from `.env` and PATCHes the
`IncomingPhoneNumbers/<sid>.json` resource to set `VoiceUrl` to
`<base>/twilio/voice`.

## 7. Smoke-test end-to-end

Dial your Twilio number from a real phone. You should hear:

1. The greeting + AI disclosure + consent prompt (Twilio `<Say>`).
2. A reply from the agent in your default language after you speak.
3. Word-aligned cut-off if you talk over the agent (barge-in).

Watch the logs (`uvicorn` stdout) for:

- `twilio_ws_connected` and `twilio_ws_start` (Media Stream opened).
- `gemini_stt_started` and `gradium_tts_connected` (providers wired).
- `stt_final` after each user turn.
- `state_transition` as the dialog advances.
- `barge_in` if you spoke over the agent.

## Troubleshooting

If something doesn't work, check [`troubleshooting.md`](troubleshooting.md).
The most common failure modes:

- **Twilio webhook 502** — your tunnel URL changed and you forgot to run
  `./scripts/update-ngrok.sh`.
- **WS closes immediately** — make sure `websocket.accept()` is called
  with no `subprotocol` (we already do; don't change it).
- **Settings validation error at startup** — `SUPPORTED_LANGUAGES` has a
  language Gradium can't synthesize, or `GRADIUM_VOICE_ID` is unset and
  `LANGUAGE_VOICE_MAP` is incomplete. The error message tells you which.
- **No transcripts** — `GEMINI_API_KEY` invalid, or the Live model ID
  rotated; set `GEMINI_LIVE_MODEL` to a current ID without redeploying.
- **TTS silent** — verify `GRADIUM_VOICE_ID` exists in your Gradium
  Studio for the active language.

## Iterating

`uvicorn --reload` reloads on Python file changes but **does not** reset
in-memory session state and **does not** drop active WebSocket
connections. After a code change, hang up and re-dial to pick up the
new code on a fresh call.
