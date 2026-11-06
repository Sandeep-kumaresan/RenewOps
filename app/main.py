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
# from starlette.routing import Route
# from starlette.types import Scope, Receive, Send
from contextlib import asynccontextmanager
# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

# Configure internal MCP route path to root so FastAPI mount at /mcp forwards cleanly
# Configure MCP's internal path to root.
mcp.settings.streamable_http_path = "/main"
mcp_asgi = mcp.streamable_http_app()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
        if request.url.path.startswith("/mcp"):
            # Allow CORS preflight OPTIONS requests without auth check
            if request.method == "OPTIONS":
                return await call_next(request)

            if settings.MCP_API_KEY:
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
# Streamable HTTP MCP Dispatcher (/mcp and /mcp/...)
# ---------------------------------------------------------------------------

# async def mcp_dispatcher(scope: Scope, receive: Receive, send: Send):
#     """
#     Directly forwards HTTP requests for both /mcp and /mcp/... to mcp_asgi.
#     Normalizes path so clients connecting to either https://host/mcp
#     or https://host/mcp/ are routed seamlessly without 405 Method Not Allowed errors.
#     """
#     if scope["type"] == "http":
#         req_path = scope.get("path", "")
#         if req_path == "/mcp" or req_path == "/mcp/":
#             scope = dict(scope)
#             scope["path"] = "/"
#             scope["root_path"] = scope.get("root_path", "") + "/mcp"
#         elif req_path.startswith("/mcp/"):
#             scope = dict(scope)
#             scope["path"] = req_path[4:]
#             scope["root_path"] = scope.get("root_path", "") + "/mcp"
#     await mcp_asgi(scope, receive, send)


# app.router.routes.append(
#     Route(
#         "/mcp",
#         endpoint=mcp_dispatcher,
#         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
#         include_in_schema=False,
#     )
# )
# app.router.routes.append(
#     Route(
#         "/mcp/{subpath:path}",
#         endpoint=mcp_dispatcher,
#         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
#         include_in_schema=False,
#     )
# )

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
# Static frontend
# ---------------------------------------------------------------------------

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")
    # Mount MCP at /mcp
    app.mount("/mcp", mcp_asgi)
    @app.get("/main", include_in_schema=False)
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{page}", include_in_schema=False)
    def serve_page(page: str):
        if page in ("mcp", "api", "docs", "redoc", "openapi.json", "health"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        page_path = os.path.join(frontend_dir, page)
        if os.path.isfile(page_path):
            return FileResponse(page_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
