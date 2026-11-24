"""Shared LLM factory supporting Vertex AI and OpenAI."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from utils.constants import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_TEMPERATURE,
    GCP_PROJECT,
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDER_VERTEX,
    OPENAI_MODEL,
    VERTEX_LOCATION,
    VERTEX_MODEL,
)


def _clear_broken_adc() -> None:
    adc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if adc_path and not os.path.exists(adc_path):
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)


def _vertex_credentials():
    _clear_broken_adc()
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


@lru_cache(maxsize=8)
def get_llm(temperature: float = DEFAULT_TEMPERATURE) -> BaseChatModel:
    """Return a chat model based on LLM_PROVIDER env var."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).lower().strip()

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


def active_model_label() -> str:
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
    if provider == LLM_PROVIDER_VERTEX:
        return f"{provider}/{os.getenv('VERTEX_MODEL', VERTEX_MODEL)}"
    return f"{provider}/{os.getenv('OPENAI_MODEL', OPENAI_MODEL)}"
