from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import logging

class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    MODEL_NAME: str = "llama-3.1-8b-instant"  # default specialist model
    SUPERVISOR_MODEL: str = "llama-3.3-70b-versatile"  # supervisor/reviewer model
    MAX_RETRIES_PER_SUBTASK: int = 2
    SEARCH_TIMEOUT_SECONDS: int = 15
    REDIS_URL: str = "redis://localhost:6379/0"
    CHROMADB_PATH: str = "./chromadb_data"
    DATABASE_URL: str = "sqlite:///agent_orchestrator.db"
    POSTGRES_URL: str = "postgresql://agent:agent@localhost:5432/agent_db"
    LOG_LEVEL: str = "INFO"
    ESCALATION_CONFIDENCE_THRESHOLD: float = 0.4
    ESCALATION_SCORE_THRESHOLD: int = 2
    TASK_TTL_SECONDS: int = 86400
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Model pricing per token
MODEL_PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05 / 1_000_000, "output": 0.08 / 1_000_000},
    "llama-3.3-70b-versatile": {"input": 0.59 / 1_000_000, "output": 0.79 / 1_000_000},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return input_tokens * pricing["input"] + output_tokens * pricing["output"]

@lru_cache
def get_settings() -> Settings:
    return Settings()

def setup_logging(level: str = None) -> logging.Logger:
    settings = get_settings()
    log_level = level or settings.LOG_LEVEL
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    return logging.getLogger("agent_orchestrator")

logger = setup_logging()
