"""Tests for dialog flow and state machine."""

import pytest
from app.dialog.state_machine import DialogState, DialogStateMachine
from app.dialog.session import CallSession


class TestDialogStateMachine:
    """Test cases for DialogStateMachine."""

    def test_initial_state(self):
        """Test that state machine starts in GREETING state."""
        sm = DialogStateMachine()
        assert sm.get_current_state() == DialogState.GREETING

    def test_valid_transition(self):
        """Test valid state transitions."""
        sm = DialogStateMachine()
        
        # GREETING -> DISCLOSURE
        assert sm.transition_to(DialogState.DISCLOSURE, "starting disclosure")
        assert sm.get_current_state() == DialogState.DISCLOSURE
        
        # DISCLOSURE -> CONSENT
        assert sm.transition_to(DialogState.CONSENT, "requesting consent")
        assert sm.get_current_state() == DialogState.CONSENT

    def test_invalid_transition(self):
        """Test that invalid transitions are rejected."""
        sm = DialogStateMachine()
        
        # Cannot go directly from GREETING to INTAKE
        assert not sm.transition_to(DialogState.INTAKE, "invalid jump")
        assert sm.get_current_state() == DialogState.GREETING

    def test_can_transition_to(self):
        """Test checking if transition is possible."""
        sm = DialogStateMachine()
        
        assert sm.can_transition_to(DialogState.DISCLOSURE)
        assert not sm.can_transition_to(DialogState.INTAKE)

    def test_state_history(self):
        """Test that state history is tracked."""
        sm = DialogStateMachine()
        
        sm.transition_to(DialogState.DISCLOSURE)
        sm.transition_to(DialogState.CONSENT)
        
        history = sm.get_state_history()
        assert len(history) == 3
        assert history[0] == DialogState.GREETING
        assert history[1] == DialogState.DISCLOSURE
        assert history[2] == DialogState.CONSENT

    def test_terminal_state(self):
        """Test terminal state detection."""
        sm = DialogStateMachine()
        
        assert not sm.is_terminal_state()
        
        # Transition to ENDED
        sm.transition_to(DialogState.CLOSE)
        sm.transition_to(DialogState.ENDED)
        
        assert sm.is_terminal_state()

    def test_should_gather_claim_info(self):
        """Test claim info gathering state check."""
        sm = DialogStateMachine()
        
        assert not sm.should_gather_claim_info()
        
        # Transition to INTAKE
        sm.transition_to(DialogState.DISCLOSURE)
        sm.transition_to(DialogState.CONSENT)
        sm.transition_to(DialogState.INTAKE)
        
        assert sm.should_gather_claim_info()


class TestCallSession:
    """Test cases for CallSession."""

    def test_session_creation(self):
        """Test session initialization."""
        session = CallSession(
            call_sid="CA123",
            from_number="+1234567890",
            to_number="+0987654321",
            language="en",
        )
        
        assert session.call_sid == "CA123"
        assert session.from_number == "+1234567890"
        assert session.language == "en"
        assert not session.consent_given

    def test_add_transcript_entry(self):
        """Test adding transcript entries."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        
        session.add_transcript_entry("user", "Hello", confidence=0.95)
        session.add_transcript_entry("assistant", "Hi there")
        
        assert len(session.transcript) == 2
        assert session.transcript[0]["role"] == "user"
        assert session.transcript[0]["confidence"] == 0.95
        assert session.transcript[1]["role"] == "assistant"

    def test_set_consent(self):
        """Test setting consent status."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        
        assert not session.consent_given
        
        session.set_consent(True)
        
        assert session.consent_given
        assert session.consent_timestamp is not None

    def test_update_claim_field(self):
        """Test updating claim fields."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        
        session.update_claim_field("caller_name", "John Doe")
        session.update_claim_field("problem_category", "vehicle_accident")
        
        claim_data = session.get_claim_data()
        assert claim_data["caller_name"] == "John Doe"
        assert claim_data["problem_category"] == "vehicle_accident"

    def test_change_language(self):
        """Test language change tracking."""
        session = CallSession("CA123", "+1234567890", "+0987654321", language="en")
        
        assert session.language == "en"
        
        session.change_language("de")
        
        assert session.language == "de"
        assert len(session.metadata["language_changes"]) == 1
        assert session.metadata["language_changes"][0]["from"] == "en"
        assert session.metadata["language_changes"][0]["to"] == "de"

    def test_low_confidence_tracking(self):
        """Test low confidence counter."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        
        assert session.metadata["low_confidence_count"] == 0
        
        count = session.increment_low_confidence()
        assert count == 1
        
        count = session.increment_low_confidence()
        assert count == 2
        
        session.reset_low_confidence()
        assert session.metadata["low_confidence_count"] == 0

    def test_escalation_request(self):
        """Test escalation request."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        
        assert not session.metadata["escalation_requested"]
        
        session.request_escalation("Low confidence")
        
        assert session.metadata["escalation_requested"]
        assert session.metadata["escalation_reason"] == "Low confidence"

    def test_session_to_dict(self):
        """Test session serialization."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        session.add_transcript_entry("user", "Hello")
        session.set_consent(True)
        
        data = session.to_dict()
        
        assert data["call_sid"] == "CA123"
        assert data["consent_given"] is True
        assert len(data["transcript"]) == 1
        assert "duration_seconds" in data


@pytest.mark.asyncio
class TestDialogFlow:
    """Integration tests for complete dialog flows."""

    async def test_successful_claim_flow(self):
        """Test a successful claim creation flow."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        sm = session.state_machine
        
        # GREETING -> DISCLOSURE
        assert sm.transition_to(DialogState.DISCLOSURE)
        session.add_transcript_entry("assistant", "I'm an AI assistant")
        
        # DISCLOSURE -> CONSENT
        assert sm.transition_to(DialogState.CONSENT)
        session.add_transcript_entry("assistant", "This call will be recorded. OK?")
        session.add_transcript_entry("user", "Yes")
        session.set_consent(True)
        
        # CONSENT -> INTAKE
        assert sm.transition_to(DialogState.INTAKE)
        session.update_claim_field("caller_name", "John Doe")
        session.update_claim_field("problem_category", "vehicle_accident")
        
        # INTAKE -> CONFIRM
        assert sm.transition_to(DialogState.CONFIRM)
        
        # CONFIRM -> CLOSE
        assert sm.transition_to(DialogState.CLOSE)
        session.set_claim_id("CLM-12345")
        
        # Verify final state
        assert session.consent_given
        assert session.claim_id == "CLM-12345"
        assert len(session.transcript) > 0

    async def test_declined_consent_flow(self):
        """Test flow when consent is declined."""
        session = CallSession("CA123", "+1234567890", "+0987654321")
        sm = session.state_machine
        
        # GREETING -> DISCLOSURE -> CONSENT
        sm.transition_to(DialogState.DISCLOSURE)
        sm.transition_to(DialogState.CONSENT)
        
        # User declines consent
        session.add_transcript_entry("user", "No")
        session.set_consent(False)
        
        # Should go directly to CLOSE
        assert sm.transition_to(DialogState.CLOSE)
        assert not session.consent_given
        assert session.claim_id is None