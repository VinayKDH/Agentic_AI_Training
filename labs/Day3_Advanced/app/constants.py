"""Static enterprise configuration for Day3 Advanced API."""

LLM_PROVIDER_AZURE = "azure"
LLM_PROVIDER_OPENAI = "openai"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_AZURE

OPENAI_MODEL = "gpt-4o-mini"
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4.1-mini"

DEFAULT_TEMPERATURE = 0.2
MAX_QUERY_LENGTH = 4000
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECONDS = 0.8
LLM_RETRY_MAX_DELAY_SECONDS = 8.0

SECRET_PATTERNS = (
    r"(?i)(api[_-]?key|secret|password|token|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)sk-[a-zA-Z0-9]{20,}",
    r"(?i)AIza[0-9A-Za-z\-_]{20,}",
    r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
)

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all prior",
    "disregard system prompt",
    "jailbreak",
    "reveal your system prompt",
)

ENTERPRISE_POLICY_CHECKLIST = (
    "Do not invent facts or credentials",
    "Do not expose secrets or personal data",
    "Be explicit about assumptions and residual risk",
    "Prefer actionable, auditable guidance",
)

AGENT_SYSTEM_PROMPT = """You are an enterprise-grade AI assistant serving a production API.
Follow these rules:
- Be accurate, concise, and operationally useful.
- Never invent credentials, account numbers, or private data.
- Call out assumptions and residual risks briefly.
- If the request is unsafe or out of policy, refuse and explain why.
- Structure answers for engineer/operator consumption when technical.
"""

COMPLIANCE_SYSTEM_PROMPT = """You are a compliance gate for enterprise API responses.
Return a short verdict: pass, conditional, or fail.
Fail only for secrets, unsafe instructions, or clear policy breaches.
"""
