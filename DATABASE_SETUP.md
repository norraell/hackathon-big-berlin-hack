# Database Setup and Mock Data Guide

This guide explains how to set up the database with insurant, policy, and claims data for the AI Claims Intake System.

## Overview

The system now includes:
- **Insurant Management**: Customer/policyholder information
- **Policy Management**: Insurance policies with comprehensive coverage details
- **Claims Management**: Claims linked to policies and insurants
- **Verification Service**: Policy and identity verification
- **Claims History**: Historical claims data for fraud detection

## Database Schema

### Tables

1. **insurants** - Policyholder information
   - Personal details (name, DOB, contact)
   - Address information
   - Communication preferences
   - Customer flags (power of attorney, vulnerable customer, etc.)

2. **policies** - Insurance policies
   - Policy details (number, product, dates)
   - Vehicle information (make, model, VIN, license plate)
   - Coverage details (Vollkasko, Teilkasko, liability)
   - Driver scope and restrictions
   - Add-ons and special conditions

3. **claims** - Insurance claims
   - Claim details and status
   - Incident information
   - Session and call tracking
   - Transcript and metadata

4. **claims_history** - Historical claims
   - Prior claims for fraud detection
   - Settlement status and amounts
   - Fraud flags and SIU referrals

## Setup Instructions

### 1. Install Dependencies

First, ensure you have the required dependencies:

```bash
pip install sqlalchemy asyncpg alembic psycopg2-binary
```

### 2. Configure Database

Update your `.env` file with the database connection:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/claims_db
```

For local development with Docker:

```bash
docker run -d \
  --name claims-postgres \
  -e POSTGRES_DB=claims_db \
  -e POSTGRES_USER=claims_user \
  -e POSTGRES_PASSWORD=claims_pass \
  -p 5432:5432 \
  postgres:15
```

Then set:
```env
DATABASE_URL=postgresql://claims_user:claims_pass@localhost:5432/claims_db
```

### 3. Initialize Database

Run the initialization script to create all tables:

```bash
python scripts/init_db.py
```

This will create:
- insurants table
- policies table
- claims table
- claims_history table
- All necessary indexes

### 4. Generate Mock Data

Load realistic test data:

```bash
python scripts/generate_mock_data.py
```

This creates 5 test scenarios:

#### Test Scenario 1: Max Mustermann
- **Policy**: POL-2024-001234
- **License Plate**: B-MW-1234
- **VIN**: WBADT43452G123456
- **Vehicle**: BMW 3er 320d
- **Coverage**: Vollkasko + Teilkasko
- **Status**: Active, no claims history
- **Phone**: +49 30 12345678
- **Use Case**: Standard active policy with full coverage

#### Test Scenario 2: Anna Schmidt
- **Policy**: POL-2024-005678
- **License Plate**: M-AS-9876
- **VIN**: WVWZZZ1KZBW123789
- **Vehicle**: VW Golf 1.5 TSI
- **Coverage**: Teilkasko only (no Vollkasko)
- **Status**: Active
- **Phone**: +49 89 98765432
- **Use Case**: Basic coverage, werkstattbindung

#### Test Scenario 3: Thomas Weber
- **Policy**: POL-2023-009876
- **License Plate**: HH-TW-5555
- **VIN**: WDD2050071F234567
- **Vehicle**: Mercedes-Benz C-Klasse
- **Coverage**: Vollkasko + Teilkasko
- **Status**: Active with 2 prior claims
- **Phone**: +49 40 55566677
- **Claims History**:
  - 2023-07-15: Parking damage (€1,200)
  - 2024-02-10: Wildlife collision (€3,500)
- **Use Case**: Testing fraud detection with claim history

#### Test Scenario 4: Maria Gonzalez
- **Policy**: POL-2024-011223
- **License Plate**: S-MG-777
- **VIN**: VBKMZ1234567890AB
- **Vehicle**: Yamaha MT-07 (Motorcycle)
- **Coverage**: Teilkasko
- **Status**: Active (Seasonal: April-October)
- **Phone**: +49 711 44455566
- **Use Case**: Seasonal coverage testing

#### Test Scenario 5: Peter Müller
- **Policy**: POL-2023-007788
- **License Plate**: K-PM-4321
- **VIN**: WAUZZZ8V7DA123456
- **Vehicle**: Audi A4 2.0 TDI
- **Coverage**: Vollkasko + Teilkasko
- **Status**: Active but payment overdue
- **Phone**: +49 221 33344455
- **Use Case**: Testing payment status checks

## Using the Verification Service

### API Endpoint

The verification service is available at `/api/verify-policy`:

```bash
curl -X POST http://localhost:8000/api/verify-policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-2024-001234",
    "caller_name": "Max Mustermann",
    "caller_phone": "+49 30 12345678"
  }'
```

### Verification Process

The service verifies:
1. **Policy Existence**: Finds policy by number, license plate, or VIN
2. **Identity Verification**: Matches caller name and phone with insurant
3. **Coverage Status**: Checks if policy is active and in coverage period
4. **Payment Status**: Verifies premium payments are current
5. **Seasonal Coverage**: Validates seasonal policies are in active period

### Response Format

```json
{
  "verified": true,
  "policy": {
    "policy_id": "...",
    "policy_number": "POL-2024-001234",
    "product_name": "KFZ Komfort Plus",
    "license_plate": "B-MW-1234",
    "vehicle_make": "BMW",
    "vehicle_model": "3er 320d",
    "status": "active",
    "has_vollkasko": true,
    "has_teilkasko": true
  },
  "insurant": {
    "insurant_id": "...",
    "first_name": "Max",
    "last_name": "Mustermann",
    "email": "max.mustermann@example.de",
    "phone": "+49 30 12345678"
  },
  "message": "Verification successful.",
  "coverage_active": true,
  "can_file_claim": true
}
```

## Integration with Claims Service

The claims service now integrates verification:

```python
from app.database import get_async_session
from app.claims.verification import VerificationService
from app.claims.service import ClaimService
from app.claims.insurant_models import VerificationRequest

# Verify policy first
async with get_async_session() as session:
    verification_service = VerificationService(session)
    
    verification_result = await verification_service.verify_policy(
        VerificationRequest(
            policy_number="POL-2024-001234",
            caller_name="Max Mustermann",
            caller_phone="+49 30 12345678"
        )
    )
    
    if verification_result.verified and verification_result.can_file_claim:
        # Create claim with policy linkage
        claim_service = ClaimService(session)
        claim = await claim_service.create_claim(
            claim_data=claim_data,
            policy_id=verification_result.policy.policy_id,
            insurant_id=verification_result.insurant.insurant_id
        )
```

## Fraud Detection

The verification service includes fraud indicators:

```python
fraud_indicators = await verification_service.check_fraud_indicators(
    policy_id=policy_id,
    incident_date=date.today()
)

# Returns:
# {
#     "recent_claims_count": 2,
#     "has_fraud_flags": False,
#     "has_siu_referrals": False,
#     "has_coverage_denials": False,
#     "high_frequency": False
# }
```

## Database Migrations

Using Alembic for schema management:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Testing Verification Scenarios

### Successful Verification
```bash
curl -X POST http://localhost:8000/api/verify-policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-2024-001234",
    "caller_name": "Max Mustermann",
    "caller_phone": "+49 30 12345678"
  }'
```

### Failed Verification (Wrong Name)
```bash
curl -X POST http://localhost:8000/api/verify-policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-2024-001234",
    "caller_name": "Wrong Name",
    "caller_phone": "+49 30 12345678"
  }'
```

### Payment Overdue
```bash
curl -X POST http://localhost:8000/api/verify-policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-2023-007788",
    "caller_name": "Peter Müller",
    "caller_phone": "+49 221 33344455"
  }'
```

### Seasonal Coverage (Out of Season)
Test in November-March:
```bash
curl -X POST http://localhost:8000/api/verify-policy \
  -H "Content-Type: application/json" \
  -d '{
    "policy_number": "POL-2024-011223",
    "caller_name": "Maria Gonzalez",
    "caller_phone": "+49 711 44455566"
  }'
```

## Health Check

Check database connectivity:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "ok",
  "ai_services": "not_implemented"
}
```

## Troubleshooting

### Database Connection Issues

1. Check PostgreSQL is running:
```bash
docker ps | grep postgres
```

2. Test connection:
```bash
psql postgresql://claims_user:claims_pass@localhost:5432/claims_db
```

3. Check logs:
```bash
docker logs claims-postgres
```

### Import Errors

The import errors shown in the IDE are expected if dependencies aren't installed. Install them:

```bash
pip install -r requirements.txt
```

Or if using poetry:
```bash
poetry install
```

### Migration Issues

Reset database (WARNING: destroys all data):
```bash
python scripts/init_db.py
python scripts/generate_mock_data.py
```

## Next Steps

1. **Integrate with Dialog System**: Use verification in the conversation flow
2. **Implement Telematics**: Add vehicle location/speed data
4. **Enhanced Fraud Detection**: ML-based fraud scoring
5. **Document Upload**: Store photos and documents
6. **Notification System**: Email/SMS confirmations

## Support

For issues or questions, check:
- Application logs: Check console output
- Database logs: `docker logs claims-postgres`
- API documentation: http://localhost:8000/docs (when running)