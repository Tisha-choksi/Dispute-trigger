from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dispute import Dispute, DisputeState
from app.schemas.dispute import (
    DisputeCreate,
    DisputeListResponse,
    DisputeResponse,
    DisputeUpdate,
)

router = APIRouter(prefix="/disputes", tags=["disputes"])


@router.get("", response_model=DisputeListResponse)
def list_disputes(
    state: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Dispute)

    if state:
        query = query.filter(Dispute.state == state)

    total = query.count()
    items = (
        query.order_by(Dispute.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return DisputeListResponse(
        items=[DisputeResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{dispute_id}", response_model=DisputeResponse)
def get_dispute(dispute_id: UUID, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return dispute


@router.post("", response_model=DisputeResponse, status_code=201)
def create_dispute(body: DisputeCreate, db: Session = Depends(get_db)):
    dispute = Dispute(**body.model_dump())
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.patch("/{dispute_id}", response_model=DisputeResponse)
def update_dispute(dispute_id: UUID, body: DisputeUpdate, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(dispute, field, value)

    db.commit()
    db.refresh(dispute)
    return dispute


@router.delete("/{dispute_id}", status_code=204)
def delete_dispute(dispute_id: UUID, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    db.delete(dispute)
    db.commit()
