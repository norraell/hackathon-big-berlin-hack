"""Gemini LLM client (dialog policy + tool calls).

We use Google Gemini for **both** STT (``app.stt.gemini_stt``) and the
dialog/tool-calling LLM (this module). One vendor, one auth path, one
quota.

This file currently ships two clients:

* :class:`GeminiLLMClient` — real provider call. **Stubbed** for the
  bootstrap; full streaming + function-calling implementation lands in
  task 4.
* :class:`EchoLLMClient` — trivial canned-response client used by the
  orchestrator so the call loop closes end-to-end (caller speaks → STT →
  *something* → TTS) before the real LLM is wired in. Mark every test that
  depends on its exact phrasing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class LLMDelta:
    """One streaming chunk from an LLM client.

    Either ``text`` carries an incremental token (pipe straight to TTS) or
    ``tool_call`` carries a complete function-call invocation (dispatch via
    ``app.llm.tools``). Real clients will emit a final delta with
    ``finish=True`` so the orchestrator can flush.
    """

    text: str | None = None
    tool_call: dict[str, Any] | None = None
    finish: bool = False


class LLMClient(Protocol):
    """Common interface every LLM client must implement."""

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]:
        """Stream a chat completion. Yields :class:`LLMDelta` chunks."""
        ...


class GeminiLLMClient:
    """Streaming Gemini client for dialog turns and tool calls.

    The full implementation will:

    * Use ``google-genai`` (``from google import genai``) with an async
      client created once per process.
    * Stream tokens via the SDK's streaming generate-content API so TTS
      can start before the full completion arrives (CLAUDE.md §5.2 latency
      budget).
    * Pass the JSON-Schema function declarations from
      :mod:`app.llm.tools` as the ``tools`` kwarg; surface tool calls as
      they arrive and dispatch them to the orchestrator.

    TODO(task-4): real provider call.
    """

    def __init__(self, api_key: str, *, model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key
        self.model = model

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]:
        raise NotImplementedError("Wire up Gemini LLM streaming in task 4")
        # The ``yield`` keeps this an async generator at the type level so
        # callers can ``async for`` against it once implemented.
        if False:  # pragma: no cover
            yield LLMDelta()


# ---------------------------------------------------------------------------
# Echo stub — keeps the call loop demonstrable until task 4 lands.
# ---------------------------------------------------------------------------

# Per-language acknowledgement so the echoed response is in the caller's
# language. Kept short on purpose — this is a placeholder, not a script.
_ECHO_PREFIX: dict[str, str] = {
    "en": "Got it. You said: ",
    "de": "Verstanden. Sie sagten: ",
    "es": "Entendido. Usted dijo: ",
    "fr": "Compris. Vous avez dit : ",
    "pt": "Entendido. Você disse: ",
}


class EchoLLMClient:
    """Canned LLM client for the bootstrap.

    Yields a single text delta that prefixes the caller's last utterance
    with a localized acknowledgement. This proves the STT → LLM → TTS path
    is wired without depending on the real LLM being implemented yet.

    TODO(task-4): replace orchestrator wiring with :class:`GeminiLLMClient`.
    """

    async def stream_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        language: str | None = None,
    ) -> AsyncIterator[LLMDelta]:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        prefix = _ECHO_PREFIX.get((language or "en").lower(), _ECHO_PREFIX["en"])
        # Yield in two chunks so the orchestrator/TTS path is exercised on
        # *streaming* input, not a single blob.
        yield LLMDelta(text=prefix)
        if last_user:
            yield LLMDelta(text=last_user)
        yield LLMDelta(finish=True)
