"""
MCP Server entry-point (Standalone mode on port 8001).
Run with: python -m app.mcp.run
Or via: uvicorn app.mcp.run:app --port 8001
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import settings
from app.mcp.server import mcp

# Base ASGI streamable app
base_app = mcp.streamable_http_app()


class MCPAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if settings.MCP_API_KEY:
            auth_header = request.headers.get("authorization", "") or request.headers.get("x-api-key", "")
            token = auth_header.replace("Bearer ", "").strip()
            if token != settings.MCP_API_KEY:
                return JSONResponse(
                    {"error": "Unauthorized: Invalid or missing MCP API key"},
                    status_code=401,
                )
        return await call_next(request)


base_app.add_middleware(MCPAuthMiddleware)
app = base_app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.mcp.run:app",
        host="0.0.0.0",
        port=settings.MCP_SERVER_PORT,
        reload=False,
    )
