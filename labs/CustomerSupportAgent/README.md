# Customer Support Email Agent (Enterprise)

LangGraph customer-support email agent with enterprise guardrails, SLA-aware routing, secret redaction, compliance checks, and optional human-in-the-loop review.

## Capabilities

1. Inbound email validation + secret redaction  
2. Intent/urgency/sentiment classification with SLA targets  
3. Knowledge-base / web doc search for product questions  
4. Bug ticket creation for defect reports  
5. Policy-aware response drafting  
6. Human review gate for billing / complex / critical cases  
7. Outbound compliance scan before send  

## Setup

```bash
cd labs/CustomerSupportAgent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source ../.env.azure
export LLM_PROVIDER=azure
```

## Run

Non-interactive demo:
```bash
./venv/bin/python demo.py
```

Interactive:
```bash
./venv/bin/python main.py
```

Enable real HITL interrupts:
```bash
export ENABLE_HITL=true
./venv/bin/python main.py
```

## Architecture

`read_email → classify_intent → (doc_search | bug_tracking | draft_response | human_review) → draft_response → human_review → send_reply`

## Project layout

```
CustomerSupportAgent/
├── main.py
├── demo.py
├── graph.py
├── nodes.py
├── state.py
└── utils/
    ├── constants.py
    ├── llm.py
    ├── guardrails.py
    ├── policies.py
    ├── observability.py
    └── resilience.py
```
