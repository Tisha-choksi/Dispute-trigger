from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DisputeCreate(BaseModel):
    chain_dispute_id: Optional[int] = None
    chain_escrow_id: Optional[int] = None
    claimant: str
    respondent: str
    amount: Decimal
    contract_address: Optional[str] = None


class DisputeUpdate(BaseModel):
    state: Optional[str] = None
    evidence_ipfs_hashes: Optional[str] = None
    summary_text: Optional[str] = None
    recommendation_text: Optional[str] = None
    arbiter_decision: Optional[str] = None
    resolver_address: Optional[str] = None


class DisputeResponse(BaseModel):
    id: UUID
    chain_dispute_id: Optional[int]
    chain_escrow_id: Optional[int]
    claimant: str
    respondent: str
    amount: Decimal
    state: str
    evidence_ipfs_hashes: str
    summary_text: Optional[str]
    recommendation_text: Optional[str]
    arbiter_decision: Optional[str]
    contract_address: Optional[str]
    resolver_address: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class DisputeListResponse(BaseModel):
    items: list[DisputeResponse]
    total: int
    page: int
    page_size: int
