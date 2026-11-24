"""LLM factory for Day3 Advanced (Azure OpenAI + OpenAI)."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.constants import (
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_TEMPERATURE,
    LLM_PROVIDER_AZURE,
    LLM_PROVIDER_OPENAI,
    OPENAI_MODEL,
)
from app.config import settings


@lru_cache(maxsize=8)
def get_llm(temperature: float = DEFAULT_TEMPERATURE) -> BaseChatModel:
    provider = (
        os.getenv("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
        or DEFAULT_LLM_PROVIDER
    ).lower().strip()

    if provider == LLM_PROVIDER_AZURE:
        from langchain_openai import AzureChatOpenAI

        endpoint = (
            os.getenv("AZURE_OPENAI_ENDPOINT")
            or getattr(settings, "AZURE_OPENAI_ENDPOINT", None)
            or os.getenv("OPENAI_API_BASE")
        )
        api_key = (
            os.getenv("AZURE_OPENAI_API_KEY")
            or getattr(settings, "AZURE_OPENAI_API_KEY", None)
            or os.getenv("OPENAI_API_KEY")
            or settings.OPENAI_API_KEY
        )
        deployment = (
            os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT")
            or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", None)
            or AZURE_OPENAI_DEPLOYMENT
        )
        api_version = (
            os.getenv("AZURE_OPENAI_API_VERSION")
            or getattr(settings, "AZURE_OPENAI_API_VERSION", None)
            or AZURE_OPENAI_API_VERSION
        )
        if not endpoint or not api_key:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required "
                "when LLM_PROVIDER=azure"
            )
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            azure_deployment=deployment,
            temperature=temperature,
        )

    if provider == LLM_PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL or OPENAI_MODEL),
            temperature=temperature,
            api_key=api_key,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def active_model_label() -> str:
    provider = (
        os.getenv("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", DEFAULT_LLM_PROVIDER)
    )
    if provider == LLM_PROVIDER_AZURE:
        deployment = (
            os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
            or os.getenv("AZURE_OPENAI_DEPLOYMENT")
            or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", None)
            or AZURE_OPENAI_DEPLOYMENT
        )
        return f"{provider}/{deployment}"
    return f"{provider}/{os.getenv('OPENAI_MODEL', settings.OPENAI_MODEL)}"
