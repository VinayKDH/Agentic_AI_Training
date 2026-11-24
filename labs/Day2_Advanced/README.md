# Day 2 - Advanced Lab: Modern Multi-Agent System (LangGraph + LangChain)

Build a production-style multi-agent workflow with the **latest LangChain/LangGraph** capabilities.

## What this lab demonstrates

- **StateGraph orchestration** with typed state + reducers
- **Command-based routing** (update state + choose next node)
- **Tool-calling researcher** via `langchain.agents.create_agent`
- **Structured outputs** for planner, coder, and reviewer
- **Checkpointing** with `MemorySaver`
- **Human-in-the-loop** via `interrupt()` / `Command(resume=...)`
- **Streaming** node updates for demos

## Agents

1. **Planner** – breaks the query into researcher/coder tasks
2. **Researcher** – tool-using research agent (`web_search`)
3. **Coder** – generates structured code artifacts
4. **Reviewer** – structured approve/revise decisions (+ optional HITL)
5. **Synthesizer** – final answer assembly

## Setup

```bash
cd labs/Day2_Advanced
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### LLM providers

**Option A — Vertex AI (default)**
```bash
export LLM_PROVIDER=vertex
export GCP_PROJECT=testkuberiq
export VERTEX_LOCATION=us-central1
export VERTEX_MODEL=gemini-2.5-flash
# Ensure gcloud auth is available
gcloud auth login
gcloud auth application-default login   # optional but recommended
```

**Option B — OpenAI**
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
```

## Run

Interactive (enter your own prompts, supports HITL):
```bash
unset GOOGLE_APPLICATION_CREDENTIALS   # if pointing to a missing file
python main.py
```

One-shot demo with streaming (HITL off):
```bash
python demo.py "Create a minimal FastAPI hello endpoint"
```

Disable human review interrupts:
```bash
export ENABLE_HITL=false
python main.py
```

## Project structure

```
Day2_Advanced/
├── main.py                     # Interactive runner + HITL resume
├── demo.py                     # Non-interactive streaming demo
├── state.py                    # Typed state + reducers
├── agents/
│   ├── planner.py
│   ├── researcher.py
│   ├── coder.py
│   └── reviewer.py
├── graph/
│   └── multi_agent_graph.py    # Command routing + interrupt
├── tools/
│   └── web_search.py
└── utils/
    ├── constants.py
    ├── llm.py
    └── routing.py
```

## Suggested demo prompts

- `Create a minimal FastAPI hello endpoint`
- `Research LangGraph Command routing and show a tiny example`
- `Write a Python function for Fibonacci with tests`

## Notes

- Needs a valid LLM backend (Vertex or OpenAI). `git pull` alone is not enough.
- If review rejects work and HITL is enabled, the graph pauses for your decision.
