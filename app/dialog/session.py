"""Per-call session state.

The :class:`Session` is the single source of truth for one phone call's
state — language, dialog state, transcript, partial claim — per CLAUDE.md
§5.2. ``SessionStore`` is a tiny in-memory map for the bootstrap; a Redis-
backed implementation lands in a later task.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any, Literal

from app.dialog.state_machine import DialogState

Speaker = Literal["caller", "agent", "system"]


@dataclass
class Turn:
    """A single utterance in the call transcript."""

    speaker: Speaker
    text: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Word-level timing surfaced by Gradium for the agent side; used to
    # truncate the transcript at the actual barge-in point (CLAUDE.md §6).
    word_timings: list[tuple[str, float, float]] = field(default_factory=list)


@dataclass
class Session:
    """Per-call state. Owned by the WS handler for the lifetime of the call."""

    call_sid: str
    stream_sid: str | None = None
    language: str = "en"
    state: DialogState = DialogState.GREETING
    consent_given: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    transcript: list[Turn] = field(default_factory=list)
    partial_claim: dict[str, Any] = field(default_factory=dict)
    # Frame counters and codec info — useful for observability without
    # pulling raw audio into logs.
    media_frames: int = 0
    codec: str | None = None

    def add_turn(self, speaker: Speaker, text: str, **kwargs: Any) -> Turn:
        """Append a turn to the transcript and return it."""
        turn = Turn(speaker=speaker, text=text, **kwargs)
        self.transcript.append(turn)
        return turn


class SessionStore:
    """Thread-safe in-memory session map.

    Replaced by a Redis-backed store in a later task; the interface
    (``get`` / ``put`` / ``pop``) is intentionally minimal so the swap is
    a one-file change.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def put(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.call_sid] = session

    def get(self, call_sid: str) -> Session | None:
        with self._lock:
            return self._sessions.get(call_sid)

    def pop(self, call_sid: str) -> Session | None:
        with self._lock:
            return self._sessions.pop(call_sid, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


_default_store = SessionStore()


def default_store() -> SessionStore:
    """Return the process-wide in-memory session store."""
    return _default_store
