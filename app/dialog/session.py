"""Session management for per-call state and data."""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from app.dialog.state_machine import DialogState, DialogStateMachine

logger = logging.getLogger(__name__)


class CallSession:
    """Manages state and data for a single call session.
    
    This is the single source of truth for session state.
    """

    def __init__(
        self,
        call_sid: str,
        from_number: str,
        to_number: str,
        language: str = "en",
    ) -> None:
        """Initialize a new call session.
        
        Args:
            call_sid: Twilio call SID
            from_number: Caller's phone number
            to_number: Called number
            language: Initial language
        """
        self.session_id = str(uuid4())
        self.call_sid = call_sid
        self.from_number = from_number
        self.to_number = to_number
        self.language = language
        
        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.ended_at: Optional[datetime] = None
        
        # State machine
        self.state_machine = DialogStateMachine()
        
        # Consent tracking
        self.consent_given = False
        self.consent_timestamp: Optional[datetime] = None
        
        # Transcript
        self.transcript: list[dict[str, Any]] = []
        
        # Partial claim data being gathered
        self.partial_claim: dict[str, Any] = {}
        
        # Claim ID once created
        self.claim_id: Optional[str] = None
        
        # Metadata
        self.metadata: dict[str, Any] = {
            "low_confidence_count": 0,
            "escalation_requested": False,
            "language_changes": [],
        }
        
        logger.info(
            f"CallSession created - ID: {self.session_id}, "
            f"CallSID: {call_sid}, From: {from_number}"
        )

    def update_timestamp(self) -> None:
        """Update the last updated timestamp."""
        self.updated_at = datetime.utcnow()

    def add_transcript_entry(
        self,
        role: str,
        content: str,
        confidence: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an entry to the transcript.
        
        Args:
            role: Speaker role ('user' or 'assistant')
            content: Transcript content
            confidence: STT confidence score (for user messages)
            timestamp: Entry timestamp (defaults to now)
        """
        entry = {
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.utcnow(),
        }
        
        if confidence is not None:
            entry["confidence"] = confidence
        
        self.transcript.append(entry)
        self.update_timestamp()
        
        logger.debug(f"Transcript entry added: {role} - {content[:50]}...")

    def truncate_last_assistant_message(self, truncated_text: str) -> None:
        """Truncate the last assistant message (for barge-in).
        
        Args:
            truncated_text: The text that was actually spoken
        """
        # Find last assistant message
        for i in range(len(self.transcript) - 1, -1, -1):
            if self.transcript[i]["role"] == "assistant":
                original = self.transcript[i]["content"]
                self.transcript[i]["content"] = truncated_text
                self.transcript[i]["truncated"] = True
                self.transcript[i]["original_content"] = original
                logger.info(
                    f"Truncated assistant message from '{original}' "
                    f"to '{truncated_text}'"
                )
                break

    def set_consent(self, given: bool) -> None:
        """Set recording consent status.
        
        Args:
            given: Whether consent was given
        """
        self.consent_given = given
        self.consent_timestamp = datetime.utcnow()
        self.update_timestamp()
        
        logger.info(f"Consent {'given' if given else 'declined'}")

    def update_claim_field(self, field: str, value: Any) -> None:
        """Update a field in the partial claim.
        
        Args:
            field: Field name
            value: Field value
        """
        self.partial_claim[field] = value
        self.update_timestamp()
        
        logger.info(f"Claim field updated: {field} = {value}")

    def get_claim_data(self) -> dict[str, Any]:
        """Get the current claim data.
        
        Returns:
            Dictionary of claim fields
        """
        return self.partial_claim.copy()

    def set_claim_id(self, claim_id: str) -> None:
        """Set the claim ID after creation.
        
        Args:
            claim_id: Created claim ID
        """
        self.claim_id = claim_id
        self.update_timestamp()
        
        logger.info(f"Claim ID set: {claim_id}")

    def change_language(self, new_language: str) -> None:
        """Change the session language.
        
        Args:
            new_language: New language code
        """
        old_language = self.language
        self.language = new_language
        self.metadata["language_changes"].append({
            "from": old_language,
            "to": new_language,
            "timestamp": datetime.utcnow(),
        })
        self.update_timestamp()
        
        logger.info(f"Language changed from {old_language} to {new_language}")

    def increment_low_confidence(self) -> int:
        """Increment low confidence counter.
        
        Returns:
            New count
        """
        self.metadata["low_confidence_count"] += 1
        count = self.metadata["low_confidence_count"]
        
        logger.warning(f"Low confidence count: {count}")
        
        return count

    def reset_low_confidence(self) -> None:
        """Reset low confidence counter."""
        self.metadata["low_confidence_count"] = 0

    def request_escalation(self, reason: str) -> None:
        """Mark session for escalation to human.
        
        Args:
            reason: Reason for escalation
        """
        self.metadata["escalation_requested"] = True
        self.metadata["escalation_reason"] = reason
        self.metadata["escalation_timestamp"] = datetime.utcnow()
        self.update_timestamp()
        
        logger.info(f"Escalation requested: {reason}")

    def end_session(self) -> None:
        """Mark the session as ended."""
        self.ended_at = datetime.utcnow()
        self.state_machine.transition_to(DialogState.ENDED, "session ended")
        self.update_timestamp()
        
        logger.info(f"Session ended - ID: {self.session_id}")

    def get_duration_seconds(self) -> float:
        """Get session duration in seconds.
        
        Returns:
            Duration in seconds
        """
        end_time = self.ended_at or datetime.utcnow()
        return (end_time - self.created_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for storage.
        
        Returns:
            Dictionary representation
        """
        return {
            "session_id": self.session_id,
            "call_sid": self.call_sid,
            "from_number": self.from_number,
            "to_number": self.to_number,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "current_state": self.state_machine.get_current_state().value,
            "state_history": [s.value for s in self.state_machine.get_state_history()],
            "consent_given": self.consent_given,
            "consent_timestamp": (
                self.consent_timestamp.isoformat() if self.consent_timestamp else None
            ),
            "transcript": self.transcript,
            "partial_claim": self.partial_claim,
            "claim_id": self.claim_id,
            "metadata": self.metadata,
            "duration_seconds": self.get_duration_seconds(),
        }

    def __repr__(self) -> str:
        """String representation of session."""
        return (
            f"CallSession(id={self.session_id}, call_sid={self.call_sid}, "
            f"state={self.state_machine.get_current_state().value}, "
            f"language={self.language})"
        )