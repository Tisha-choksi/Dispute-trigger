from sqlalchemy.orm import Session

from app.models.dispute import Dispute, DisputeState


class DisputeService:
    def __init__(self, db: Session):
        self.db = db

    def advance_state(self, dispute_id: int) -> Dispute:
        dispute = self.db.query(Dispute).filter(
            Dispute.chain_dispute_id == dispute_id
        ).first()

        if not dispute:
            raise ValueError(f"Dispute {dispute_id} not found")

        current = dispute.state

        if current == DisputeState.OPEN:
            dispute.state = DisputeState.UNDER_REVIEW
        elif current == DisputeState.UNDER_REVIEW:
            dispute.state = DisputeState.RESOLVED

        self.db.commit()
        self.db.refresh(dispute)
        return dispute

    def get_open_disputes(self):
        return (
            self.db.query(Dispute)
            .filter(Dispute.state == DisputeState.OPEN)
            .order_by(Dispute.created_at.asc())
            .all()
        )

    def get_stats(self):
        total = self.db.query(Dispute).count()
        resolved = (
            self.db.query(Dispute)
            .filter(Dispute.state == DisputeState.RESOLVED)
            .count()
        )
        open_count = (
            self.db.query(Dispute)
            .filter(Dispute.state == DisputeState.OPEN)
            .count()
        )
        review = (
            self.db.query(Dispute)
            .filter(Dispute.state == DisputeState.UNDER_REVIEW)
            .count()
        )

        return {
            "total": total,
            "open": open_count,
            "under_review": review,
            "resolved": resolved,
        }
