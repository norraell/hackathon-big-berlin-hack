"""Dialog state machine for managing conversation flow."""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DialogState(Enum):
    """States in the dialog flow."""
    
    GREETING = "greeting"
    DISCLOSURE = "disclosure"
    CONSENT = "consent"
    INTAKE = "intake"
    CONFIRM = "confirm"
    CLOSE = "close"
    ENDED = "ended"


class DialogStateMachine:
    """Manages the dialog state transitions.
    
    State flow:
    GREETING → DISCLOSURE → CONSENT → INTAKE → CONFIRM → CLOSE → ENDED
    
    Special transitions:
    - CONSENT (declined) → CLOSE
    - Any state → CLOSE (on error or user request)
    """

    def __init__(self, initial_state: DialogState = DialogState.GREETING) -> None:
        """Initialize the state machine.
        
        Args:
            initial_state: Starting state
        """
        self.current_state = initial_state
        self.previous_state: Optional[DialogState] = None
        self.state_history: list[DialogState] = [initial_state]
        
        logger.info(f"DialogStateMachine initialized in state: {initial_state.value}")

    def transition_to(self, new_state: DialogState, reason: str = "") -> bool:
        """Transition to a new state.
        
        Args:
            new_state: Target state
            reason: Reason for transition (for logging)
            
        Returns:
            True if transition was valid and executed
        """
        if not self._is_valid_transition(self.current_state, new_state):
            logger.warning(
                f"Invalid transition from {self.current_state.value} "
                f"to {new_state.value}"
            )
            return False
        
        self.previous_state = self.current_state
        self.current_state = new_state
        self.state_history.append(new_state)
        
        log_msg = f"State transition: {self.previous_state.value} → {new_state.value}"
        if reason:
            log_msg += f" (reason: {reason})"
        logger.info(log_msg)
        
        return True

    def _is_valid_transition(
        self,
        from_state: DialogState,
        to_state: DialogState,
    ) -> bool:
        """Check if a state transition is valid.
        
        Args:
            from_state: Current state
            to_state: Target state
            
        Returns:
            True if transition is allowed
        """
        # Define valid transitions
        valid_transitions = {
            DialogState.GREETING: [DialogState.DISCLOSURE, DialogState.CLOSE],
            DialogState.DISCLOSURE: [DialogState.CONSENT, DialogState.CLOSE],
            DialogState.CONSENT: [DialogState.INTAKE, DialogState.CLOSE],
            DialogState.INTAKE: [DialogState.CONFIRM, DialogState.CLOSE],
            DialogState.CONFIRM: [DialogState.INTAKE, DialogState.CLOSE],
            DialogState.CLOSE: [DialogState.ENDED],
            DialogState.ENDED: [],  # Terminal state
        }
        
        return to_state in valid_transitions.get(from_state, [])

    def can_transition_to(self, state: DialogState) -> bool:
        """Check if transition to a state is possible.
        
        Args:
            state: Target state
            
        Returns:
            True if transition is valid
        """
        return self._is_valid_transition(self.current_state, state)

    def get_current_state(self) -> DialogState:
        """Get the current state.
        
        Returns:
            Current dialog state
        """
        return self.current_state

    def get_previous_state(self) -> Optional[DialogState]:
        """Get the previous state.
        
        Returns:
            Previous dialog state or None
        """
        return self.previous_state

    def get_state_history(self) -> list[DialogState]:
        """Get the complete state history.
        
        Returns:
            List of states in chronological order
        """
        return self.state_history.copy()

    def is_in_state(self, state: DialogState) -> bool:
        """Check if currently in a specific state.
        
        Args:
            state: State to check
            
        Returns:
            True if in the specified state
        """
        return self.current_state == state

    def is_terminal_state(self) -> bool:
        """Check if in a terminal state.
        
        Returns:
            True if in ENDED state
        """
        return self.current_state == DialogState.ENDED

    def reset(self) -> None:
        """Reset the state machine to initial state."""
        self.current_state = DialogState.GREETING
        self.previous_state = None
        self.state_history = [DialogState.GREETING]
        logger.info("DialogStateMachine reset to GREETING state")

    def get_next_expected_state(self) -> Optional[DialogState]:
        """Get the next expected state in the normal flow.
        
        Returns:
            Next state in the standard flow, or None if at end
        """
        flow_order = [
            DialogState.GREETING,
            DialogState.DISCLOSURE,
            DialogState.CONSENT,
            DialogState.INTAKE,
            DialogState.CONFIRM,
            DialogState.CLOSE,
            DialogState.ENDED,
        ]
        
        try:
            current_index = flow_order.index(self.current_state)
            if current_index < len(flow_order) - 1:
                return flow_order[current_index + 1]
        except ValueError:
            pass
        
        return None

    def should_gather_claim_info(self) -> bool:
        """Check if we should be gathering claim information.
        
        Returns:
            True if in INTAKE or CONFIRM state
        """
        return self.current_state in [DialogState.INTAKE, DialogState.CONFIRM]

    def can_create_claim(self) -> bool:
        """Check if we can create a claim (have consent and info).
        
        Returns:
            True if in CONFIRM or CLOSE state
        """
        return self.current_state in [DialogState.CONFIRM, DialogState.CLOSE]