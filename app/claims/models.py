"""SQLAlchemy and Pydantic models for claims."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Text, Enum as SQLEnum, JSON
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
import enum

Base = declarative_base()


class ClaimCategory(str, enum.Enum):
    """Claim category enumeration."""
    
    PROPERTY_DAMAGE = "property_damage"
    VEHICLE_ACCIDENT = "vehicle_accident"
    PERSONAL_INJURY = "personal_injury"
    THEFT = "theft"
    LIABILITY = "liability"
    OTHER = "other"


class ClaimSeverity(str, enum.Enum):
    """Claim severity enumeration."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClaimStatus(str, enum.Enum):
    """Claim status enumeration."""
    
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


# SQLAlchemy Model
class Claim(Base):
    """Database model for insurance claims."""
    
    __tablename__ = "claims"
    
    # Primary key
    claim_id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Caller information
    caller_name = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=False)
    contact_email = Column(String(255), nullable=True)
    
    # Incident details
    problem_category = Column(SQLEnum(ClaimCategory), nullable=False)
    problem_description = Column(Text, nullable=False)
    incident_date = Column(DateTime, nullable=False)
    incident_location = Column(String(500), nullable=True)
    
    # Severity and status
    severity = Column(SQLEnum(ClaimSeverity), nullable=False)
    status = Column(SQLEnum(ClaimStatus), default=ClaimStatus.SUBMITTED, nullable=False)
    
    # Additional information
    estimated_damage = Column(String(100), nullable=True)
    
    # Session tracking
    session_id = Column(String(36), nullable=False)
    call_sid = Column(String(100), nullable=False)
    language = Column(String(10), nullable=False, default="en")
    
    # Transcript and metadata
    transcript = Column(JSON, nullable=True)
    claim_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<Claim(id={self.claim_id}, category={self.problem_category}, status={self.status})>"


# Pydantic Models for API
class ClaimCreate(BaseModel):
    """Schema for creating a new claim."""
    
    caller_name: str = Field(..., min_length=1, max_length=255)
    contact_phone: str = Field(..., min_length=1, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    problem_category: ClaimCategory
    problem_description: str = Field(..., min_length=10)
    incident_date: datetime
    incident_location: Optional[str] = Field(None, max_length=500)
    severity: ClaimSeverity
    estimated_damage: Optional[str] = Field(None, max_length=100)
    session_id: str
    call_sid: str
    language: str = "en"
    transcript: Optional[list] = None
    claim_metadata: Optional[dict] = None


class ClaimUpdate(BaseModel):
    """Schema for updating an existing claim."""
    
    caller_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_phone: Optional[str] = Field(None, min_length=1, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    problem_category: Optional[ClaimCategory] = None
    problem_description: Optional[str] = Field(None, min_length=10)
    incident_date: Optional[datetime] = None
    incident_location: Optional[str] = Field(None, max_length=500)
    severity: Optional[ClaimSeverity] = None
    status: Optional[ClaimStatus] = None
    estimated_damage: Optional[str] = Field(None, max_length=100)
    transcript: Optional[list] = None
    claim_metadata: Optional[dict] = None


class ClaimResponse(BaseModel):
    """Schema for claim response."""
    
    claim_id: str
    caller_name: str
    contact_phone: str
    contact_email: Optional[str]
    problem_category: ClaimCategory
    problem_description: str
    incident_date: datetime
    incident_location: Optional[str]
    severity: ClaimSeverity
    status: ClaimStatus
    estimated_damage: Optional[str]
    session_id: str
    call_sid: str
    language: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        """Pydantic config."""
        from_attributes = True