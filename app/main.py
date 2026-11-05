"""
RenewOps – FastAPI Application Entry Point
Unified architecture:
  - Serves REST API at /api/v1/...
  - Serves Web Dashboard & Static assets at / and /static/...
  - Serves Remote Streamable HTTP MCP Server at /mcp
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db.init_db import init_db
from app.api.v1 import subscriptions, renewals, analytics
from app.mcp.server import mcp
from contextlib import asynccontextmanager
# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------
mcp_asgi = mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Subscription & Contract Management Platform – REST API & MCP Server",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if isinstance(settings.ALLOWED_ORIGINS, list) else [settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# MCP Authentication Middleware (protects /mcp when MCP_API_KEY is configured)
# ---------------------------------------------------------------------------

class MCPProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp") and settings.MCP_API_KEY:
            auth_header = request.headers.get("authorization", "") or request.headers.get("x-api-key", "")
            token = auth_header.replace("Bearer ", "").strip()
            if token != settings.MCP_API_KEY:
                return JSONResponse(
                    {"detail": "Unauthorized: Invalid or missing MCP API key"},
                    status_code=401,
                )
        return await call_next(request)


app.add_middleware(MCPProtectionMiddleware)

# ---------------------------------------------------------------------------
# REST API Routers
# ---------------------------------------------------------------------------

app.include_router(subscriptions.router, prefix=settings.API_V1_PREFIX)
app.include_router(renewals.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)

# ---------------------------------------------------------------------------
# Streamable HTTP MCP Mount (/mcp)
# ---------------------------------------------------------------------------

mcp_asgi = mcp.streamable_http_app()
app.mount("/mcp", mcp_asgi)

# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{page}", include_in_schema=False)
    def serve_page(page: str):
        page_path = os.path.join(frontend_dir, page)
        if os.path.isfile(page_path):
            return FileResponse(page_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "mcp_endpoint": "/mcp",
        "demo_org_id": settings.DEMO_ORG_ID,
    }

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    init_db()
