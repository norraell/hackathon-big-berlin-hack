"""Dialog state-machine tests.

Covers the happy path through every legal transition and asserts that an
illegal transition is a no-op (and not an exception)."""

from __future__ import annotations

import logging

from app.dialog.session import Session
from app.dialog.state_machine import DialogEvent, DialogState, transition


def test_happy_path_runs_through_all_states() -> None:
    session = Session(call_sid="CA_test_happy")
    assert session.state is DialogState.GREETING

    assert transition(session, DialogEvent.GREETED) is DialogState.DISCLOSURE
    assert transition(session, DialogEvent.DISCLOSED) is DialogState.CONSENT
    assert transition(session, DialogEvent.CONSENT_GRANTED) is DialogState.INTAKE
    assert transition(session, DialogEvent.INTAKE_COMPLETE) is DialogState.CONFIRM
    assert transition(session, DialogEvent.CONFIRMED) is DialogState.CLOSE
    assert transition(session, DialogEvent.CALL_ENDED) is DialogState.ENDED


def test_consent_denied_short_circuits_to_ended() -> None:
    session = Session(call_sid="CA_test_consent_no")
    transition(session, DialogEvent.GREETED)
    transition(session, DialogEvent.DISCLOSED)
    assert transition(session, DialogEvent.CONSENT_DENIED) is DialogState.ENDED


def test_human_callback_short_circuits_from_intake() -> None:
    session = Session(call_sid="CA_test_handoff")
    for event in (
        DialogEvent.GREETED,
        DialogEvent.DISCLOSED,
        DialogEvent.CONSENT_GRANTED,
    ):
        transition(session, event)
    assert session.state is DialogState.INTAKE
    assert transition(session, DialogEvent.HUMAN_CALLBACK) is DialogState.ENDED


def test_illegal_transition_is_noop_and_logs_warning(caplog: object) -> None:
    # caplog is a pytest fixture; type as object to avoid importing pytest types.
    import pytest  # noqa: PLC0415  — local import keeps the module importable without pytest

    assert isinstance(caplog, pytest.LogCaptureFixture)
    session = Session(call_sid="CA_test_illegal")
    # Cannot grant consent before greeting/disclosure.
    with caplog.at_level(logging.WARNING, logger="app.dialog.state_machine"):
        result = transition(session, DialogEvent.CONSENT_GRANTED)
    assert result is DialogState.GREETING  # unchanged
    assert session.state is DialogState.GREETING
    assert any("illegal_transition" in rec.message for rec in caplog.records)
