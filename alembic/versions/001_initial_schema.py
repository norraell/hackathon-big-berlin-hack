"""Initial schema with insurants, policies, and claims.

Revision ID: 001
Revises: 
Create Date: 2024-04-25 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create insurants table
    op.create_table(
        'insurants',
        sa.Column('insurant_id', sa.String(36), primary_key=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('phone', sa.String(50), nullable=False),
        sa.Column('address_street', sa.String(255), nullable=False),
        sa.Column('address_city', sa.String(100), nullable=False),
        sa.Column('address_postal_code', sa.String(20), nullable=False),
        sa.Column('address_country', sa.String(2), nullable=False, server_default='DE'),
        sa.Column('preferred_language', sa.String(10), nullable=False, server_default='de'),
        sa.Column('preferred_communication_channel', sa.String(50), nullable=False, server_default='email'),
        sa.Column('has_power_of_attorney', sa.Boolean(), server_default='false'),
        sa.Column('is_vulnerable_customer', sa.Boolean(), server_default='false'),
        sa.Column('marketing_consent', sa.Boolean(), server_default='false'),
        sa.Column('customer_since', sa.Date(), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create policies table
    op.create_table(
        'policies',
        sa.Column('policy_id', sa.String(36), primary_key=True),
        sa.Column('policy_number', sa.String(50), nullable=False, unique=True),
        sa.Column('insurant_id', sa.String(36), sa.ForeignKey('insurants.insurant_id'), nullable=False),
        sa.Column('product_name', sa.String(100), nullable=False),
        sa.Column('tariff_version', sa.String(50), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('renewal_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('annual_premium', sa.Float(), nullable=False),
        sa.Column('payment_status', sa.String(50), nullable=False, server_default='current'),
        sa.Column('license_plate', sa.String(20), nullable=False),
        sa.Column('vin', sa.String(17), nullable=False),
        sa.Column('vehicle_make', sa.String(50), nullable=False),
        sa.Column('vehicle_model', sa.String(100), nullable=False),
        sa.Column('first_registration', sa.Date(), nullable=False),
        sa.Column('engine_power_kw', sa.Integer(), nullable=False),
        sa.Column('fuel_type', sa.String(50), nullable=False),
        sa.Column('vehicle_value', sa.Float(), nullable=False),
        sa.Column('current_sum_insured', sa.Float(), nullable=False),
        sa.Column('use_type', sa.String(50), nullable=False, server_default='private'),
        sa.Column('annual_mileage', sa.Integer(), nullable=False),
        sa.Column('garage_address', sa.String(500), nullable=True),
        sa.Column('liability_sum', sa.Float(), nullable=False, server_default='100000000.0'),
        sa.Column('has_vollkasko', sa.Boolean(), server_default='false'),
        sa.Column('has_teilkasko', sa.Boolean(), server_default='false'),
        sa.Column('deductible_vollkasko', sa.Float(), nullable=True),
        sa.Column('deductible_teilkasko', sa.Float(), nullable=True),
        sa.Column('addons', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('sf_class_liability', sa.String(10), nullable=True),
        sa.Column('sf_class_vollkasko', sa.String(10), nullable=True),
        sa.Column('has_rabattschutz', sa.Boolean(), server_default='false'),
        sa.Column('has_werkstattbindung', sa.Boolean(), server_default='false'),
        sa.Column('driver_scope', sa.String(50), nullable=False, server_default='named_drivers'),
        sa.Column('min_driver_age', sa.Integer(), nullable=True),
        sa.Column('named_drivers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('country_coverage', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('seasonal_months', sa.String(50), nullable=True),
        sa.Column('gross_negligence_waived', sa.Boolean(), server_default='false'),
        sa.Column('has_telematics', sa.Boolean(), server_default='false'),
        sa.Column('broker_id', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create claims table
    op.create_table(
        'claims',
        sa.Column('claim_id', sa.String(36), primary_key=True),
        sa.Column('caller_name', sa.String(255), nullable=False),
        sa.Column('contact_phone', sa.String(50), nullable=False),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('problem_category', sa.String(50), nullable=False),
        sa.Column('problem_description', sa.Text(), nullable=False),
        sa.Column('incident_date', sa.DateTime(), nullable=False),
        sa.Column('incident_location', sa.String(500), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='submitted'),
        sa.Column('estimated_damage', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('call_sid', sa.String(100), nullable=False),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('transcript', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create claims_history table
    op.create_table(
        'claims_history',
        sa.Column('history_id', sa.String(36), primary_key=True),
        sa.Column('policy_id', sa.String(36), sa.ForeignKey('policies.policy_id'), nullable=False),
        sa.Column('claim_id', sa.String(36), nullable=True),
        sa.Column('claim_date', sa.Date(), nullable=False),
        sa.Column('claim_type', sa.String(50), nullable=False),
        sa.Column('claim_amount', sa.Float(), nullable=False),
        sa.Column('fault_quota', sa.Float(), nullable=True),
        sa.Column('settlement_status', sa.String(50), nullable=False),
        sa.Column('fraud_flag', sa.Boolean(), server_default='false'),
        sa.Column('siu_referral', sa.Boolean(), server_default='false'),
        sa.Column('coverage_denied', sa.Boolean(), server_default='false'),
        sa.Column('denial_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )
    
    # Create indexes
    op.create_index('idx_insurants_email', 'insurants', ['email'])
    op.create_index('idx_policies_policy_number', 'policies', ['policy_number'])
    op.create_index('idx_policies_license_plate', 'policies', ['license_plate'])
    op.create_index('idx_policies_vin', 'policies', ['vin'])
    op.create_index('idx_policies_insurant_id', 'policies', ['insurant_id'])
    op.create_index('idx_claims_session_id', 'claims', ['session_id'])
    op.create_index('idx_claims_call_sid', 'claims', ['call_sid'])
    op.create_index('idx_claims_history_policy_id', 'claims_history', ['policy_id'])
    op.create_index('idx_claims_history_claim_date', 'claims_history', ['claim_date'])


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop indexes
    op.drop_index('idx_claims_history_claim_date')
    op.drop_index('idx_claims_history_policy_id')
    op.drop_index('idx_claims_call_sid')
    op.drop_index('idx_claims_session_id')
    op.drop_index('idx_policies_insurant_id')
    op.drop_index('idx_policies_vin')
    op.drop_index('idx_policies_license_plate')
    op.drop_index('idx_policies_policy_number')
    op.drop_index('idx_insurants_email')
    
    # Drop tables
    op.drop_table('claims_history')
    op.drop_table('claims')
    op.drop_table('policies')
    op.drop_table('insurants')