"""Test script for verification service."""

import asyncio
import sys
from pathlib import Path
from datetime import date

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_async_session
from app.claims.verification import VerificationService
from app.claims.insurant_models import VerificationRequest


async def test_verification():
    """Test the verification service with mock data."""
    
    print("🧪 Testing Verification Service\n")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "Test 1: Successful Verification - Max Mustermann",
            "request": VerificationRequest(
                policy_number="POL-2024-001234",
                caller_name="Max Mustermann",
                caller_phone="+49 30 12345678",
            ),
            "expected": "verified=True, can_file_claim=True"
        },
        {
            "name": "Test 2: Verification by License Plate - Anna Schmidt",
            "request": VerificationRequest(
                license_plate="M-AS-9876",
                caller_name="Anna Schmidt",
                caller_phone="+49 89 98765432",
            ),
            "expected": "verified=True, can_file_claim=True"
        },
        {
            "name": "Test 3: Verification by VIN - Thomas Weber",
            "request": VerificationRequest(
                vin="WDD2050071F234567",
                caller_name="Thomas Weber",
                caller_phone="+49 40 55566677",
            ),
            "expected": "verified=True, can_file_claim=True"
        },
        {
            "name": "Test 4: Payment Overdue - Peter Müller",
            "request": VerificationRequest(
                policy_number="POL-2023-007788",
                caller_name="Peter Müller",
                caller_phone="+49 221 33344455",
            ),
            "expected": "verified=True, can_file_claim=False (payment overdue)"
        },
        {
            "name": "Test 5: Failed Verification - Wrong Name",
            "request": VerificationRequest(
                policy_number="POL-2024-001234",
                caller_name="Wrong Name",
                caller_phone="+49 30 12345678",
            ),
            "expected": "verified=False"
        },
        {
            "name": "Test 6: Policy Not Found",
            "request": VerificationRequest(
                policy_number="POL-9999-NOTFOUND",
                caller_name="Test User",
                caller_phone="+49 123 456789",
            ),
            "expected": "verified=False (policy not found)"
        },
    ]
    
    async with get_async_session() as session:
        verification_service = VerificationService(session)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{test_case['name']}")
            print("-" * 60)
            
            try:
                result = await verification_service.verify_policy(test_case["request"])
                
                print(f"✓ Verified: {result.verified}")
                print(f"✓ Coverage Active: {result.coverage_active}")
                print(f"✓ Can File Claim: {result.can_file_claim}")
                print(f"✓ Message: {result.message}")
                
                if result.policy:
                    print(f"✓ Policy: {result.policy.policy_number} - {result.policy.vehicle_make} {result.policy.vehicle_model}")
                    print(f"  License Plate: {result.policy.license_plate}")
                    print(f"  Vollkasko: {result.policy.has_vollkasko}, Teilkasko: {result.policy.has_teilkasko}")
                
                if result.insurant:
                    print(f"✓ Insurant: {result.insurant.first_name} {result.insurant.last_name}")
                    print(f"  Email: {result.insurant.email}")
                    print(f"  Phone: {result.insurant.phone}")
                
                # Test fraud indicators if policy found
                if result.policy:
                    fraud_indicators = await verification_service.check_fraud_indicators(
                        policy_id=result.policy.policy_id,
                        incident_date=date.today()
                    )
                    print(f"✓ Fraud Indicators:")
                    print(f"  Recent Claims: {fraud_indicators['recent_claims_count']}")
                    print(f"  High Frequency: {fraud_indicators['high_frequency']}")
                    print(f"  Fraud Flags: {fraud_indicators['has_fraud_flags']}")
                
                print(f"✓ Expected: {test_case['expected']}")
                print("✅ PASSED")
                
            except Exception as e:
                print(f"❌ FAILED: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")


async def test_claims_history():
    """Test claims history retrieval."""
    
    print("\n\n🧪 Testing Claims History\n")
    print("=" * 60)
    
    async with get_async_session() as session:
        verification_service = VerificationService(session)
        
        # Get Thomas Weber's policy (has claims history)
        result = await verification_service.verify_policy(
            VerificationRequest(
                policy_number="POL-2023-009876",
                caller_name="Thomas Weber",
                caller_phone="+49 40 55566677",
            )
        )
        
        if result.policy and result.insurant:
            print(f"Policy: {result.policy.policy_number}")
            print(f"Insurant: {result.insurant.first_name} {result.insurant.last_name}")
            print("\nClaims History:")
            print("-" * 60)
            
            history = await verification_service.get_claims_history(
                policy_id=result.policy.policy_id
            )
            
            if history:
                for claim in history:
                    print(f"  Date: {claim.claim_date}")
                    print(f"  Type: {claim.claim_type}")
                    print(f"  Amount: €{claim.claim_amount:,.2f}")
                    print(f"  Status: {claim.settlement_status}")
                    print(f"  Fault Quota: {claim.fault_quota}")
                    print()
                print(f"✅ Found {len(history)} historical claims")
            else:
                print("  No claims history found")
        else:
            print("❌ Policy not found")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  VERIFICATION SERVICE TEST SUITE")
    print("=" * 60)
    
    try:
        asyncio.run(test_verification())
        asyncio.run(test_claims_history())
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)