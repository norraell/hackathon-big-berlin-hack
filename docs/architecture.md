# Architecture

This document describes the system at the level a new contributor needs to
read existing code or to add a new component. Operational rules and the
non-negotiable legal/ethical constraints live in [`../CLAUDE.md`](../CLAUDE.md).

## 1. System overview

```
PSTN caller
    │
    ▼
Twilio Voice (phone number) ── Media Streams (bidirectional WebSocket, μ-law 8 kHz)
    │
    ▼
FastAPI WebSocket server (this repo)
    │
    ├─► Gemini STT (streaming, multilingual)            # speech → text
    ├─► Gemini LLM (gemini-2.5-flash, function calling) # dialog policy + tool calls
    └─► Gradium TTS (streaming PCM, word timings)       # text → speech
    │
    └─► Postgres + Redis                                # claims, sessions, call state
```

Two surfaces are exposed to the outside world:

- `POST /twilio/voice` — Twilio webhook. Returns TwiML that speaks the
  greeting/disclosure/consent preamble (via Twilio `<Say>`) and immediately
  opens a Media Streams connection back to us.
- `WS /twilio/stream` — Twilio Media Streams WebSocket. Carries μ-law
  8 kHz audio in both directions for the rest of the call.

A third trivial surface, `GET /health`, is for liveness checks (used by
ECS / load balancer health probes).

## 2. Per-call lifecycle

1. **Twilio dials our webhook.** `app/telephony/twilio_handler.py` builds
   TwiML: a `<Say>` preamble (greeting + AI disclosure + consent ask) in
   the configured default language, then a `<Connect><Stream/>` pointing at
   `wss://<host>/twilio/stream`.
2. **WebSocket opens.** `app/telephony/media_stream.py` accepts the WS
   (no subprotocol — Twilio does not negotiate one). It receives Twilio's
   four frame types: `connected`, `start`, `media`, `stop`.
3. **`start` frame** carries `callSid`, `streamSid`, codec metadata.
   We construct a `Session` (the per-call source of truth) and a
   `CallOrchestrator`, then call `orchestrator.start()` which opens the
   Gemini STT Live session and the Gradium TTS WebSocket.
4. **`media` frames** carry base64-encoded μ-law audio. The orchestrator
   decodes each frame, runs cheap energy-based VAD for barge-in detection,
   upsamples 8 kHz → 16 kHz PCM, and pushes the PCM into the STT session.
5. **STT emits results.** Interim transcripts feed barge-in / latency
   logic; on each *final* transcript, the orchestrator dispatches a turn
   to the LLM.
6. **LLM streams text + tool calls.** Each text delta is piped straight
   into Gradium TTS — we never wait for the full completion.
7. **TTS streams audio.** Raw 24 kHz PCM out → downsample 24 kHz → 8 kHz →
   μ-law-encode → base64 → Twilio `media` frame back to the caller.
8. **Word-level timestamps** from TTS are recorded on the in-flight agent
   turn so that a barge-in can truncate the assistant transcript at the
   actual interruption point ("what the caller heard").
9. **Barge-in**: if the caller speaks while TTS is producing, the
   orchestrator calls `tts.interrupt()`, drains the outbound queue, and
   truncates the assistant turn at the last completed word.
10. **`stop` frame** (call hangup) tears down everything: cancels the pump
    tasks, closes provider connections, and pops the session from the
    in-memory store.

The detailed dialog state transitions (greeting → disclosure → consent →
intake → confirm → close) are documented in
[`dialog-flow.md`](dialog-flow.md).

## 3. Component map

| Layer | Module | Responsibility |
|---|---|---|
| HTTP / WS | `app/main.py` | FastAPI app, route wiring (thin) |
| Telephony | `app/telephony/twilio_handler.py` | Build TwiML for the inbound webhook |
| Telephony | `app/telephony/media_stream.py` | Parse Twilio WS frames, delegate to orchestrator |
| STT | `app/stt/gemini_stt.py` | Streaming Gemini Live wrapper (PCM in, transcripts out) |
| LLM | `app/llm/client.py` | Streaming LLM client + tool-call deltas (`EchoLLMClient` stub for bootstrap) |
| LLM | `app/llm/prompts.py` | System prompt + localized greeting/disclosure/consent text |
| LLM | `app/llm/tools.py` | JSON-Schema tool/function definitions |
| TTS | `app/tts/gradium_tts.py` | Streaming Gradium TTS, persistent WS, word timings |
| Dialog | `app/dialog/state_machine.py` | Legal state transitions (illegal = no-op + warn) |
| Dialog | `app/dialog/session.py` | Per-call state, transcript, partial claim, in-memory store |
| Dialog | `app/dialog/orchestrator.py` | Per-call audio pipeline + barge-in |
| Claims | `app/claims/models.py` | Claim ORM models (stub) |
| Claims | `app/claims/service.py` | `create_claim`, `attach_transcript` (stub) |
| Utils | `app/utils/audio.py` | μ-law ↔ PCM, resampling, energy VAD |
| Utils | `app/utils/language.py` | ISO 639-1 normalization |

## 4. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Runtime | Python 3.11+ | Best ecosystem for STT/TTS SDKs; type hints are first-class |
| Web | FastAPI + Uvicorn | Native async, WebSocket support, fast startup |
| Telephony | Twilio Programmable Voice + Media Streams | Inbound PSTN, bidirectional audio, mature SDKs |
| STT | Google Gemini Live (`gemini-2.5-flash-native-audio-latest`) | Multilingual, streaming, sub-second latency |
| LLM | Google Gemini (`gemini-2.5-flash`) via `google-genai` | Same vendor as STT (one API key, one quota); JSON-Schema function calling |
| TTS | Gradium via official `gradium` SDK | Sub-300 ms TTFA, word-level timestamps for barge-in, connection multiplexing |
| Storage | Postgres (claims, transcripts), Redis (live sessions) | Postgres for durable structured data; Redis for low-latency session state |
| Audio | `audioop` (≤3.12) / NumPy fallback (3.13+) | μ-law ↔ PCM and resampling; one-place codec policy |

## 5. Data flow under one turn

```
caller speaks
   │  μ-law 8 kHz frames over Twilio WS
   ▼
media_stream.py  (decode base64, parse frame)
   │
   ▼
orchestrator.feed_caller_audio()
   │  μ-law → PCM 8 kHz → upsample → PCM 16 kHz
   ▼
gemini_stt.feed_audio()
   │  (also: VAD on PCM 8 kHz → if TTS active → barge-in)
   ▼
gemini_stt.results()  ── async iterator of STTResult(is_final, text, language)
   │
   ▼  on is_final:
orchestrator._handle_user_turn()
   │  build messages from session.transcript
   ▼
llm.stream_completion()  ── async iterator of LLMDelta(text|tool_call|finish)
   │
   ▼  per delta.text:
gradium_tts.send_text()
   │
   ▼
gradium_tts.iter_audio()  ── async iterator of raw PCM 24 kHz chunks
   │  PCM 24 kHz → downsample → PCM 8 kHz → μ-law-encode
   │  chunk to ~20 ms (160 bytes), base64
   ▼
websocket.send_text({event:"media", streamSid, media:{payload}})
   │
   ▼
caller hears the agent
```

Three pumps run concurrently on the orchestrator:

- `_pump_stt_results` — drains STT, dispatches LLM turns on finals.
- `_pump_tts_audio` — drains TTS audio, encodes, sends Twilio media frames.
- `_pump_word_timings` — appends `(text, start_s, stop_s)` triples to the
  current agent turn for barge-in truncation.

## 6. Latency budget

End-of-user-speech → start-of-agent-audio must be **≤ 1500 ms p95**.
Anything slower feels broken on a phone line. The budget breaks down
roughly as:

| Stage | Typical |
|---|---|
| STT final-marker latency (Gemini Live) | 150–300 ms |
| LLM first-token (Gemini 2.5 Flash) | 250–400 ms |
| TTS time-to-first-audio (Gradium, multiplexed connection) | ~214 ms |
| Resample + μ-law + WS round trip | < 50 ms |

That is only achievable if every stage **streams**. Three rules apply
everywhere:

1. Never wait for a full LLM completion before starting TTS — pipe each
   text delta straight in.
2. Reuse the Gradium WebSocket across turns (saves ~50 ms TTFA per turn).
3. Never block the event loop. All audio I/O is async; provider stages
   communicate via `asyncio.Queue`.

## 7. Failure modes

Encoded into the orchestrator and provider layers:

- **STT confidence low for two consecutive turns** → ask the caller to
  repeat, then offer a human callback (`request_human_callback` tool).
- **LLM call times out (>3 s)** → play a pre-recorded "one moment please"
  filler, retry once, then escalate.
- **TTS fails** → fall back to a secondary provider; if both fail, play a
  pre-recorded apology and end the call gracefully (do not just hang up).
- **Caller language is outside the Gradium set** → apologize in English
  (`UNSUPPORTED_LANGUAGE_FALLBACK_EN`) and offer a callback. Never silently
  fall back to a wrong-language voice.

## 8. Where to extend

| You want to… | Touch |
|---|---|
| Swap the LLM provider | `app/llm/client.py` (and `architecture.md`/this file) |
| Add a new tool | `app/llm/tools.py` + dispatcher in `orchestrator._handle_user_turn` |
| Add a language | `app/config.py` (`SUPPORTED_LANGUAGES`), `app/llm/prompts.py` (preamble), Gradium voice ID in `LANGUAGE_VOICE_MAP` |
| Add a state | `app/dialog/state_machine.py` — add to `DialogState` and `_TRANSITIONS` |
| Replace the in-memory session store | `app/dialog/session.py` — keep the `get/put/pop` interface, swap to Redis |
| Persist a claim | `app/claims/service.py` (currently stubbed) |
