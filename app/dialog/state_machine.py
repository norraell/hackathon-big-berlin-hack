"""Dialog state machine.

Encodes the legal transitions between dialog states (CLAUDE.md §7). Illegal
transitions are no-ops and emit a warning rather than raising — a flaky STT
turn or an out-of-order tool call should not crash a live call.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid runtime import cycle
    from app.dialog.session import Session

logger = logging.getLogger(__name__)


class DialogState(str, Enum):
    """States the intake dialog can occupy.

    Order: GREETING → DISCLOSURE → CONSENT → INTAKE → CONFIRM → CLOSE → ENDED.
    From most states the call may also short-circuit to ENDED (caller
    hangs up, consent denied, escalation to human callback).
    """

    GREETING = "greeting"
    DISCLOSURE = "disclosure"
    CONSENT = "consent"
    INTAKE = "intake"
    CONFIRM = "confirm"
    CLOSE = "close"
    ENDED = "ended"


class DialogEvent(str, Enum):
    """Events that drive the state machine."""

    GREETED = "greeted"
    DISCLOSED = "disclosed"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_DENIED = "consent_denied"
    INTAKE_COMPLETE = "intake_complete"
    CONFIRMED = "confirmed"
    CALL_ENDED = "call_ended"
    HUMAN_CALLBACK = "human_callback"


# Legal (state, event) → next_state transitions. Anything not in this map is
# logged as illegal and ignored.
_TRANSITIONS: dict[tuple[DialogState, DialogEvent], DialogState] = {
    (DialogState.GREETING, DialogEvent.GREETED): DialogState.DISCLOSURE,
    (DialogState.DISCLOSURE, DialogEvent.DISCLOSED): DialogState.CONSENT,
    (DialogState.CONSENT, DialogEvent.CONSENT_GRANTED): DialogState.INTAKE,
    (DialogState.CONSENT, DialogEvent.CONSENT_DENIED): DialogState.ENDED,
    (DialogState.CONSENT, DialogEvent.HUMAN_CALLBACK): DialogState.ENDED,
    (DialogState.INTAKE, DialogEvent.INTAKE_COMPLETE): DialogState.CONFIRM,
    (DialogState.INTAKE, DialogEvent.HUMAN_CALLBACK): DialogState.ENDED,
    (DialogState.CONFIRM, DialogEvent.CONFIRMED): DialogState.CLOSE,
    (DialogState.CONFIRM, DialogEvent.HUMAN_CALLBACK): DialogState.ENDED,
    (DialogState.CLOSE, DialogEvent.CALL_ENDED): DialogState.ENDED,
    # Hard hang-up can fire from anywhere except ENDED.
    (DialogState.GREETING, DialogEvent.CALL_ENDED): DialogState.ENDED,
    (DialogState.DISCLOSURE, DialogEvent.CALL_ENDED): DialogState.ENDED,
    (DialogState.CONSENT, DialogEvent.CALL_ENDED): DialogState.ENDED,
    (DialogState.INTAKE, DialogEvent.CALL_ENDED): DialogState.ENDED,
    (DialogState.CONFIRM, DialogEvent.CALL_ENDED): DialogState.ENDED,
}


def transition(session: Session, event: DialogEvent) -> DialogState:
    """Advance ``session.state`` according to ``event``.

    Returns the resulting state. If the (state, event) pair is illegal, logs
    a warning and leaves the session unchanged.
    """
    current = session.state
    next_state = _TRANSITIONS.get((current, event))
    if next_state is None:
        logger.warning(
            "illegal_transition",
            extra={
                "call_sid": session.call_sid,
                "from_state": current.value,
                "event": event.value,
            },
        )
        return current
    if next_state != current:
        logger.info(
            "state_transition",
            extra={
                "call_sid": session.call_sid,
                "from_state": current.value,
                "to_state": next_state.value,
                "event": event.value,
            },
        )
    session.state = next_state
    return next_state
