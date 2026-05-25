from celery import Celery

from app.config import settings

celery_app = Celery(
    "dispute_triage",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_routes = {
    "summarize_dispute": {"queue": "nlp"},
    "classify_evidence": {"queue": "nlp"},
    "generate_recommendation": {"queue": "nlp"},
}


@celery_app.task
def summarize_dispute(dispute_id: int):
    return {"dispute_id": dispute_id, "status": "pending"}


@celery_app.task
def classify_evidence(evidence_id: int):
    return {"evidence_id": evidence_id, "status": "pending"}


@celery_app.task
def generate_recommendation(dispute_id: int):
    return {"dispute_id": dispute_id, "status": "pending"}
