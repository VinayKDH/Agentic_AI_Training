# Day 3 - Medium: Enterprise FastAPI Agent Service

Deploy a LangGraph agent as a FastAPI service with Azure OpenAI support, input guardrails, retries, and compliance metadata.

## Setup

```bash
cd labs/Day3_Medium
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source ../.env.azure
export LLM_PROVIDER=azure
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Test

```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?", "stream": false}'
```

## Enterprise notes

- Default provider is Azure (`LLM_PROVIDER=azure`)
- Guardrails block empty/oversized/injection/secret-bearing prompts
- Response metadata includes `run_id`, model label, and compliance verdict
