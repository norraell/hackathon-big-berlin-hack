"""Policy and insurant verification service."""

import logging
from datetime import date, datetime
from typing import Optional, Tuple

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.claims.insurant_models import (
    Insurant,
    Policy,
    ClaimsHistory,
    PolicyStatus,
    VerificationRequest,
    VerificationResponse,
    InsurantResponse,
    PolicyResponse,
)

logger = logging.getLogger(__name__)


class VerificationService:
    """Service for verifying policy and insurant information."""
    
    def __init__(self, session: AsyncSession):
        """Initialize verification service.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def verify_policy(
        self,
        request: VerificationRequest
    ) -> VerificationResponse:
        """Verify policy and insurant information.
        
        Args:
            request: Verification request with policy/vehicle identifiers
            
        Returns:
            Verification response with policy and insurant details
        """
        logger.info(f"Verifying policy for caller: {request.caller_name}")
        
        # Find policy by identifiers
        policy = await self._find_policy(
            policy_number=request.policy_number,
            license_plate=request.license_plate,
            vin=request.vin,
        )
        
        if not policy:
            logger.warning("Policy not found")
            return VerificationResponse(
                verified=False,
                message="Policy not found. Please check your policy number, license plate, or VIN.",
                coverage_active=False,
                can_file_claim=False,
            )
        
        # Load insurant
        insurant = await self._get_insurant(policy.insurant_id)
        
        if not insurant:
            logger.error(f"Insurant not found for policy {policy.policy_number}")
            return VerificationResponse(
                verified=False,
                message="Policy holder information not found.",
                coverage_active=False,
                can_file_claim=False,
            )
        
        # Verify caller identity
        identity_verified = await self._verify_identity(
            insurant=insurant,
            caller_name=request.caller_name,
            caller_phone=request.caller_phone,
            date_of_birth=request.date_of_birth,
        )
        
        if not identity_verified:
            logger.warning(f"Identity verification failed for {request.caller_name}")
            return VerificationResponse(
                verified=False,
                message="Identity verification failed. Please verify your personal information.",
                coverage_active=False,
                can_file_claim=False,
            )
        
        # Check policy status and coverage
        coverage_active = await self._check_coverage_active(policy)
        can_file_claim = coverage_active and policy.payment_status == "current"
        
        # Build response
        policy_response = PolicyResponse.model_validate(policy)
        insurant_response = InsurantResponse.model_validate(insurant)
        
        message = "Verification successful."
        if not coverage_active:
            message = "Policy found but coverage is not active."
        elif not can_file_claim:
            message = "Policy found but premium payment is overdue."
        
        logger.info(f"Verification completed for policy {policy.policy_number}: verified={identity_verified}, active={coverage_active}")
        
        return VerificationResponse(
            verified=identity_verified,
            policy=policy_response,
            insurant=insurant_response,
            message=message,
            coverage_active=coverage_active,
            can_file_claim=can_file_claim,
        )
    
    async def _find_policy(
        self,
        policy_number: Optional[str] = None,
        license_plate: Optional[str] = None,
        vin: Optional[str] = None,
    ) -> Optional[Policy]:
        """Find policy by various identifiers.
        
        Args:
            policy_number: Policy number
            license_plate: Vehicle license plate
            vin: Vehicle identification number
            
        Returns:
            Policy if found, None otherwise
        """
        conditions = []
        
        if policy_number:
            conditions.append(Policy.policy_number == policy_number)
        if license_plate:
            conditions.append(Policy.license_plate == license_plate.upper())
        if vin:
            conditions.append(Policy.vin == vin.upper())
        
        if not conditions:
            return None
        
        query = select(Policy).where(or_(*conditions))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def _get_insurant(self, insurant_id: str) -> Optional[Insurant]:
        """Get insurant by ID.
        
        Args:
            insurant_id: Insurant ID
            
        Returns:
            Insurant if found, None otherwise
        """
        query = select(Insurant).where(Insurant.insurant_id == insurant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def _verify_identity(
        self,
        insurant: Insurant,
        caller_name: str,
        caller_phone: str,
        date_of_birth: Optional[date] = None,
    ) -> bool:
        """Verify caller identity against insurant record.
        
        Args:
            insurant: Insurant record
            caller_name: Caller's name
            caller_phone: Caller's phone number
            date_of_birth: Caller's date of birth (optional)
            
        Returns:
            True if identity verified, False otherwise
        """
        # Normalize phone number (remove spaces, dashes, etc.)
        normalized_caller_phone = "".join(filter(str.isdigit, caller_phone))
        normalized_insurant_phone = "".join(filter(str.isdigit, insurant.phone))
        
        # Check phone number match
        phone_match = normalized_caller_phone in normalized_insurant_phone or \
                     normalized_insurant_phone in normalized_caller_phone
        
        # Check name match (case-insensitive, partial match)
        full_name = f"{insurant.first_name} {insurant.last_name}".lower()
        caller_name_lower = caller_name.lower()
        name_match = (
            insurant.first_name.lower() in caller_name_lower or
            insurant.last_name.lower() in caller_name_lower or
            caller_name_lower in full_name
        )
        
        # Check date of birth if provided
        dob_match = True
        if date_of_birth:
            dob_match = insurant.date_of_birth == date_of_birth
        
        # Require at least phone match and name match
        verified = phone_match and name_match and dob_match
        
        logger.debug(f"Identity verification: phone={phone_match}, name={name_match}, dob={dob_match}")
        
        return verified
    
    async def _check_coverage_active(self, policy: Policy) -> bool:
        """Check if policy coverage is currently active.
        
        Args:
            policy: Policy record
            
        Returns:
            True if coverage is active, False otherwise
        """
        today = date.today()
        
        # Check policy status
        if policy.status != PolicyStatus.ACTIVE.value:
            return False
        
        # Check effective and renewal dates
        if policy.effective_date > today:
            return False
        
        if policy.renewal_date < today:
            return False
        
        # Check seasonal coverage if applicable
        if policy.seasonal_months:
            current_month = today.month
            start_month, end_month = map(int, policy.seasonal_months.split("-"))
            
            if start_month <= end_month:
                # Normal range (e.g., 04-10)
                if not (start_month <= current_month <= end_month):
                    return False
            else:
                # Wrap-around range (e.g., 11-03)
                if not (current_month >= start_month or current_month <= end_month):
                    return False
        
        return True
    
    async def get_claims_history(
        self,
        policy_id: str,
        limit: int = 10
    ) -> list[ClaimsHistory]:
        """Get claims history for a policy.
        
        Args:
            policy_id: Policy ID
            limit: Maximum number of records to return
            
        Returns:
            List of claims history records
        """
        query = (
            select(ClaimsHistory)
            .where(ClaimsHistory.policy_id == policy_id)
            .order_by(ClaimsHistory.claim_date.desc())
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def check_fraud_indicators(
        self,
        policy_id: str,
        incident_date: date
    ) -> dict:
        """Check for fraud indicators based on claims history.
        
        Args:
            policy_id: Policy ID
            incident_date: Date of current incident
            
        Returns:
            Dictionary with fraud indicators
        """
        # Get recent claims (last 24 months)
        two_years_ago = date(incident_date.year - 2, incident_date.month, incident_date.day)
        
        query = (
            select(ClaimsHistory)
            .where(
                and_(
                    ClaimsHistory.policy_id == policy_id,
                    ClaimsHistory.claim_date >= two_years_ago
                )
            )
        )
        
        result = await self.session.execute(query)
        recent_claims = list(result.scalars().all())
        
        # Calculate indicators
        indicators = {
            "recent_claims_count": len(recent_claims),
            "has_fraud_flags": any(claim.fraud_flag for claim in recent_claims),
            "has_siu_referrals": any(claim.siu_referral for claim in recent_claims),
            "has_coverage_denials": any(claim.coverage_denied for claim in recent_claims),
            "high_frequency": len(recent_claims) >= 3,
        }
        
        return indicators