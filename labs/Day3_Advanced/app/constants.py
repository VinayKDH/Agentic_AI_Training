"""Static configuration values for Day3 Advanced agent API."""

API_TITLE = "Agentic AI API"
API_VERSION = "1.0.0"
API_PREFIX = "/api/v1"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_WORKERS = 1

LLM_PROVIDER_VERTEX = "vertex"
LLM_PROVIDER_OPENAI = "openai"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_VERTEX

GCP_PROJECT_DEFAULT = "testkuberiq"
VERTEX_LOCATION_DEFAULT = "us-central1"
VERTEX_MODEL_DEFAULT = "gemini-2.5-flash"

OPENAI_MODEL_DEFAULT = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

REDIS_HOST_DEFAULT = "localhost"
REDIS_PORT_DEFAULT = 6379
CACHE_TTL_SECONDS = 3600
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60

LANGCHAIN_PROJECT_DEFAULT = "agentic-ai-production"
DEFAULT_LOG_LEVEL = "INFO"

AGENT_PROMPT_TEMPLATE = (
    "You are a helpful production agentic AI assistant. "
    "User asked: {user_message}. Provide a clear, concise response."
)

DEMO_USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
}
