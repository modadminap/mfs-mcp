"""
HTTP host for the MFS Cowork MCP servers (Azure Container Apps ready).
"""
import os
import sys
import importlib

from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware.base import BaseHTTPMiddleware
from mcp.server.transport_security import TransportSecuritySettings

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

mcp.settings.stateless_http = True
mcp.settings.json_response = True
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
    allowed_hosts=["*"],
    allowed_origins=["*"],
)

AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "").strip()


class BearerAuth(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
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


app = mcp.streamable_http_app()
app.router.routes.insert(0, Route("/health", health, methods=["GET"]))
app.add_middleware(BearerAuth)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
