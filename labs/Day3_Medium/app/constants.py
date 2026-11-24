"""Static enterprise configuration for Day3 Medium API."""

LLM_PROVIDER_AZURE = "azure"
LLM_PROVIDER_OPENAI = "openai"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_AZURE

OPENAI_MODEL = "gpt-4o-mini"
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 0.2
MAX_QUERY_LENGTH = 4000
LLM_MAX_RETRIES = 3

SECRET_PATTERNS = (
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)sk-[a-zA-Z0-9]{20,}",
)

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "jailbreak",
    "reveal your system prompt",
)

AGENT_SYSTEM_PROMPT = """You are an enterprise API assistant.
Be accurate, concise, and safe. Never invent secrets or private data.
Call out assumptions briefly and refuse unsafe requests.
"""
