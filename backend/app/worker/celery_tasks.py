import logging

from celery import Celery

from app.config import settings
from app.services.evidence_classifier import EvidenceClassifier
from app.services.summarization_service import SummarizationService

logger = logging.getLogger(__name__)

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
def summarize_dispute(dispute_id: int, chat_log: str):
    service = SummarizationService(openai_api_key=settings.openai_api_key)
    summary = service.summarize(chat_log)
    logger.info("Summarized dispute %s: %s", dispute_id, summary.get("summary_paragraph", "")[:80])
    return {"dispute_id": dispute_id, "summary": summary, "status": "completed"}


@celery_app.task
def classify_evidence(evidence_id: int, text: str, evidence_type: str = "general"):
    classifier = EvidenceClassifier()
    result = classifier.classify(text, evidence_type=evidence_type)
    logger.info("Classified evidence %s: %s", evidence_id, result)
    return {"evidence_id": evidence_id, "classification": result, "status": "completed"}


@celery_app.task
def generate_recommendation(dispute_id: int):
    return {"dispute_id": dispute_id, "status": "pending"}
