# Agentic AI Training - Lab Projects

This directory contains fully functional lab projects for the 3-day Agentic AI Training program.

## Lab Structure

### Day 1 Labs
- **Day1_Medium**: Basic conversational agent with LangChain
- **Day1_Advanced**: Multi-tool agent with RAG integration

### Day 2 Labs
- **Day2_Medium**: Multi-agent research system with LangGraph
- **Day2_Advanced**: Complex multi-agent system with state management

### Day 3 Labs
- **Day3_Medium**: Enterprise FastAPI agent service (Azure, guardrails)
- **Day3_Advanced**: Production API with auth/metrics + enterprise gates
- **CustomerSupportAgent**: Enterprise email support workflow (SLA, HITL, compliance)

## Credentials (for sharing with students)

This repo is shared **without Azure/OpenAI secrets**.

```bash
cd labs
cp .env.azure.example .env.azure   # students fill THEIR own keys
```

- Template: [`.env.azure.example`](.env.azure.example)
- Setup guide: [ENV_SETUP.md](ENV_SETUP.md) · [AZURE_AI_SETUP.md](AZURE_AI_SETUP.md)
- Never commit `.env`, `.env.azure`, or keys

## Quick Start

Each lab directory contains:
- Complete source code
- `requirements.txt` for dependencies
- `README.md` with setup instructions

### General Setup Steps

1. Add your LLM credentials (once):
```bash
cd labs
cp .env.azure.example .env.azure
# edit .env.azure with your Azure OpenAI or use OpenAI vars (see ENV_SETUP.md)
```

2. Navigate to a lab:
```bash
cd Day2_Advanced  # or any other lab
```

3. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Load credentials and run:
```bash
set -a; source ../.env.azure; set +a
export LLM_PROVIDER=azure
python main.py  # or follow lab-specific instructions
```

## Prerequisites

- Python 3.10+ (3.11 recommended)
- **Your own** Azure OpenAI or OpenAI API credentials
- (Optional) Redis / Docker for Day 3 Advanced

## Notes

- Each lab is self-contained and can be run independently
- Instructors: share the git repo or a zip that **excludes** `**/.env*`, `**/venv/`, and local credential files
- Some labs require additional services (Redis, Docker) — see individual READMEs

## Support

Refer to the main lab documentation files in the parent directory for detailed explanations and exercises.

## Python 3.11 Compatibility

All labs are optimized for **Python 3.11** which provides:
- ✅ Excellent stability with LangChain
- ✅ Full package compatibility
- ✅ No compatibility warnings
- ✅ Best performance

Key features:
- Updated all package versions for Python 3.11 compatibility
- Migrated to LangChain Core imports (`langchain_core`)
- Updated RAG implementation to use LCEL (LangChain Expression Language)
- All Pydantic models use v2 syntax
- Fallback imports for maximum compatibility

See `PYTHON_3_11_SETUP.md` for detailed setup instructions.

