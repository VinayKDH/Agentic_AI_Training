from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import agent, auth, metrics
from app.llm import active_model_label
import logging
import os
import time

# Prefer shared Azure lab credentials when present
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env.azure"), override=False)
os.environ.setdefault("LLM_PROVIDER", settings.LLM_PROVIDER)

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))

app = FastAPI(
    title=settings.API_TITLE,
    description="Enterprise production-ready Agentic AI API with guardrails and audit metadata",
    version=settings.API_VERSION,
    debug=settings.DEBUG
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    logging.info(
        f"Request: {request.method} {request.url.path} from {request.client.host}"
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logging.info(
            f"Response: {response.status_code} in {process_time:.3f}s"
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    except Exception as e:
        logging.error(f"Request failed: {str(e)}")
        raise

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX, tags=["authentication"])
app.include_router(agent.router, prefix=settings.API_PREFIX, tags=["agent"])
app.include_router(metrics.router, prefix=settings.API_PREFIX, tags=["metrics"])

@app.get("/")
async def root():
    return {
        "message": settings.API_TITLE,
        "version": settings.API_VERSION,
        "model": active_model_label(),
        "docs": "/docs",
        "health": "/health",
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from app.cache import cache_service
    health_status = {
        "status": "healthy",
        "model": active_model_label(),
        "llm_provider": settings.LLM_PROVIDER,
        "cache": "connected" if cache_service.enabled else "disabled",
        "enterprise_gates": ["input_guardrails", "output_secret_scan", "audit_trail"],
    }
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS if not settings.DEBUG else 1
    )

