# Troubleshooting

Failure modes you are likely to hit, and what to do about them. If you
hit one not listed here, add it.

## Startup

### `ValidationError: SUPPORTED_LANGUAGES contains languages not supported by Gradium TTS`

Gradium currently supports `en, fr, de, es, pt`. Anything else in
`SUPPORTED_LANGUAGES` is rejected at startup. Either drop the language,
or wait until Gradium adds it. Never silently fall back to a
wrong-language voice (`CLAUDE.md` §6).

### `ValueError: DEFAULT_LANGUAGE=... is not in SUPPORTED_LANGUAGES`

Self-explanatory. Add the language to `SUPPORTED_LANGUAGES` or change
`DEFAULT_LANGUAGE`.

### `ValueError: GRADIUM_VOICE_ID is unset and LANGUAGE_VOICE_MAP is missing voice IDs for languages: ['de', 'es']`

Either set `GRADIUM_VOICE_ID` (used as the default for any language not
in the map), or fill in `LANGUAGE_VOICE_MAP` for **every** language in
`SUPPORTED_LANGUAGES`.

### `RuntimeError: google-genai is not installed`

`pip install -e '.[dev]'` should pull it in via `pyproject.toml`. If
you're running in a fresh venv, re-install. Same applies to
`gradium SDK is not installed`.

## Twilio webhook

### Twilio returns "Application error" / 502 to the caller

The webhook URL is unreachable or returning non-2xx. Check:

1. Is the tunnel up? `curl https://<ngrok>/health` should return
   `{"status":"ok"}`.
2. Does the URL Twilio is calling match your current tunnel? Run
   `./scripts/update-ngrok.sh` after every ngrok restart.
3. Is the app actually running? `lsof -i :8000` or check `uvicorn` logs.

### `POST /twilio/voice` returns 200 but the call disconnects

Look at the TwiML response. The most common bug is
`PUBLIC_BASE_URL=http://...` — Twilio cannot dial a `ws://` Media
Stream over plain HTTP from a public number, only `wss://`. The handler
auto-derives `wss://` from `https://`, so make sure `PUBLIC_BASE_URL`
starts with `https://`.

## Media Streams WebSocket

### WS connects then closes immediately

You probably passed a `subprotocol=` to `websocket.accept()`. Twilio
Media Streams does **not** negotiate one. The current code does the
right thing — leave it alone.

### `twilio_ws_media_before_start` log entries

A `media` frame arrived before the `start` frame. Either Twilio sent
frames out of order (rare), or the WS handler missed the `start` event.
Drop the frame and continue — the orchestrator isn't constructed yet.

### Audible drops or jitter on the caller's side

Outbound chunk size is too large (causes jitter) or too small (causes
WS-frame overhead). The current value (`_OUTBOUND_FRAME_BYTES = 160`,
~20 ms) is the sweet spot for telephony. Tune in
`app/dialog/orchestrator.py` if you're sure.

## STT (Gemini Live)

### No transcripts appear

1. `GEMINI_API_KEY` is invalid or scoped wrong → check Google AI Studio.
2. `GEMINI_LIVE_MODEL` rotated → set `GEMINI_LIVE_MODEL=<current id>`
   without redeploying. Google rotates Live model IDs aggressively.
3. SDK version mismatch → the Live API surface has been moving; see the
   `TODO(verify-sdk)` comments in `app/stt/gemini_stt.py`.

### Transcripts appear but `is_final` is never `True`

Look for `server_content.turn_complete=True` in the SDK responses. If
the SDK version uses a different end-of-turn marker, update
`_extract_results` in `app/stt/gemini_stt.py`. Without finals, the
orchestrator never dispatches an LLM turn and the agent stays silent.

### `Cannot extract voices from a non-audio request`

You are using a native-audio Live model with `response_modalities=[TEXT]`.
The current code already requests `[AUDIO]` with a dummy voice config and
discards the audio output, which works on both half-cascade and
native-audio models. If you change the modality, you'll hit this error.

## TTS (Gradium)

### TTS connects but no audio plays

1. The voice ID for the active language doesn't exist in your Gradium
   Studio. Verify in the Studio UI and update `GRADIUM_VOICE_ID` /
   `LANGUAGE_VOICE_MAP`.
2. The SDK entrypoint name doesn't match what we probe. See
   `_open_stream` in `app/tts/gradium_tts.py` — there are
   `TODO(verify-sdk)` markers for the names we try.

### Wrong voice / wrong language

A language switch mid-call requires re-`connect`ing to Gradium with the
new `voice_id` (Gradium `setup` is one-shot per connection). Verify
`GradiumTTSClient.connect()` is being called with the new voice when the
LLM emits `set_caller_language`.

### Barge-in cuts but the next reply is missing the first few words

The reader task wasn't drained between turns. The current code calls
`_drain_queue_sync` for both `_audio_q` and `_words_q` before starting
a new reader. If you change the connection lifecycle, preserve this
ordering.

## Latency

### p95 turn latency > 1500 ms

Profile per stage (the orchestrator already logs structured events with
`call_sid` extras — easy to slice in your log aggregator):

| Stage | Reasonable | If bad |
|---|---|---|
| STT final-marker latency | 150–300 ms | Live model overloaded; switch model ID |
| LLM first-token | 250–400 ms | Different model? Long system prompt? |
| TTS TTFA | ~258 ms p50, ~214 ms multiplexed | Reconnecting per turn (fix: persistent `GradiumClient`) |
| Outbound resample + WS round trip | < 50 ms | Outbound queue backed up; check `_pump_tts_audio` |

Common root cause: someone introduced an `await llm.full_completion()`
instead of streaming deltas. Search for `async for delta in
self.llm.stream_completion(...)` and confirm the body still calls
`await self.tts.send_text(delta.text)` per delta.

## Database / Redis

### `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)`

Postgres isn't running. Start it:
`docker compose -f infra/docker-compose.yml up -d postgres redis`.

### `DATABASE_URL` mismatch between Compose and venv

In Compose, the Postgres host is `postgres`. From the venv, it's
`localhost`. Pick one and stick to it. The `app` service in Compose
already overrides via `env_file`.

## Tests

### `RuntimeWarning: coroutine '...' was never awaited` in tests

`pyproject.toml` sets `asyncio_mode = "auto"`. If your `async def` test
isn't being picked up, you probably accidentally deleted that line.

### `tests/test_orchestrator.py` flakes

The orchestrator runs three pump tasks concurrently; tests that assert
the order of operations need explicit synchronization (e.g. wait on a
queue) rather than `asyncio.sleep`. If you see flakes, you've raced the
pumps.
