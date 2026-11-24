# Day 3 - Advanced: Enterprise Agentic API

Production-style FastAPI service with JWT auth, metrics, caching hooks, and enterprise LLM gates.

## Enterprise additions

- Azure OpenAI / OpenAI provider factory (`LLM_PROVIDER=azure` default)
- Input guardrails (injection markers, secrets, length)
- Output secret scanning
- Multi-node LangGraph flow: guardrails → agent → compliance
- Audit trail + compliance verdict in response metadata
- Redis optional for local demos (`REDIS_ENABLED=false` by default)

## Setup

```bash
cd labs/Day3_Advanced
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source ../.env.azure
export LLM_PROVIDER=azure
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

- API: http://localhost:8001
- Docs: http://localhost:8001/docs
- Health: http://localhost:8001/health

## Auth

```bash
curl -X POST http://localhost:8001/api/v1/login \
  -d "username=admin&password=admin123"
```

## Query

```bash
TOKEN=... # from login
curl -X POST http://localhost:8001/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize FastAPI health-check best practices"}'
```
