# Azure / LLM Setup (Bring Your Own Credentials)

This training repo does **not** ship cloud keys. Each student (or instructor) must provide their own LLM credentials.

## Recommended: Azure OpenAI

1. Create (or reuse) an Azure OpenAI resource in your subscription.
2. Deploy a chat model (examples that work with these labs):
   - `gpt-4.1-mini` (preferred default in lab code)
   - or `gpt-4o-mini` / `gpt-4o`
3. Copy the template:

```bash
cd labs
cp .env.azure.example .env.azure
```

4. Edit `labs/.env.azure` with **your** endpoint, key, and deployment name.
5. Load it before running a lab:

```bash
set -a; source labs/.env.azure; set +a
export LLM_PROVIDER=azure
```

### Required variables

| Variable | Example |
|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | `https://YOUR-RESOURCE.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | your key from Azure portal |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | your deployment name |

## Alternative: OpenAI API

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
```

Or put the same values in each lab’s local `.env` (gitignored).

## Security rules for sharing this repo

- Commit **code + `.env.azure.example` only**
- Never commit `.env`, `.env.azure`, keys, or portal screenshots with secrets
- If sharing a zip: exclude `**/.env*`, `**/venv/`, and any local credential files
- Rotate keys if they were ever pasted into chat, slides, or screenshots

## Quick verify

```bash
cd labs/Day2_Advanced
source venv/bin/activate
set -a; source ../.env.azure; set +a
export LLM_PROVIDER=azure
python -c "from utils.llm import active_model_label, get_llm; print(active_model_label()); print(get_llm().invoke('ping').content[:80])"
```
