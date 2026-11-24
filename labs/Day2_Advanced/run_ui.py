#!/usr/bin/env python3
"""Launch the Day2 Advanced enterprise Agent Desk UI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env.azure", override=False)

os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if broken_adc and not os.path.exists(broken_adc):
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

from ui.app import main

if __name__ == "__main__":
    main()
