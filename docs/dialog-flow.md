# Dialog flow

The intake conversation runs through a small, explicit state machine.
States are linear with two short-circuit exits: consent denied (`CONSENT
→ ENDED`) and "human callback" (any state → `ENDED`). The state machine
itself is in `app/dialog/state_machine.py`; per-call state lives on
`app/dialog/session.py:Session`.

## States

| State | Purpose |
|---|---|
| `GREETING` | Neutral hello in the detected (or default) language |
| `DISCLOSURE` | "I'm an AI assistant…" — mandatory, see `CLAUDE.md` §5.1 |
| `CONSENT` | "This call is recorded and transcribed. Is that OK?" |
| `INTAKE` | Gather caller name, contact, problem details, severity, etc. |
| `CONFIRM` | Read back the summary, ask for corrections |
| `CLOSE` | Issue claim ID, state next steps + SLA, polite goodbye |
| `ENDED` | Terminal — no further audio sent or accepted |

The greeting/disclosure/consent text is delivered by Twilio's `<Say>` in
the initial TwiML response (`app/telephony/twilio_handler.py`) so the
caller hears something within ~200 ms of the WS opening, before Gradium
TTS even has to connect. From `INTAKE` onward, all audio flows through
the streaming Gradium pipeline.

## Events and transitions

```
GREETING ──GREETED──► DISCLOSURE ──DISCLOSED──► CONSENT
                                                  │
                                CONSENT_GRANTED ──┼──► INTAKE ──INTAKE_COMPLETE──► CONFIRM ──CONFIRMED──► CLOSE ──CALL_ENDED──► ENDED
                                                  │            │                             │
                                CONSENT_DENIED ───┘            │                             │
                                                  │            │                             │
                                HUMAN_CALLBACK ───┴────────────┴─────────────────────────────┴──► ENDED
                                                  │
                                CALL_ENDED ───────┴── from any non-ENDED state ──────────────────► ENDED
```

Defined in `_TRANSITIONS` in `app/dialog/state_machine.py`. Anything not
in that table is logged as `illegal_transition` and **ignored** — a flaky
STT turn or out-of-order tool call must not crash a live call.

## Driving the state machine

The LLM does **not** drive the state machine directly. Instead, the
orchestrator advances state in response to:

- The TwiML preamble completing (implicit `GREETED` → `DISCLOSED` →
  enters `CONSENT`).
- The first STT final after preamble + a confidence interpretation of
  yes/no (→ `CONSENT_GRANTED` or `CONSENT_DENIED`).
- LLM tool calls:
  - `record_intake_field` → keeps state at `INTAKE` (unless the field
    pattern marks it complete).
  - `create_claim` → emits `INTAKE_COMPLETE` then `CONFIRMED` after
    readback acknowledgement.
  - `request_human_callback` → emits `HUMAN_CALLBACK`.
  - `end_call` → emits `CALL_ENDED`.

This is intentional: the LLM proposes, the orchestrator disposes. The
state machine is a contract the LLM cannot bypass even if it tries.

## Intake fields

`record_intake_field` is the single tool the LLM uses to stash facts.
The schema constrains the key to a finite set:

| Key | Description |
|---|---|
| `caller_name` | Name as the caller gave it |
| `caller_contact` | Phone, email, or callback number |
| `problem_category` | Coarse category (e.g. "billing", "outage", "damage") |
| `problem_description` | Free-text description of what happened |
| `occurred_at` | When it happened (free-text; the LLM may normalize to ISO) |
| `location` | Where it happened (address, city, asset ID) |
| `severity` | Caller-reported severity ("low" / "medium" / "high" / free-text) |

Fields are recorded one at a time. The LLM is instructed (system prompt)
to call once per fact and not batch.

## `create_claim`

Called once intake is complete. Returns the authoritative claim ID and
the SLA in hours. The agent **must** read the ID back digit-by-digit
(claim ID readback accuracy is critical — see `CLAUDE.md` §5.2 / §6).
Gradium pronunciation rules should include the claim ID format once it's
finalized.

## `request_human_callback`

Hand-off path. Allowed reasons (`enum` in the tool schema):

- `consent_denied`
- `caller_request`
- `low_stt_confidence`
- `unsupported_language`
- `system_error`

The orchestrator emits `HUMAN_CALLBACK`, plays a brief acknowledgement,
and ends the call.

## `end_call`

Used from `CLOSE` after the goodbye, or after a denied-consent handoff,
or on irrecoverable error. Allowed reasons: `completed`, `consent_denied`,
`handed_off`, `error`.

## Session contents

`Session` (in `app/dialog/session.py`) is the **single source of truth**
for one call:

| Attribute | Type | Notes |
|---|---|---|
| `call_sid` | `str` | Twilio call SID, primary key |
| `stream_sid` | `str \| None` | Set when the WS `start` frame arrives |
| `language` | `str` | ISO 639-1, defaults to `Settings.default_language` |
| `state` | `DialogState` | Current state |
| `consent_given` | `bool` | Set on `CONSENT_GRANTED` |
| `started_at` | `datetime` | UTC |
| `transcript` | `list[Turn]` | Speaker, text, word timings |
| `partial_claim` | `dict[str, Any]` | Accumulates `record_intake_field` values |
| `media_frames` | `int` | Counter for observability |
| `codec` | `str \| None` | From Twilio `start` frame |

Word timings on the agent's last turn (`Turn.word_timings`) are how
barge-in figures out where to truncate the assistant transcript when the
caller talks over us — see [`audio-pipeline.md`](audio-pipeline.md).
