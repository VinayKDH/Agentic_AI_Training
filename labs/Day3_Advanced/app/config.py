from pydantic_settings import BaseSettings
from typing import Optional

from app import constants as C


class Settings(BaseSettings):
    """Application settings."""

    API_TITLE: str = C.API_TITLE
    API_VERSION: str = C.API_VERSION
    API_PREFIX: str = C.API_PREFIX
    DEBUG: bool = False

    HOST: str = C.DEFAULT_HOST
    PORT: int = C.DEFAULT_PORT
    WORKERS: int = C.DEFAULT_WORKERS

    LLM_PROVIDER: str = C.DEFAULT_LLM_PROVIDER
    GCP_PROJECT: str = C.GCP_PROJECT_DEFAULT
    VERTEX_LOCATION: str = C.VERTEX_LOCATION_DEFAULT
    VERTEX_MODEL: str = C.VERTEX_MODEL_DEFAULT

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = C.OPENAI_MODEL_DEFAULT
    OPENAI_TEMPERATURE: float = C.DEFAULT_TEMPERATURE
    OPENAI_MAX_TOKENS: int = C.DEFAULT_MAX_TOKENS

    REDIS_HOST: str = C.REDIS_HOST_DEFAULT
    REDIS_PORT: int = C.REDIS_PORT_DEFAULT
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_ENABLED: bool = False

    SECRET_KEY: str = C.DEFAULT_SECRET_KEY
    ALGORITHM: str = C.JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = C.ACCESS_TOKEN_EXPIRE_MINUTES

    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = C.RATE_LIMIT_REQUESTS
    RATE_LIMIT_WINDOW: int = C.RATE_LIMIT_WINDOW_SECONDS

    CACHE_ENABLED: bool = False
    CACHE_TTL: int = C.CACHE_TTL_SECONDS

    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = False
    LOG_LEVEL: str = C.DEFAULT_LOG_LEVEL

    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = C.LANGCHAIN_PROJECT_DEFAULT

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
