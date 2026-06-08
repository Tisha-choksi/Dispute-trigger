from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/dispute_triage"
    redis_url: str = "redis://localhost:6379/0"
    rpc_url: str = "http://127.0.0.1:8545"
    contract_address: str = ""
    cors_origins: str = "http://localhost:5173"
    evidence_threshold: int = 2
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    nlp_model_path: str = "backend/app/models"

    class Config:
        env_file = ".env"


settings = Settings()
