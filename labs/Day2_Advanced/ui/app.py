"""FastAPI multi-lab enterprise console (Agent Desk)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT.parent

load_dotenv(ROOT / ".env")
load_dotenv(LABS / ".env.azure", override=False)

os.environ.setdefault("LLM_PROVIDER", "azure")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1-mini")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

broken_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if broken_adc and not os.path.exists(broken_adc):
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

from ui.lab_runners import stream_lab_resume, stream_lab_run
from ui.labs import default_lab_id, get_lab, list_labs
from utils.constants import (
    DEFAULT_AUTONOMY_LEVEL,
    MAX_QUERY_LENGTH,
    UI_HOST,
    UI_PORT,
    UI_SUBTITLE,
    UI_TITLE,
)
from utils.governance import AutonomyGovernor, normalize_autonomy_level
from utils.llm import active_model_label

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title=UI_TITLE, version="2.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=MAX_QUERY_LENGTH)
    lab_id: str = Field(default_factory=default_lab_id)
    enable_hitl: bool = False
    autonomy_level: str = DEFAULT_AUTONOMY_LEVEL


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str = Field(..., min_length=1, max_length=2000)
    lab_id: str = Field(default_factory=default_lab_id)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": UI_TITLE, "labs": [lab["id"] for lab in list_labs()]}


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    labs = list_labs()
    current = get_lab(default_lab_id())
    governance = AutonomyGovernor(DEFAULT_AUTONOMY_LEVEL).catalog()
    return {
        "title": UI_TITLE,
        "subtitle": UI_SUBTITLE,
        "model": active_model_label(),
        "provider": active_model_label().split("/", 1)[0],
        "default_lab_id": default_lab_id(),
        "labs": labs,
        "flow": current.get("flow", []),
        "examples": current.get("examples", []),
        "hitl_default": False,
        "default_autonomy_level": DEFAULT_AUTONOMY_LEVEL,
        "governance": governance,
    }


@app.get("/api/governance")
def governance_catalog() -> dict:
    return AutonomyGovernor(DEFAULT_AUTONOMY_LEVEL).catalog()


@app.get("/api/labs/{lab_id}")
def lab_details(lab_id: str) -> dict:
    try:
        return get_lab(lab_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/runs")
def start_run(body: RunRequest) -> StreamingResponse:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        get_lab(body.lab_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        stream_lab_run(
            body.lab_id,
            query,
            enable_hitl=body.enable_hitl,
            autonomy_level=normalize_autonomy_level(body.autonomy_level),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/runs/resume")
def resume_run(body: ResumeRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_lab_resume(body.lab_id, body.thread_id, body.decision.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    import uvicorn

    host = os.getenv("UI_HOST", UI_HOST)
    port = int(os.getenv("UI_PORT", str(UI_PORT)))
    uvicorn.run(
        "ui.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
