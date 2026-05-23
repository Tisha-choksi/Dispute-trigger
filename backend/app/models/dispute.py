import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DisputeState(str, enum.Enum):
    OPEN = "Open"
    UNDER_REVIEW = "UnderReview"
    RESOLVED = "Resolved"


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_dispute_id = Column(Integer, unique=True, nullable=True)
    chain_escrow_id = Column(Integer, nullable=True)

    claimant = Column(String(42), nullable=False)
    respondent = Column(String(42), nullable=False)
    amount = Column(Numeric(32, 18), nullable=False)

    state = Column(Enum(DisputeState), default=DisputeState.OPEN, nullable=False)

    evidence_ipfs_hashes = Column(Text, default="")
    summary_text = Column(Text, nullable=True)
    recommendation_text = Column(Text, nullable=True)
    arbiter_decision = Column(Text, nullable=True)

    contract_address = Column(String(42), nullable=True)
    resolver_address = Column(String(42), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
