# Telephony (Twilio)

The telephony layer is intentionally thin. It owns:

- The HTTP webhook Twilio hits when a call arrives (returns TwiML).
- The Media Streams WebSocket where bidirectional audio flows.

It owns no dialog policy and no audio processing — both are delegated to
`app/dialog/orchestrator.py`. The clean split keeps Twilio quirks (frame
shapes, subprotocol gotchas, reconnection behaviour) isolated from the
rest of the system.

## 1. Voice webhook (`POST /twilio/voice`)

Code: [`app/telephony/twilio_handler.py`](../app/telephony/twilio_handler.py).

Twilio dials this URL when the configured phone number receives a call.
We respond with a TwiML document that does two things:

1. **Speak the preamble with `<Say>`** — greeting + AI disclosure +
   recording consent, in `Settings.default_language`. Polly locales
   (`en-US`, `de-DE`, `es-ES`, `fr-FR`, `pt-PT`) are picked per language.
   Using `<Say>` here means the caller hears something within ~200 ms of
   the call connecting, before our Gradium WebSocket even has to open.
2. **Open a Media Stream** with `<Connect><Stream/>` pointing at
   `wss://<host>/twilio/stream`. Once Twilio negotiates the WS, all
   subsequent audio (in both directions) flows over it.

We deliberately do **not** use `<Gather>` to read the caller's first
utterance — STT runs over the Media Stream as soon as it's connected.

### TwiML stream URL

The handler converts the public base URL by swapping the scheme:

```
https://abcd.ngrok.io  →  wss://abcd.ngrok.io/twilio/stream
http://localhost:8000  →  ws://localhost:8000/twilio/stream
```

`PUBLIC_BASE_URL` is read from `Settings`. In dev, point it at your
ngrok HTTPS URL; in prod, at the ALB hostname (or your custom domain).

## 2. Media Streams WebSocket (`WS /twilio/stream`)

Code: [`app/telephony/media_stream.py`](../app/telephony/media_stream.py).

Twilio Media Streams emits four JSON frame types over the WebSocket.
We handle each in `handle_media_stream()`:

| Event | Action |
|---|---|
| `connected` | Log; no action. |
| `start` | Read `callSid`, `streamSid`, codec metadata. Construct a `Session`, build a `CallOrchestrator`, call `orchestrator.start()`. |
| `media` | Base64-decode the payload, hand the μ-law bytes to `orchestrator.feed_caller_audio()`. |
| `stop` | Log totals, break the loop. |

On any exit (normal `stop`, `WebSocketDisconnect`, or exception) we
**always** call `orchestrator.stop()` and `store.pop(call_sid)` in a
`finally` block so provider connections and session state never leak.

### Subprotocol gotcha

Twilio Media Streams does **not** negotiate a WebSocket subprotocol. We
call `await websocket.accept()` with no `subprotocol` argument. (An
earlier version passed `subprotocol="audio.twilio.com"` and Twilio
immediately closed the WS because it never requested that protocol.)

### Outbound media frame shape

The orchestrator wraps each μ-law chunk in:

```json
{
  "event": "media",
  "streamSid": "MZ...",
  "media": { "payload": "<base64 μ-law>" }
}
```

Twilio expects μ-law 8 kHz mono. We send chunks of ~20 ms (160 bytes)
to balance jitter (large chunks) against WS-frame overhead (small
chunks). Trailing partial chunks at end-of-utterance are sent as-is —
Twilio tolerates short final frames.

## 3. Provider injection

`handle_media_stream` accepts an `OrchestratorFactory` so tests can swap
in mocks for STT / LLM / TTS without touching the WS layer. The default
factory wires the real clients:

```python
def default_orchestrator_factory(session, websocket, settings):
    stt = GeminiSTTClient(api_key=settings.gemini_api_key,
                          model=settings.gemini_live_model or DEFAULT_GEMINI_LIVE_MODEL)
    llm = EchoLLMClient()        # TODO(task-4): swap to GeminiLLMClient
    tts = GradiumTTSClient(api_key=settings.gradium_api_key,
                           endpoint=settings.gradium_endpoint)
    return CallOrchestrator(session=session, settings=settings,
                            websocket=websocket, stt=stt, llm=llm, tts=tts)
```

The LLM is currently the canned `EchoLLMClient` so the call loop closes
end-to-end before the real Gemini LLM client is wired up
(see [`llm-and-tools.md`](llm-and-tools.md)).

## 4. Updating the Twilio webhook

When your tunnel URL changes (every ngrok restart on the free tier),
update Twilio:

```bash
./scripts/update-ngrok.sh                       # auto-detect from local ngrok
./scripts/update-ngrok.sh https://abcd.ngrok.io # explicit base URL
```

The script auto-detects ngrok via its local API on `http://localhost:4040`
(also probes the WSL2 default-gateway host so it works when ngrok runs
on the Windows side). It reads Twilio creds from `.env`.

After running, also update `PUBLIC_BASE_URL` in `.env` if your app reads
it from disk (the script reminds you).

## 5. Codec assumptions

| Direction | Codec | Sample rate |
|---|---|---|
| Twilio → us | μ-law | 8 kHz mono |
| Us → Twilio | μ-law | 8 kHz mono |

All codec / resampling work is in `app/utils/audio.py`. The telephony
layer never touches PCM — see [`audio-pipeline.md`](audio-pipeline.md).
