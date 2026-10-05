import contextlib
import os
import secrets
import shutil
import subprocess
import urllib.parse
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Mount, Route

# Configuration via environment variables
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
SERVER_NAME = os.environ.get("SERVER_NAME", "HostTerminalBridge")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://host.vpjoshi.in").rstrip("/")

# OAuth Credentials (defaults provided, can be overridden via env)
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "joshilab-client")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "joshilab-secret-2026")

USE_NSENTER = os.environ.get(
    "USE_NSENTER", "1" if shutil.which("nsenter") else "0"
).lower() in ("1", "true", "yes")

# In-memory stores for issued auth codes and tokens
valid_tokens: set[str] = set()
valid_codes: dict[str, str] = {}


def can_use_nsenter() -> bool:
    """Check if nsenter can be used to execute commands in the host namespace."""
    env_val = os.environ.get("USE_NSENTER")
    if env_val is not None:
        if env_val.lower() not in ("1", "true", "yes"):
            return False
    elif not USE_NSENTER:
        return False

    if not shutil.which("nsenter"):
        return False

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        return False

    if os.path.exists("/proc/1/ns"):
        try:
            for ns in ("mnt", "ipc", "pid"):
                ns_path = f"/proc/1/ns/{ns}"
                if os.path.exists(ns_path) and not os.access(ns_path, os.R_OK):
                    return False
        except OSError:
            return False

    return True


# Initialize FastMCP
mcp = FastMCP(SERVER_NAME, host=HOST, port=PORT)


@mcp.tool()
def exec_command(command: str, timeout: int = 120) -> str:
    """Executes arbitrary commands directly on the host system via nsenter.

    Args:
        command: The shell command to execute on the host.
        timeout: Maximum execution time in seconds (default: 120).
    """
    if not command or not command.strip():
        return "Error: Command cannot be empty."

    if can_use_nsenter():
        cmd = [
            "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--",
            "/bin/bash", "-c", command,
        ]
    else:
        # Fallback for local development or non-containerized environments
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            shell = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
            cmd = [shell, "-c", command]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"[STDERR]\n{result.stderr}")
        output = "\n".join(output_parts).strip()

        if result.returncode != 0:
            exit_msg = f"(Exit code {result.returncode})"
            return f"{output}\n{exit_msg}".strip() if output else exit_msg

        return output if output else "(Command executed successfully with exit code 0, no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution failed: {str(e)}"


# Build the underlying transports
_ = mcp.streamable_http_app()


class StreamableDispatcher:
    """ASGI application wrapping FastMCP's StreamableHTTP session manager."""

    def __init__(self, mcp_instance: FastMCP):
        self.mcp = mcp_instance

    async def __call__(self, scope, receive, send):
        await self.mcp.session_manager.handle_request(scope, receive, send)


streamable_dispatcher = StreamableDispatcher(mcp)

sse_app = mcp.sse_app()
messages_mount = next(r for r in sse_app.routes if getattr(r, "path", "") == "/messages")


def get_base_url(request: Request) -> str:
    """Return public base URL, falling back to request host."""
    if PUBLIC_URL:
        return PUBLIC_URL
    return f"{request.url.scheme}://{request.url.netloc}"


# 1. Root & Health Probes
async def root(request: Request) -> JSONResponse:
    base = get_base_url(request)
    return JSONResponse({
        "status": "ok",
        "name": SERVER_NAME,
        "mcp": f"{base}/mcp",
    })


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy"})


# 2. RFC 9728 OAuth Discovery Endpoints for Gemini & MCP clients
async def oauth_protected_resource(request: Request) -> JSONResponse:
    base = get_base_url(request)
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
    })


async def oauth_authorization_server(request: Request) -> JSONResponse:
    base = get_base_url(request)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": [
            "authorization_code",
            "client_credentials",
            "refresh_token",
        ],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
            "none",
        ],
        "scopes_supported": ["mcp"],
    })


# 3. OAuth 2.0 Authorization Endpoint
async def oauth_authorize(request: Request) -> Response:
    redirect_uri = request.query_params.get("redirect_uri")
    state = request.query_params.get("state", "")
    client_id = request.query_params.get("client_id")

    if not redirect_uri:
        return PlainTextResponse(
            "Gemini MCP OAuth Authorization Endpoint. Ready.", status_code=200
        )

    code = secrets.token_urlsafe(32)
    valid_codes[code] = client_id or OAUTH_CLIENT_ID

    sep = "&" if "?" in redirect_uri else "?"
    target = f"{redirect_uri}{sep}code={code}"
    if state:
        target += f"&state={urllib.parse.quote(state)}"

    return RedirectResponse(url=target, status_code=302)


# 4. OAuth 2.0 Token Endpoint
async def oauth_token(request: Request) -> JSONResponse:
    client_id = None
    client_secret = None

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        client_id = form.get("client_id")
        client_secret = form.get("client_secret")
    elif "application/json" in content_type:
        data = await request.json()
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")

    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        import base64

        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            if ":" in decoded:
                client_id, client_secret = decoded.split(":", 1)
        except Exception:
            pass

    # Verify credentials if supplied
    if client_id and client_id != OAUTH_CLIENT_ID:
        return JSONResponse(
            {"error": "invalid_client", "error_description": "Invalid client ID"},
            status_code=401,
        )
    if client_secret and client_secret != OAUTH_CLIENT_SECRET:
        return JSONResponse(
            {"error": "invalid_client", "error_description": "Invalid client secret"},
            status_code=401,
        )

    token = "mcp_" + secrets.token_urlsafe(32)
    valid_tokens.add(token)

    return JSONResponse({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "scope": "mcp",
    })


@contextlib.asynccontextmanager
async def lifespan(app_instance: Starlette):
    print_startup_banner()
    if mcp._session_manager is not None and mcp.session_manager._has_started:
        mcp._session_manager = None
        _ = mcp.streamable_http_app()
    async with mcp.session_manager.run():
        yield


def print_startup_banner():
    banner = f"""
================================================================================
  JOSHILAB-MCP SERVER INITIALIZED
--------------------------------------------------------------------------------
  MCP Server URL:   {PUBLIC_URL}/mcp
  Alternative URL:  {PUBLIC_URL}/sse

  Gemini OAuth Credentials:
    Client ID:     {OAUTH_CLIENT_ID}
    Client Secret: {OAUTH_CLIENT_SECRET}
================================================================================
"""
    print(banner, flush=True)


routes = [
    Route("/", endpoint=root, methods=["GET", "POST"]),
    Route("/health", endpoint=health, methods=["GET"]),
    Route("/healthz", endpoint=health, methods=["GET"]),
    Route("/.well-known/oauth-protected-resource", endpoint=oauth_protected_resource, methods=["GET"]),
    Route("/.well-known/oauth-protected-resource/mcp", endpoint=oauth_protected_resource, methods=["GET"]),
    Route("/.well-known/oauth-protected-resource/sse", endpoint=oauth_protected_resource, methods=["GET"]),
    Route("/.well-known/oauth-authorization-server", endpoint=oauth_authorization_server, methods=["GET"]),
    Route("/.well-known/openid-configuration", endpoint=oauth_authorization_server, methods=["GET"]),
    Route("/oauth/authorize", endpoint=oauth_authorize, methods=["GET"]),
    Route("/oauth/token", endpoint=oauth_token, methods=["POST"]),
    # Modern Streamable HTTP transport endpoints
    Route("/mcp", endpoint=streamable_dispatcher, methods=["GET", "POST", "DELETE"]),
    Route("/sse", endpoint=streamable_dispatcher, methods=["GET", "POST", "HEAD", "DELETE"]),
    messages_mount,
]

app = Starlette(routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)