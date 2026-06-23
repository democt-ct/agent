import os
import threading
import time
import uuid as uuid_mod

import app.models  # noqa: F401
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.evaluation_routes import router as evaluation_router
from app.api.memory_routes import router as memory_router
from app.api.mcp_routes import router as mcp_router
from app.api.stream_routes import router as stream_router
from app.api.routes import router
from app.core.metrics import metrics_endpoint, HTTP_REQUEST_COUNT, HTTP_REQUEST_LATENCY
from app.core.database import Base, engine
from app.core.logging import setup_logging, get_logger, log_request
from app.core.scheduler import start_scheduler, shutdown_scheduler
from app.middleware.patient_data_guard import PatientDataGuardMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
# Lazy import — get_knowledge_retriever is imported inside on_startup to avoid pulling
# chromadb / torch / sentence-transformers at module load time.


APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(APP_DIR)
TESTER_HTML = os.path.join(APP_DIR, "static", "index.html")
EVALUATE_HTML = os.path.join(APP_DIR, "static", "evaluate.html")
REACT_DIST = os.path.join(PROJECT_DIR, "frontend", "dist")
OPENAPI_TAGS = [
    {
        "name": "memory",
        "description": "记忆模块：包含短期会话记忆、长期画像、关键事件抽取与偏好配置接口。",
    },
    {
        "name": "mcp-server",
        "description": "MCP 服务模块：包含工具列表、智能问答、图文问答、身份 token 与语音输出接口。",
    },
]

# Setup logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")
setup_logging(level=LOG_LEVEL, format_type=LOG_FORMAT)

logger = get_logger(__name__)

app = FastAPI(
    title="Patient Agent Data Service",
    version="0.3.1",
    description="患者身份信息、病历、就诊记录和模块化 MCP 工具服务",
    openapi_tags=OPENAPI_TAGS,
)

STATIC_DIR = os.path.join(APP_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Serve React frontend if built
if os.path.isdir(REACT_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(REACT_DIST, "assets")), name="react-assets")


# Request logging middleware with tracing
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else None
        path = request.url.path
        
        # Generate trace_id for request correlation
        trace_id = request.headers.get("X-Trace-Id") or str(uuid_mod.uuid4())[:8]
        
        # Add trace_id to request state for downstream use
        request.state.trace_id = trace_id
        
        response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Structured log with trace_id
        log_request(
            logger=logger,
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )
        logger.info(
            "[trace=%s] %s %s %s %.1fms",
            trace_id, request.method, path, response.status_code, duration_ms,
        )
        
        # Record Prometheus metrics
        HTTP_REQUEST_COUNT.labels(
            method=request.method, path=path, status=response.status_code,
        ).inc()
        HTTP_REQUEST_LATENCY.labels(
            method=request.method, path=path,
        ).observe(duration_ms / 1000.0)
        
        # Pass trace_id in response header
        response.headers["X-Trace-Id"] = trace_id
        
        return response


app.add_middleware(LoggingMiddleware)

# CORS: allow specific origins from env (default * for development)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
logger.info("CORS origins: %s", CORS_ORIGINS)

# Rate limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
app.add_middleware(RateLimitMiddleware, max_per_minute=RATE_LIMIT_PER_MINUTE)
logger.info("Rate limit: %d/min", RATE_LIMIT_PER_MINUTE)

# Patient data access control and audit logging
app.add_middleware(PatientDataGuardMiddleware)
logger.info("Patient data guard middleware enabled")


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting Patient Agent Data Service...")
    
    # Create tables automatically on first startup.
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
    
    try:
        # Deferred import so chromadb / torch / sentence-transformers only load now,
        # not at app module import time.
        from app.services.knowledge_retrieval import get_knowledge_retriever  # noqa: F811

        # Warm up the retrieval stack so the first user question does not pay
        # the model initialization cost.
        threading.Thread(target=get_knowledge_retriever().warmup, daemon=True).start()
        logger.info("Knowledge retriever warmup started in background")
    except Exception as e:
        logger.warning(f"Knowledge retriever warmup failed: {e}")

    # Start background scheduler
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
def on_shutdown() -> None:
    logger.info("Shutting down application...")
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler shutdown failed: {e}")


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "version": "0.3.1"}


@app.get("/health/detailed")
def detailed_health_check():
    """Detailed health check with component status."""
    health_status = {
        "status": "ok",
        "version": "0.3.1",
        "components": {}
    }
    
    # Check database
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["components"]["database"] = {"status": "ok"}
    except Exception as e:
        health_status["components"]["database"] = {"status": "error", "message": str(e)}
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        from app.core.redis_client import get_redis_client
        client = get_redis_client()
        client.ping()
        health_status["components"]["redis"] = {"status": "ok"}
    except Exception as e:
        health_status["components"]["redis"] = {"status": "error", "message": str(e)}
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/", include_in_schema=False)
def tester_home():
    # Serve React build if available, else legacy static html
    react_index = os.path.join(REACT_DIST, "index.html")
    if os.path.isfile(react_index):
        return FileResponse(
            react_index,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return FileResponse(
        TESTER_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/tester", include_in_schema=False)
def tester_page():
    return FileResponse(
        TESTER_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/evaluate", include_in_schema=False)
def evaluate_page():
    """Quality evaluation console."""
    return FileResponse(
        EVALUATE_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


app.include_router(router)
app.include_router(memory_router)
app.include_router(mcp_router)
app.include_router(stream_router)
app.include_router(evaluation_router)

# Prometheus metrics endpoint
app.add_route("/metrics", metrics_endpoint, include_in_schema=False)
logger.info("Prometheus /metrics endpoint enabled")
