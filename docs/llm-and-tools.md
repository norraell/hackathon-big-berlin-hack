# LLM and tools

The dialog LLM is Google Gemini (`gemini-2.5-flash`) accessed through the
`google-genai` SDK. Same vendor as STT — one API key, one quota path.
This document covers the LLM client interface, the system prompt, and
the tool/function-calling contract.

## Client interface

`app/llm/client.py` defines a small `LLMClient` Protocol:

```python
class LLMClient(Protocol):
    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]: ...
```

`LLMDelta` is the streaming chunk type:

```python
@dataclass
class LLMDelta:
    text: str | None = None
    tool_call: dict[str, Any] | None = None
    finish: bool = False
```

Each delta carries either incremental `text` (pipe straight to TTS) or a
complete `tool_call` (dispatch via `app/llm/tools.py`). The final delta
sets `finish=True` so the orchestrator can flush.

## Two implementations

- **`GeminiLLMClient`** — the real provider call. Currently a stub
  (`raise NotImplementedError`). Full streaming + function-calling lands
  in task 4. The plan:
  - One process-wide async `genai.Client(api_key=...)`.
  - `client.aio.models.generate_content_stream(...)` with the function
    declarations from `app/llm/tools.py:ALL_TOOLS`.
  - Map SDK chunks into `LLMDelta` (one `text=` per text chunk, one
    `tool_call=` per function call, one `finish=True` at the end).
- **`EchoLLMClient`** — canned client used during the bootstrap so the
  call loop closes end-to-end before the real LLM is wired up. Yields a
  localized acknowledgement plus the caller's last utterance, in two
  text deltas. Replace orchestrator wiring with `GeminiLLMClient` when
  task 4 lands.

The orchestrator depends on the Protocol, not the concrete class, so
the swap is a one-line change in
`app/telephony/media_stream.py:default_orchestrator_factory`.

## System prompt

`app/llm/prompts.py:SYSTEM_PROMPT` is the operating contract. It must
not be edited to weaken disclosure, consent, or scope rules — see
`CLAUDE.md` §5.1 / §11.

Substitution variables: `{company_name}`, `{sla_hours}`. Render with
`render_system_prompt(...)`.

Hard rules baked in:

- The agent is an AI; never claim to be human; if asked, confirm and
  offer a human callback.
- Recording consent has been obtained; if the caller withdraws consent,
  stop intake and transfer.
- No medical, legal, or financial advice; no promises of compensation,
  timelines, or outcomes (only the standard SLA).
- Speak naturally for voice: short sentences, contractions, one
  question at a time. No bullet points, no markdown.
- Mirror the caller's language; switch when they switch.

Workflow (also baked in): greet → confirm problem type → gather (when,
where, what happened, severity, contact) → read back summary → issue
claim ID → close.

## Localized preambles

`GREETING_DISCLOSURE_CONSENT` in the same file maps language code to
the spoken preamble (greeting + AI disclosure + recording-consent ask).
Languages: `en`, `de`, `es`, `fr`, `pt`. The English version is
canonical; translations preserve meaning, not literal phrasing.

`render_preamble(language=..., company_name=..., default_language=...)`
returns the rendered preamble; falls back to the default-language
template if no translation exists.

`UNSUPPORTED_LANGUAGE_FALLBACK_EN` is what we say (always in English)
when STT detects a language outside the Gradium TTS set. Followed by a
human-callback offer. Never silently fall back to a wrong-language voice
(`CLAUDE.md` §6).

## Tool schemas

`app/llm/tools.py:ALL_TOOLS` contains the JSON-Schema function
declarations. The schemas are the **authoritative contract** — the
dispatcher (in a later task) validates incoming tool calls against them
before executing.

| Tool | Purpose |
|---|---|
| `set_caller_language` | Switch active language. Constrained to the supported set (`en`, `de`, `es`, `fr`, `pt`). Triggers a Gradium voice swap (re-`connect` with the new `voice_id`). |
| `record_intake_field` | Record one fact about the report. `key` is constrained to a finite enum (`caller_name`, `caller_contact`, `problem_category`, `problem_description`, `occurred_at`, `location`, `severity`); `value` is a string. Call once per fact, do not batch. |
| `create_claim` | Persist accumulated `record_intake_field` values as a claim. Returns the authoritative `claim_id` and SLA in hours. **Never** invent a claim ID — always call this tool. |
| `request_human_callback` | Hand off to a human. Allowed `reason`: `consent_denied`, `caller_request`, `low_stt_confidence`, `unsupported_language`, `system_error`. |
| `end_call` | End gracefully. Allowed `reason`: `completed`, `consent_denied`, `handed_off`, `error`. |

`tool_names()` returns the registered names; `ALL_TOOLS` returns the
list of schema dicts ready to pass to the SDK.

## Why tool calls?

Tool calls are the **only** way the LLM mutates state (`CLAUDE.md` §5.2).
The LLM never writes to Postgres directly; it emits a structured tool
call, the backend validates it against the schema, and only then
executes. This:

- Keeps prompt-injection out of the data path (the LLM cannot construct
  a SQL string or skip validation).
- Makes the conversation recordable and replayable — every state change
  is a typed event in the transcript.
- Makes the agent testable: assert tool-call sequences, not text shape.

## Adding a tool

1. Add the schema dict to `app/llm/tools.py` and append it to
   `ALL_TOOLS`.
2. Add a dispatcher branch in
   `app/dialog/orchestrator.py:_handle_user_turn` (currently a `TODO`).
3. Update the system prompt if the LLM needs guidance on when to call it.
4. Add a unit test that constructs a fake `LLMDelta(tool_call=...)` and
   asserts the dispatcher does the right thing.
