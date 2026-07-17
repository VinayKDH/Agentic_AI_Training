"""Shared LLM factory for Day2 Advanced multi-agent demo."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from utils.constants import (
    GCP_PROJECT,
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDER_VERTEX,
    OPENAI_MODEL,
    VERTEX_LOCATION,
    VERTEX_MODEL,
)


def _vertex_credentials():
    """Resolve Vertex credentials, avoiding a broken ADC file path if present."""
    broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if broken_adc and not os.path.exists(broken_adc):
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    try:
        import google.auth

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return creds
    except Exception:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
        ).strip()
        from google.oauth2.credentials import Credentials

        return Credentials(token=token)


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.3) -> BaseChatModel:
    """Return chat model for agents (Vertex by default for demo)."""
    provider = os.getenv("LLM_PROVIDER", LLM_PROVIDER_VERTEX).lower().strip()

    if provider == LLM_PROVIDER_VERTEX:
        from langchain_google_vertexai import ChatVertexAI

        return ChatVertexAI(
            model_name=os.getenv("VERTEX_MODEL", VERTEX_MODEL),
            project=os.getenv("GCP_PROJECT", GCP_PROJECT),
            location=os.getenv("VERTEX_LOCATION", VERTEX_LOCATION),
            credentials=_vertex_credentials(),
            temperature=temperature,
        )

    if provider == LLM_PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", OPENAI_MODEL),
            temperature=temperature,
            api_key=api_key,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
