# Day 2 - Advanced Lab: Enterprise Multi-Agent System (LangGraph + LangChain)

Production-style multi-agent workflow with enterprise guardrails, policy gates, retries, and auditability.

## What this lab demonstrates

- **StateGraph orchestration** with typed state + reducers
- **Command-based routing** with dependency-aware dispatch
- **Tool-calling researcher** via `langchain.agents.create_agent`
- **Structured outputs** for planner, coder, and reviewer (risk, priority, acceptance criteria)
- **Autonomy governance (L0–L4)**: plan gates, review escalation, final-release rights, audit
- **Enterprise gates**: input validation, secret scanning, policy checklist, quality scoring
- **Resilience**: exponential backoff retries for transient LLM/tool failures
- **Observability**: run IDs, node timings, audit trail, compliance verdict
- **Checkpointing** with `MemorySaver`
- **Human-in-the-loop** via `interrupt()` / `Command(resume=...)`
- **Streaming** node updates for demos

### Autonomy levels

| Level | Name | Behavior |
|------|------|----------|
| L0 | Supervised | Approve plan + every review + final release |
| L1 | Assisted | Approve plan + final release; escalate on reject |
| L2 | Conditional | Auto within risk ceiling; escalate on reject/policy/high risk |
| L3 | High | Escalate only for critical risk / hard policy / severe miss |
| L4 | Full | No human gates; hard guardrails + audit remain |

## Agents

1. **Planner** – enterprise plan with acceptance criteria, risk, priority
2. **Researcher** – tool-using research with sources and risk callouts
3. **Coder** – secure, runnable code with usage + security notes
4. **Reviewer** – policy-aware approve/revise (+ optional HITL)
5. **Synthesizer** – executive-ready final delivery summary

## Setup

```bash
cd labs/Day2_Advanced
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### LLM providers

**Option A — Azure OpenAI (default)**
```bash
export LLM_PROVIDER=azure
# or: source ../.env.azure
```

**Option B — Vertex AI**
```bash
export LLM_PROVIDER=vertex
export GCP_PROJECT=testkuberiq
export VERTEX_LOCATION=us-central1
export VERTEX_MODEL=gemini-2.5-flash
```

**Option C — OpenAI**
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

## Run

### Web UI (recommended)

```bash
source venv/bin/activate
source ../.env.azure
export LLM_PROVIDER=azure
pip install -r requirements.txt
python run_ui.py
```

Open [http://127.0.0.1:7860](http://127.0.0.1:7860)

Select a lab (Day 2 Advanced, Day 3 Medium/Advanced, or Customer Support), click **Run**, and stream live updates plus the enterprise run report. HITL is available for Day 2 and Customer Support.

### CLI

Interactive:
```bash
python main.py
```

One-shot demo:
```bash
./venv/bin/python demo.py "Create a minimal FastAPI hello endpoint"
```

Disable HITL:
```bash
export ENABLE_HITL=false
python main.py
```

## Project structure

```
Day2_Advanced/
├── run_ui.py                   # Launch Agent Desk web UI
├── main.py
├── demo.py
├── state.py
├── ui/
│   ├── app.py                  # FastAPI + SSE
│   ├── service.py
│   └── static/                 # Console frontend
├── agents/
├── graph/
├── tools/
└── utils/
```

## Suggested prompts

- `Create a minimal FastAPI hello endpoint`
- `Research LangGraph Command routing and show a tiny example`
- `Write a Python function for Fibonacci with tests`
