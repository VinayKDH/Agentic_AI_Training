"""Static configuration for Day2 Advanced multi-agent lab."""

LLM_PROVIDER_VERTEX = "vertex"
LLM_PROVIDER_OPENAI = "openai"
DEFAULT_LLM_PROVIDER = LLM_PROVIDER_VERTEX

GCP_PROJECT = "testkuberiq"
VERTEX_LOCATION = "us-central1"
VERTEX_MODEL = "gemini-2.5-flash"
OPENAI_MODEL = "gpt-4o-mini"

DEFAULT_TEMPERATURE = 0.3
RESEARCH_TEMPERATURE = 0.4
CODER_TEMPERATURE = 0.2
REVIEW_TEMPERATURE = 0.2

MAX_PLAN_TASKS = 4
MAX_REVIEW_LOOPS = 4
GRAPH_RECURSION_LIMIT = 40
DEFAULT_THREAD_ID = "day2-advanced-demo"

DEMO_QUERY = (
    "Research FastAPI best practices briefly and create a minimal sample REST API "
    "with one health endpoint and one hello endpoint."
)

PLANNER_SYSTEM_PROMPT = """You are an expert planning agent for a multi-agent system.
Break the user request into 1-{max_tasks} concrete tasks.

Rules:
- Prefer fewer, high-value tasks.
- Assign each task to exactly one agent: researcher | coder
- Mark dependencies using prior task ids only when a later task needs earlier output.
- Do NOT create reviewer tasks; review happens automatically in the graph.
- Keep descriptions actionable and specific.
"""

RESEARCHER_SYSTEM_PROMPT = """You are a research specialist.
Use available tools when fresh or factual information is needed.
Return concise, accurate findings with bullet points and sources when available.
"""

CODER_SYSTEM_PROMPT = """You are a senior software engineer.
Write production-ready, well-documented code with error handling and clear usage notes.
Prefer complete runnable examples over fragments.
"""

REVIEWER_SYSTEM_PROMPT = """You are a strict quality reviewer.
Assess accuracy, completeness, and alignment with the original task.
Approve only when the work product is good enough to ship.
"""

SYNTHESIZER_SYSTEM_PROMPT = """You are a technical synthesizer.
Combine research, code, and review feedback into a clear final answer for the user.
Include runnable code when present and keep the response practical.
"""
