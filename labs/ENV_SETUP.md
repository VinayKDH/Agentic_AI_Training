# Environment Setup Guide (Students)

Labs load credentials from local env files. **Do not commit secrets.**

## Option A — Shared Azure file (recommended)

```bash
cd labs
cp .env.azure.example .env.azure
# edit labs/.env.azure with your Azure OpenAI endpoint + key + deployment
```

Then in each lab:

```bash
set -a; source ../.env.azure; set +a
export LLM_PROVIDER=azure
```

See [AZURE_AI_SETUP.md](AZURE_AI_SETUP.md) for details.

## Option B — Per-lab `.env`

Create a `.env` inside the lab folder:

### OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### Azure OpenAI
```env
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=YOUR_AZURE_OPENAI_KEY
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4.1-mini
```

### Day 3 Advanced extras
```env
SECRET_KEY=change-me-for-local-dev
REDIS_ENABLED=false
```

## Getting keys

- **Azure OpenAI**: Azure Portal → your OpenAI resource → Keys and Endpoint + Model deployments
- **OpenAI**: https://platform.openai.com/api-keys

## Important

- `.env` and `.env.azure` are gitignored
- Only templates like `.env.azure.example` should be shared
- Instructors: never paste live keys into the repo, README, or slides
