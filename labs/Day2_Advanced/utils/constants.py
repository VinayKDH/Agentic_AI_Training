"""Static configuration for Day2 Advanced enterprise multi-agent lab."""

LLM_PROVIDER_VERTEX = "vertex"
LLM_PROVIDER_OPENAI = "openai"
LLM_PROVIDER_AZURE = "azure"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_AZURE

GCP_PROJECT = "testkuberiq"
VERTEX_LOCATION = "us-central1"
VERTEX_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o-mini"

AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4.1-mini"

DEFAULT_TEMPERATURE = 0.2
RESEARCH_TEMPERATURE = 0.3
CODER_TEMPERATURE = 0.1
REVIEW_TEMPERATURE = 0.1
PLANNER_TEMPERATURE = 0.1

MAX_PLAN_TASKS = 4
MAX_REVIEW_LOOPS = 4
GRAPH_RECURSION_LIMIT = 40
DEFAULT_THREAD_ID = "day2-advanced-demo"

# Enterprise UI console
UI_HOST = "127.0.0.1"
UI_PORT = 7860
UI_TITLE = "Agent Desk"
UI_SUBTITLE = "Select a training lab and run enterprise agent workflows"
UI_FLOW_STEPS = (
    "planner",
    "dispatch",
    "researcher",
    "coder",
    "reviewer",
    "synthesizer",
)
UI_EXAMPLE_PROMPTS = (
    "Create a minimal FastAPI hello endpoint with a health check",
    "Research LangGraph Command routing and show a tiny Python example",
    "Write a Python Fibonacci function with unit tests",
)
UI_DEFAULT_LAB_ID = "day2_advanced"
UI_LABS = (
    {
        "id": "day2_advanced",
        "name": "Day 2 Advanced",
        "description": "Multi-agent planner → research/code → review → synthesize",
        "supports_hitl": True,
        "input_label": "What should the agents deliver?",
        "run_label": "Run Day 2 agents",
        "flow": [
            "planner",
            "dispatch",
            "researcher",
            "coder",
            "reviewer",
            "synthesizer",
        ],
        "examples": [
            "Create a minimal FastAPI hello endpoint with a health check",
            "Research LangGraph Command routing and show a tiny Python example",
            "Write a Python Fibonacci function with unit tests",
        ],
    },
    {
        "id": "day3_medium",
        "name": "Day 3 Medium",
        "description": "FastAPI agent service with enterprise guardrails",
        "supports_hitl": False,
        "input_label": "API query for the Day 3 Medium agent",
        "run_label": "Run Day 3 Medium",
        "flow": ["guardrails", "agent", "response"],
        "examples": [
            "What is machine learning in one paragraph?",
            "Explain rate limiting for APIs",
            "Summarize FastAPI health-check best practices",
        ],
    },
    {
        "id": "day3_advanced",
        "name": "Day 3 Advanced",
        "description": "Production API agent with compliance gate + audit trail",
        "supports_hitl": False,
        "input_label": "API query for the Day 3 Advanced agent",
        "run_label": "Run Day 3 Advanced",
        "flow": ["guardrails", "agent", "compliance_gate"],
        "examples": [
            "Summarize FastAPI health-check best practices",
            "How should an enterprise API handle retries?",
            "Draft a short incident status update for a 15-minute outage",
        ],
    },
    {
        "id": "customer_support",
        "name": "Customer Support Agent",
        "description": "Email support: classify → search/ticket → draft → review → send",
        "supports_hitl": True,
        "input_label": "Customer email content",
        "run_label": "Run support agent",
        "flow": [
            "read_email",
            "classify_intent",
            "doc_search",
            "bug_tracking",
            "draft_response",
            "human_review",
            "send_reply",
        ],
        "examples": [
            "How do I reset my password? I can't remember it.",
            "The export feature crashes when I select PDF format.",
            "I was charged twice for my subscription! Please fix this immediately.",
        ],
    },
)

# Enterprise resilience
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY_SECONDS = 0.8
LLM_RETRY_MAX_DELAY_SECONDS = 8.0
AGENT_TIMEOUT_SECONDS = 120

# Enterprise quality gates
MIN_REVIEW_SCORE = 7
MIN_APPROVAL_SCORE = 8
REQUIRE_SOURCES_FOR_RESEARCH = True
REQUIRE_USAGE_NOTES_FOR_CODE = True
BLOCK_ON_SECRET_FINDINGS = True
MAX_QUERY_LENGTH = 4000
MAX_WORK_PRODUCT_CHARS = 24000

# Enterprise risk / priority labels
RISK_LEVELS = ("low", "medium", "high", "critical")
PRIORITY_LEVELS = ("p0", "p1", "p2", "p3")

DEMO_QUERY = (
    "Research FastAPI best practices briefly and create a minimal sample REST API "
    "with one health endpoint and one hello endpoint."
)

ENTERPRISE_POLICY_CHECKLIST = (
    "Security: no hardcoded secrets, unsafe eval, or obvious injection risks",
    "Reliability: errors handled; inputs validated; failures are explicit",
    "Maintainability: clear structure, naming, and short usage notes",
    "Compliance: no PII leakage; cite sources for factual claims",
    "Operability: include run/test steps where code is produced",
)

SECRET_PATTERNS = (
    r"(?i)(api[_-]?key|secret|password|token|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    r"(?i)sk-[a-zA-Z0-9]{20,}",
    r"(?i)AIza[0-9A-Za-z\-_]{20,}",
    r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*",
)

PII_PATTERNS = (
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b",
)

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all prior",
    "disregard system prompt",
    "you are now",
    "jailbreak",
    "reveal your system prompt",
)

PLANNER_SYSTEM_PROMPT = """You are an enterprise planning agent for a regulated multi-agent delivery system.
Break the user request into 1-{max_tasks} concrete, auditable tasks.

Enterprise rules:
- Prefer fewer, high-value tasks with clear acceptance criteria.
- Assign each task to exactly one agent: researcher | coder
- For implementation requests, include both research (when facts/APIs matter) and coder work.
- Mark dependencies using prior task ids/labels only when a later task needs earlier output.
- Do NOT create reviewer tasks; review/quality gates run automatically.
- Tag each task with risk_level (low|medium|high|critical) and priority (p0|p1|p2|p3).
- Keep descriptions actionable, testable, and scoped for enterprise delivery.
- Never ask for or embed secrets, credentials, or personal data.
"""

RESEARCHER_SYSTEM_PROMPT = """You are an enterprise research specialist.
Produce decision-ready findings suitable for architecture and engineering review.

Requirements:
- Use tools when freshness, citations, or external facts are needed.
- Separate facts from assumptions.
- Prefer primary/official sources; list URLs when available.
- Call out risks, constraints, and alternatives briefly.
- Never invent citations; if unknown, say so.
- Do not include secrets, credentials, or personal data.
"""

CODER_SYSTEM_PROMPT = """You are a senior enterprise software engineer.
Deliver production-minded, secure, maintainable code.

Requirements:
- Prefer complete runnable examples over fragments.
- Include input validation, explicit error handling, and logging hooks where useful.
- Avoid hardcoded secrets, eval/exec on untrusted input, and unsafe defaults.
- Document assumptions, dependencies, and how to run/test.
- Keep the solution scoped to the task; do not over-engineer.
- Follow enterprise checklist: security, reliability, maintainability, operability.
"""

REVIEWER_SYSTEM_PROMPT = """You are a strict enterprise quality and compliance reviewer.
Approve only work that is safe, complete, and ready for handoff.

Evaluate against:
1) Correctness and completeness vs the original task
2) Security (secrets, injection, unsafe patterns)
3) Reliability (error handling, validation)
4) Maintainability and clarity
5) Source quality for research; run/test notes for code
6) Policy checklist items provided in context

Scoring guidance:
- 9-10: ship-ready with minor or no nits
- 7-8: acceptable with documented residual risk
- <=6: must revise

Reject when secrets are present, claims are uncited where required, or acceptance criteria are unmet.
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are an enterprise delivery synthesizer.
Produce a clear executive-ready final answer for engineers and reviewers.

Structure:
1) Summary (what was delivered)
2) Solution / findings (include runnable code when present)
3) Risks & residual items
4) How to validate (run/test steps)
5) Sources (when research was used)

Be precise, practical, and avoid fluff. Do not invent facts or hide review failures.
"""

COMPLIANCE_GATE_SYSTEM_PROMPT = """You are an enterprise compliance gate.
Given the run artifacts and policy checklist, return a concise compliance verdict.
Flag blocking issues only for real policy failures (secrets, unsafe code, missing required usage notes for code, fabricated certainty).
"""
