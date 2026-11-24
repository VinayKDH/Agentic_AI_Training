from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

from dotenv import load_dotenv

from app.constants import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_TEMPERATURE,
    OPENAI_MODEL,
)

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT.parent / ".env.azure", override=False)
os.environ.setdefault("LLM_PROVIDER", DEFAULT_LLM_PROVIDER)


class Settings(BaseSettings):
    """Application settings"""

    API_TITLE: str = "Enterprise Agentic AI API"
    API_VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8001
    WORKERS: int = 1

    LLM_PROVIDER: str = DEFAULT_LLM_PROVIDER
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = OPENAI_MODEL
    OPENAI_TEMPERATURE: float = DEFAULT_TEMPERATURE
    OPENAI_MAX_TOKENS: int = 2000

    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: str = AZURE_OPENAI_DEPLOYMENT
    AZURE_OPENAI_API_VERSION: str = AZURE_OPENAI_API_VERSION

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_ENABLED: bool = False

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    CACHE_ENABLED: bool = False
    CACHE_TTL: int = 3600

    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = False
    LOG_LEVEL: str = "INFO"

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "day3-advanced-enterprise"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
