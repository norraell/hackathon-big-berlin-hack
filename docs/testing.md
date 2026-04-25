# Testing

`pytest -q` must pass before any merge. The suite is fast (no live
network calls, all providers mocked) and runs in < 5 s on a laptop.

## Layout

```
tests/
├── conftest.py              # shared fixtures (currently empty)
├── test_audio.py            # μ-law / PCM round-trips, resampling, VAD
├── test_dialog_flow.py      # state-machine transitions
├── test_orchestrator.py     # full pipeline with mock STT / LLM / TTS
└── fixtures/
    └── sample_calls/        # recorded μ-law fixtures (replay tests)
```

## Running

```bash
pytest -q                    # full suite
pytest -q tests/test_audio.py
pytest -q -k barge_in        # match by node ID
pytest -q -x                 # stop on first failure
pytest -q --log-cli-level=INFO   # surface our structured logs
```

`pyproject.toml` configures `asyncio_mode = "auto"`, so `async def`
tests are picked up without a per-test decorator.

## Test categories

### Unit

- **Audio** (`test_audio.py`): μ-law round-trips, resampling shape and
  energy, VAD positive/negative. Tolerances reflect that μ-law is lossy
  and `audioop.ratecv` introduces small artifacts.
- **Dialog state machine** (`test_dialog_flow.py`): happy path through
  every legal transition; consent denial short-circuits to `ENDED`;
  human callback short-circuits from `INTAKE`; illegal transitions are
  no-ops + logged warnings (not exceptions).
- **Tool schemas** (planned): `app/llm/tools.py:ALL_TOOLS` validates
  against JSON-Schema, names are unique, enums match the documented
  vocabulary.

### Integration

- **Orchestrator** (`test_orchestrator.py`): full per-call pipeline with
  mock STT / LLM / TTS objects implementing the Protocols in
  `app/dialog/orchestrator.py`. Asserts:
  - μ-law in → STT call with PCM 16 kHz.
  - STT final → LLM dispatch → TTS `send_text`.
  - TTS audio → outbound Twilio media frames (correct base64, correct
    `streamSid`, correct chunk size).
  - Caller voiced audio while TTS active → `tts.interrupt()` + outbound
    queue drained + transcript truncated.

### Replay

The `tests/fixtures/sample_calls/` directory holds recorded μ-law
fixtures that can be fed through the WS endpoint as if they were live
calls. Use this when reproducing a tricky barge-in or codec edge case.

### Load (manual / CI)

Not part of `pytest -q`. Run separately:

- 50 concurrent calls to a staging deployment.
- Assert p95 end-of-user-speech → start-of-agent-audio ≤ 1500 ms.

## Mocking providers

The orchestrator depends on three small Protocols (`_STTLike`,
`_LLMLike`, `_TTSLike`). A `MagicMock` with the right async methods is
sufficient — no need to subclass.

For STT and TTS, the easiest pattern is to back the iterators with
`asyncio.Queue` so tests can `put()` results in a deterministic order:

```python
class FakeSTT:
    def __init__(self):
        self._q: asyncio.Queue[STTResult | None] = asyncio.Queue()
    async def start(self, language=None): pass
    async def feed_audio(self, pcm): pass
    def results(self):  # AsyncIterator
        return _drain(self._q)
    async def close(self): await self._q.put(None)
```

`tests/test_orchestrator.py` has the canonical examples — copy from
there.

## Adding a test

1. Decide which category it belongs to (unit / integration / replay).
2. Put fast tests in the right `test_*.py`. New module is fine if the
   surface is large.
3. Async tests just `async def` — no `@pytest.mark.asyncio` needed.
4. Use structured assertions on **observable behaviour** (tool call
   shape, transcript content, frame count), not implementation details.
5. If you add a fixture used by more than one file, lift it into
   `conftest.py`.

## What we deliberately do not test

- The `google-genai` SDK or the Gradium SDK themselves — they have
  their own tests. We test our adapters and the protocol shape we
  expect from them (and pin SDK versions in `pyproject.toml` once
  verified).
- TTS audio quality. That is reviewed manually in Gradium Studio.
- TTS / STT model latency. Out of our control beyond "stream end-to-end".
