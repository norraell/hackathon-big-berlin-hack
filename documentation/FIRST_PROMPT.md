# First prompt — bootstrap the voice agent backend

Paste this into Claude Code (or your Claude API agent) as the first message after `CLAUDE.md` is in the repo root.

---

Read `CLAUDE.md` end to end before doing anything else. Then bootstrap the backend skeleton for the voice AI agent it describes. Scope of this first task is **scaffolding plus a working "hello" call path** — not the full intake flow yet.

## Concrete deliverables for this task

1. **Project skeleton** matching the layout in `CLAUDE.md` section 4. Empty modules are fine where noted, but each must have a docstring describing what goes in it.

2. **`pyproject.toml`** with: `fastapi`, `uvicorn[standard]`, `twilio`, `google-generativeai`, `gradium`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `numpy`, `python-multipart`, `websockets`, `httpx`. Dev deps: `pytest`, `pytest-asyncio`, `ruff`, `mypy`. The `websockets` dep is for the Twilio Media Streams server side, not Gradium — Gradium goes through its official SDK.

3. **`app/config.py`** — `Settings` class via `pydantic-settings`, loading every variable listed in `CLAUDE.md` section 8. Validate that required keys are present at startup. Validate that `GRADIUM_VOICE_ID` is set (or that a per-language voice map is configured), and that `SUPPORTED_LANGUAGES` is a subset of Gradium's supported set (en, fr, de, es, pt).

4. **`app/main.py`** — FastAPI app with:
   - `GET /health` returning `{"status": "ok"}`.
   - `POST /twilio/voice` — Twilio voice webhook. Returns TwiML that:
     - Plays the greeting + AI disclosure + recording-consent prompt in the default language.
     - Connects the call to a `<Stream>` pointing at the WS endpoint.
   - `WS /twilio/stream` — accepts Twilio Media Streams frames. For this first task, just decode μ-law, log frame counts, and echo silence back. Real STT/LLM/TTS wiring comes in the next task.

5. **`app/telephony/twilio_handler.py`** — TwiML builder. The greeting/disclosure/consent text must come from `app/llm/prompts.py` so it's localizable. Hard-coded English fallback is acceptable for now.

6. **`app/telephony/media_stream.py`** — async WS handler. Parse Twilio's JSON frames (`connected`, `start`, `media`, `stop`). Decode the base64 μ-law payload. Hold a per-call `Session` object (defined in `app/dialog/session.py`). Log structured events (call SID, stream SID, frame count, codec). No audio processing yet — the goal is a clean, observable pipe.

7. **`app/dialog/session.py`** — minimal `Session` dataclass: `call_sid`, `stream_sid`, `language`, `state` (enum from the state machine), `started_at`, `transcript: list[Turn]`, `partial_claim: dict`. Include an in-memory `SessionStore` for session management.

8. **`app/dialog/state_machine.py`** — `DialogState` enum (`GREETING`, `DISCLOSURE`, `CONSENT`, `INTAKE`, `CONFIRM`, `CLOSE`, `ENDED`) and a `transition(session, event)` function with the legal transitions encoded. No-op on illegal transitions but log a warning.

9. **`app/llm/prompts.py`** — start with the system prompt below (do not modify the disclosure/consent wording, only translate it):

   > You are a voice intake agent for {company_name}. You handle inbound phone calls from people reporting problems. Your job is to gather the facts needed to open a claim, nothing more.
   >
   > Hard rules:
   > - You are an AI. The caller has already been told this. Never claim to be human, even if asked directly. If asked, confirm you are AI and offer a human callback.
   > - The call is recorded and transcribed; consent has already been obtained at the start. If the caller withdraws consent at any point, stop intake immediately and transfer to the human callback flow.
   > - Do not give medical, legal, or financial advice. Do not promise specific compensation, timelines, or outcomes. You may state the standard SLA: a human will follow up within {sla_hours} business hours.
   > - Speak naturally for voice: short sentences, contractions, one question at a time. Avoid bullet points and markdown — your output is spoken aloud.
   > - Mirror the caller's language. If they switch, switch with them.
   >
   > Workflow: greet → confirm what kind of problem → gather (when, where, what happened, severity, contact) → read back summary → issue claim ID → close.
   >
   > Use the provided tools to record information. Never invent claim IDs — always call `create_claim` and read back the ID it returns.

   Provide German, Spanish, French, and Portuguese translations of the *greeting/disclosure/consent* preamble (not the full system prompt). These are the languages Gradium TTS supports alongside English; do not add languages outside this set.

10. **`app/llm/tools.py`** — JSON schemas for the tools the LLM will call: `set_caller_language`, `record_intake_field` (key/value), `create_claim` (returns `{claim_id, sla_hours}`), `request_human_callback` (returns `{callback_window}`), `end_call` (with reason). Stubs only; implementations land next task.

11. **`app/tts/gradium_tts.py`** — module stub for the Gradium TTS client, built on the official `gradium` SDK (`from gradium.client import GradiumClient`). For this task: define a `GradiumTTSClient` class with a documented async interface (`connect(voice_id, language) -> None`, `send_text(text: str) -> None`, `iter_audio() -> AsyncIterator[bytes]`, `interrupt() -> None`, `close() -> None`). Body can be a `NotImplementedError` placeholder marked `# TODO(task-3): wire up gradium SDK streaming`. Include a docstring at the top of the file with a one-paragraph summary of the integration constraints from `CLAUDE.md` section 6 (multiplexing, PCM output → resample to μ-law 8 kHz, voice-per-language, word-level timestamps).

12. **`app/utils/audio.py`** — μ-law ↔ 16-bit PCM conversion (use `audioop` from stdlib; if it's been removed in your Python, use `numpy`-based fallback and note it). Resampling 8 kHz ↔ 16 kHz **and 24 kHz → 8 kHz** (Gradium emits 24 kHz PCM by default; we down-sample before μ-law-encoding for Twilio). A simple energy-based VAD function returning `bool`. Unit-test all three conversions.

13. **`tests/test_dialog_flow.py`** — happy-path state transitions and one illegal-transition assertion.

14. **`tests/test_audio.py`** — round-trip μ-law → PCM → μ-law within tolerance, 24 kHz → 8 kHz resample sanity check.

15. **`.env.example`** — every variable from `CLAUDE.md` section 8, with placeholders and short comments.

16. **`README.md`** — quick-start: clone, copy `.env`, `docker compose up`, `uvicorn`, point Twilio webhook. 30 lines max.

## Constraints

- Do **not** wire up real STT, LLM, or TTS calls in this task. Stubs that return canned data are fine; mark them with `# TODO(task-2): real provider call`.
- Do **not** modify the disclosure or consent rules from `CLAUDE.md`. If you think a rule is wrong, raise it in the response — don't change it unilaterally.
- Keep the diff focused. No premature optimization, no extra abstractions "for later".

## What I want back

1. A short plan (5–8 bullets) before you start.
2. The implementation.
3. Output of `pytest -q` showing tests pass.
4. A list of every assumption you made that wasn't explicit in the brief or `CLAUDE.md`, so I can confirm or correct.

When the scaffold is solid and tests pass, stop and wait for the next task. The next two tasks, in order, will be: (task 2) wiring Gemini STT into the WS handler, and (task 3) wiring Gradium TTS as the speech output.