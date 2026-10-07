"""
HTTP host for the MFS Cowork MCP servers (Azure Container Apps ready).

Wraps a FastMCP server with the Streamable HTTP transport, a bearer-token auth
gate, and an unauthenticated /health endpoint, then serves it with uvicorn.

Which expert to host is chosen by the MCP_SERVER env var:
    equity | credit | portfolio

Env:
    MCP_SERVER       equity | credit | portfolio   (required)
    MCP_AUTH_TOKEN   bearer token clients must send (optional; no auth if unset)
    FINNHUB_API_KEY  required only for the equity server
    PORT             listen port (default 8000)

Local run:
    $env:MCP_SERVER="credit"; python host.py
Endpoint:
    POST https://<host>/mcp     (Streamable HTTP MCP)
    GET  https://<host>/health  (liveness)
"""
import os
import sys
import importlib

from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware.base import BaseHTTPMiddleware

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "servers"))
sys.path.insert(0, os.path.join(HERE, "shared"))

SERVER_MODULES = {
    "equity": "equity_server",
    "credit": "credit_server",
    "portfolio": "portfolio_server",
}

choice = os.environ.get("MCP_SERVER", "").strip().lower()
if choice not in SERVER_MODULES:
    sys.stderr.write(
        f"MCP_SERVER must be one of {list(SERVER_MODULES)}, got '{choice}'.\n")
    sys.exit(2)

module = importlib.import_module(SERVER_MODULES[choice])
mcp = module.mcp

# Stateless HTTP so the app scales cleanly across ACA replicas (our tools are
# stateless) and returns plain JSON responses.
mcp.settings.stateless_http = True
mcp.settings.json_response = True

AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()


class BearerAuth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # health is always open; everything else needs the bearer token (if set)
        if request.url.path == "/health" or not AUTH_TOKEN:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and auth[7:].strip() == AUTH_TOKEN:
            return await call_next(request)
        return JSONResponse({"error": "unauthorized"}, status_code=401)


async def health(_request):
    return JSONResponse({
        "status": "ok",
        "server": mcp.name,
        "expert": choice,
        "transport": "streamable-http",
        "auth": "bearer" if AUTH_TOKEN else "open",
    })


# streamable_http_app() returns a Starlette app with the MCP session lifespan
# already wired. We add the health route and the auth middleware onto it.
app = mcp.streamable_http_app()
app.router.routes.insert(0, Route("/health", health, methods=["GET"]))
app.add_middleware(BearerAuth)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
