"""Static enterprise configuration for Customer Support Email Agent."""

LLM_PROVIDER_AZURE = "azure"
LLM_PROVIDER_OPENAI = "openai"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_AZURE

OPENAI_MODEL = "gpt-4o-mini"
AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4.1-mini"

DEFAULT_TEMPERATURE = 0.2
CLASSIFY_TEMPERATURE = 0.1
DRAFT_TEMPERATURE = 0.3

LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECONDS = 0.8
LLM_RETRY_MAX_DELAY_SECONDS = 8.0
MAX_EMAIL_LENGTH = 12000
GRAPH_RECURSION_LIMIT = 40
DEFAULT_THREAD_PREFIX = "support-email"

SECRET_PATTERNS = (
    r"(?i)(api[_-]?key|secret|password|token|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)sk-[a-zA-Z0-9]{20,}",
    r"(?i)AIza[0-9A-Za-z\-_]{20,}",
    r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(?i)\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
)

PII_PATTERNS = (
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)

SLA_TARGETS_HOURS = {
    "critical": 1,
    "high": 4,
    "medium": 24,
    "low": 48,
}

SUPPORT_POLICY_CHECKLIST = (
    "No secrets, payment card numbers, or passwords in replies",
    "Empathetic, professional tone matching urgency",
    "Cite documentation when answering product questions",
    "Include ticket IDs for bugs",
    "Escalate billing/security/complex issues to human review",
    "Do not invent account balances, refunds, or policy exceptions",
)

KNOWLEDGE_BASE = {
    "password reset": (
        "To reset your password, go to Settings > Security > Reset Password. "
        "You'll receive an email with reset instructions."
    ),
    "export feature": (
        "The export feature supports PDF, CSV, and Excel formats. "
        "Click the Export button in the top menu."
    ),
    "billing": (
        "You can view billing in Settings > Billing. "
        "For disputed charges, escalate to billing operations with the invoice ID."
    ),
    "api": (
        "API docs: https://api.example.com/docs. "
        "Generate API keys in Settings > API. Never share keys in email."
    ),
}

CLASSIFIER_SYSTEM_PROMPT = """You are an enterprise customer-support email classifier.
Classify into intent: question | bug | billing | feature | complex
Urgency: low | medium | high | critical

Rules:
- Billing disputes and payment failures are at least high urgency.
- Production outages / security concerns are critical.
- Ambiguous technical root-cause issues are complex.
- Provide a concise topic and summary suitable for ticket systems.
"""

DRAFT_SYSTEM_PROMPT = """You are an enterprise customer support specialist.
Draft a professional, empathetic email reply.

Requirements:
- Address the customer concern directly
- Use documentation context when available
- Reference bug ticket IDs when present
- Never invent refunds, credits, or account data
- Never include secrets or ask for passwords/full card numbers
- Match urgency in tone; keep concise and actionable
- Include clear next steps and SLA expectation when useful
"""
