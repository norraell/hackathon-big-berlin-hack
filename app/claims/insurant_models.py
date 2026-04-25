"""SQLAlchemy and Pydantic models for insurants and policies."""

from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Date, Text, Boolean, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, EmailStr
import enum

Base = declarative_base()


class CoverageType(str, enum.Enum):
    """Coverage type enumeration."""
    LIABILITY = "liability"
    VOLLKASKO = "vollkasko"
    TEILKASKO = "teilkasko"
    GAP = "gap"
    NEUWERT = "neuwert"
    MALLORCA = "mallorca"
    AUSLANDSSCHUTZ = "auslandsschutz"
    SCHUTZBRIEF = "schutzbrief"
    FAHRERSCHUTZ = "fahrerschutz"


class VehicleUseType(str, enum.Enum):
    """Vehicle use type enumeration."""
    PRIVATE = "private"
    COMMERCIAL = "commercial"
    COMPANY_CAR = "company_car"
    RENTAL = "rental"
    DRIVING_SCHOOL = "driving_school"
    TAXI = "taxi"


class PolicyStatus(str, enum.Enum):
    """Policy status enumeration."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# SQLAlchemy Models
class Insurant(Base):
    """Database model for insurants (policyholders)."""
    
    __tablename__ = "insurants"
    
    # Primary key
    insurant_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    
    # Contact information
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=False)
    address_street = Column(String(255), nullable=False)
    address_city = Column(String(100), nullable=False)
    address_postal_code = Column(String(20), nullable=False)
    address_country = Column(String(2), nullable=False, default="DE")
    
    # Preferences
    preferred_language = Column(String(10), nullable=False, default="de")
    preferred_communication_channel = Column(String(50), nullable=False, default="email")
    
    # Flags
    has_power_of_attorney = Column(Boolean, default=False)
    is_vulnerable_customer = Column(Boolean, default=False)
    marketing_consent = Column(Boolean, default=False)
    
    # Metadata
    customer_since = Column(Date, nullable=False)
    insurant_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    policies = relationship("Policy", back_populates="insurant")
    
    def __repr__(self) -> str:
        return f"<Insurant(id={self.insurant_id}, name={self.first_name} {self.last_name})>"


class Policy(Base):
    """Database model for insurance policies."""
    
    __tablename__ = "policies"
    
    # Primary key
    policy_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    policy_number = Column(String(50), nullable=False, unique=True)
    
    # Foreign key to insurant
    insurant_id = Column(String(36), ForeignKey("insurants.insurant_id"), nullable=False)
    
    # Policy details
    product_name = Column(String(100), nullable=False)
    tariff_version = Column(String(50), nullable=False)
    effective_date = Column(Date, nullable=False)
    renewal_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default=PolicyStatus.ACTIVE.value)
    
    # Premium
    annual_premium = Column(Float, nullable=False)
    payment_status = Column(String(50), nullable=False, default="current")
    
    # Vehicle information
    license_plate = Column(String(20), nullable=False)
    vin = Column(String(17), nullable=False)
    vehicle_make = Column(String(50), nullable=False)
    vehicle_model = Column(String(100), nullable=False)
    first_registration = Column(Date, nullable=False)
    engine_power_kw = Column(Integer, nullable=False)
    fuel_type = Column(String(50), nullable=False)
    vehicle_value = Column(Float, nullable=False)
    current_sum_insured = Column(Float, nullable=False)
    use_type = Column(String(50), nullable=False, default=VehicleUseType.PRIVATE.value)
    annual_mileage = Column(Integer, nullable=False)
    garage_address = Column(String(500), nullable=True)
    
    # Coverage details
    liability_sum = Column(Float, nullable=False, default=100000000.0)  # €100M
    has_vollkasko = Column(Boolean, default=False)
    has_teilkasko = Column(Boolean, default=False)
    deductible_vollkasko = Column(Float, nullable=True)
    deductible_teilkasko = Column(Float, nullable=True)
    
    # Add-ons (stored as JSON for flexibility)
    addons = Column(JSON, nullable=True)
    
    # No-claims class
    sf_class_liability = Column(String(10), nullable=True)
    sf_class_vollkasko = Column(String(10), nullable=True)
    has_rabattschutz = Column(Boolean, default=False)
    has_werkstattbindung = Column(Boolean, default=False)
    
    # Driver scope
    driver_scope = Column(String(50), nullable=False, default="named_drivers")
    min_driver_age = Column(Integer, nullable=True)
    named_drivers = Column(JSON, nullable=True)  # List of driver objects
    
    # Geographic and temporal scope
    country_coverage = Column(JSON, nullable=True)  # List of country codes
    seasonal_months = Column(String(50), nullable=True)  # e.g., "04-10"
    
    # Special conditions
    gross_negligence_waived = Column(Boolean, default=False)
    has_telematics = Column(Boolean, default=False)
    
    # Metadata
    broker_id = Column(String(50), nullable=True)
    policy_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    insurant = relationship("Insurant", back_populates="policies")
    
    def __repr__(self) -> str:
        return f"<Policy(number={self.policy_number}, vehicle={self.license_plate})>"


class ClaimsHistory(Base):
    """Database model for claims history."""
    
    __tablename__ = "claims_history"
    
    # Primary key
    history_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Foreign keys
    policy_id = Column(String(36), ForeignKey("policies.policy_id"), nullable=False)
    claim_id = Column(String(36), nullable=True)  # Reference to actual claim
    
    # Claim details
    claim_date = Column(Date, nullable=False)
    claim_type = Column(String(50), nullable=False)
    claim_amount = Column(Float, nullable=False)
    fault_quota = Column(Float, nullable=True)  # 0.0 to 1.0
    settlement_status = Column(String(50), nullable=False)
    
    # Flags
    fraud_flag = Column(Boolean, default=False)
    siu_referral = Column(Boolean, default=False)
    coverage_denied = Column(Boolean, default=False)
    denial_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ClaimsHistory(policy={self.policy_id}, date={self.claim_date})>"


# Pydantic Models for API
class InsurantCreate(BaseModel):
    """Schema for creating a new insurant."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=50)
    address_street: str
    address_city: str
    address_postal_code: str
    address_country: str = "DE"
    preferred_language: str = "de"
    preferred_communication_channel: str = "email"
    customer_since: date


class InsurantResponse(BaseModel):
    """Schema for insurant response."""
    insurant_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    email: str
    phone: str
    address_street: str
    address_city: str
    address_postal_code: str
    address_country: str
    preferred_language: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class PolicyCreate(BaseModel):
    """Schema for creating a new policy."""
    policy_number: str
    insurant_id: str
    product_name: str
    tariff_version: str
    effective_date: date
    renewal_date: date
    annual_premium: float
    license_plate: str
    vin: str
    vehicle_make: str
    vehicle_model: str
    first_registration: date
    engine_power_kw: int
    fuel_type: str
    vehicle_value: float
    current_sum_insured: float
    use_type: str = VehicleUseType.PRIVATE.value
    annual_mileage: int
    has_vollkasko: bool = False
    has_teilkasko: bool = False


class PolicyResponse(BaseModel):
    """Schema for policy response."""
    policy_id: str
    policy_number: str
    insurant_id: str
    product_name: str
    license_plate: str
    vehicle_make: str
    vehicle_model: str
    status: str
    effective_date: date
    renewal_date: date
    has_vollkasko: bool
    has_teilkasko: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class VerificationRequest(BaseModel):
    """Schema for policy verification request."""
    policy_number: Optional[str] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    caller_name: str
    caller_phone: str
    date_of_birth: Optional[date] = None


class VerificationResponse(BaseModel):
    """Schema for verification response."""
    verified: bool
    policy: Optional[PolicyResponse] = None
    insurant: Optional[InsurantResponse] = None
    message: str
    coverage_active: bool = False
    can_file_claim: bool = False