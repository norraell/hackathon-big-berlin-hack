"""Service layer for claim operations."""

import logging
from datetime import datetime
from typing import Optional

from app.claims.models import Claim, ClaimCreate, ClaimUpdate, ClaimResponse

logger = logging.getLogger(__name__)


class ClaimService:
    """Service for managing claims."""

    def __init__(self, db_session) -> None:
        """Initialize claim service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session

    async def create_claim(self, claim_data: ClaimCreate) -> ClaimResponse:
        """Create a new claim.
        
        Args:
            claim_data: Claim creation data
            
        Returns:
            Created claim
        """
        try:
            # Create claim instance
            claim = Claim(
                caller_name=claim_data.caller_name,
                contact_phone=claim_data.contact_phone,
                contact_email=claim_data.contact_email,
                problem_category=claim_data.problem_category,
                problem_description=claim_data.problem_description,
                incident_date=claim_data.incident_date,
                incident_location=claim_data.incident_location,
                severity=claim_data.severity,
                estimated_damage=claim_data.estimated_damage,
                session_id=claim_data.session_id,
                call_sid=claim_data.call_sid,
                language=claim_data.language,
                transcript=claim_data.transcript,
                metadata=claim_data.metadata,
            )
            
            # Add to database
            self.db.add(claim)
            await self.db.commit()
            await self.db.refresh(claim)
            
            logger.info(f"Claim created: {claim.claim_id}")
            
            return ClaimResponse.from_orm(claim)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating claim: {e}", exc_info=True)
            raise

    async def get_claim(self, claim_id: str) -> Optional[ClaimResponse]:
        """Get a claim by ID.
        
        Args:
            claim_id: Claim ID
            
        Returns:
            Claim or None if not found
        """
        try:
            claim = await self.db.get(Claim, claim_id)
            
            if claim:
                return ClaimResponse.from_orm(claim)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting claim {claim_id}: {e}", exc_info=True)
            raise

    async def update_claim(
        self,
        claim_id: str,
        claim_data: ClaimUpdate,
    ) -> Optional[ClaimResponse]:
        """Update an existing claim.
        
        Args:
            claim_id: Claim ID
            claim_data: Update data
            
        Returns:
            Updated claim or None if not found
        """
        try:
            claim = await self.db.get(Claim, claim_id)
            
            if not claim:
                return None
            
            # Update fields
            update_dict = claim_data.dict(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(claim, field, value)
            
            claim.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(claim)
            
            logger.info(f"Claim updated: {claim_id}")
            
            return ClaimResponse.from_orm(claim)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating claim {claim_id}: {e}", exc_info=True)
            raise

    async def attach_transcript(
        self,
        claim_id: str,
        transcript: list,
    ) -> Optional[ClaimResponse]:
        """Attach transcript to a claim.
        
        Args:
            claim_id: Claim ID
            transcript: Transcript data
            
        Returns:
            Updated claim or None if not found
        """
        try:
            claim = await self.db.get(Claim, claim_id)
            
            if not claim:
                return None
            
            claim.transcript = transcript
            claim.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(claim)
            
            logger.info(f"Transcript attached to claim: {claim_id}")
            
            return ClaimResponse.from_orm(claim)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error attaching transcript to claim {claim_id}: {e}", exc_info=True)
            raise

    async def get_claims_by_session(self, session_id: str) -> list[ClaimResponse]:
        """Get all claims for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of claims
        """
        try:
            # TODO: Implement query
            # result = await self.db.execute(
            #     select(Claim).where(Claim.session_id == session_id)
            # )
            # claims = result.scalars().all()
            
            # return [ClaimResponse.from_orm(claim) for claim in claims]
            
            # Placeholder
            return []
            
        except Exception as e:
            logger.error(f"Error getting claims for session {session_id}: {e}", exc_info=True)
            raise

    async def delete_claim(self, claim_id: str) -> bool:
        """Delete a claim (for GDPR compliance).
        
        Args:
            claim_id: Claim ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            claim = await self.db.get(Claim, claim_id)
            
            if not claim:
                return False
            
            await self.db.delete(claim)
            await self.db.commit()
            
            logger.info(f"Claim deleted: {claim_id}")
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting claim {claim_id}: {e}", exc_info=True)
            raise


def format_claim_id_for_speech(claim_id: str) -> str:
    """Format claim ID for clear speech readback.
    
    Args:
        claim_id: Claim ID (e.g., "abc123-def456")
        
    Returns:
        Formatted string for TTS (e.g., "A B C 1 2 3 dash D E F 4 5 6")
    """
    # Split by dashes
    parts = claim_id.split("-")
    
    formatted_parts = []
    for part in parts:
        # Spell out each character with spaces
        spelled = " ".join(part.upper())
        formatted_parts.append(spelled)
    
    # Join with "dash"
    return " dash ".join(formatted_parts)