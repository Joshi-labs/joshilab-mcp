import os
import shutil
import subprocess
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

# Configuration via environment variables
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
SERVER_NAME = os.environ.get("SERVER_NAME", "HostTerminalBridge")
USE_NSENTER = os.environ.get(
    "USE_NSENTER", "1" if shutil.which("nsenter") else "0"
).lower() in ("1", "true", "yes")

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

    if USE_NSENTER and shutil.which("nsenter"):
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


# Custom routes for probes, health checks, and Gemini OAuth discovery
@mcp.custom_route("/", methods=["GET", "POST"])
async def root(request: Request) -> JSONResponse:
    """Root endpoint responding to health and Gemini discovery probes."""
    return JSONResponse({
        "status": "ok",
        "name": SERVER_NAME,
        "mcp": "/sse",
    })


@mcp.custom_route("/health", methods=["GET"])
@mcp.custom_route("/healthz", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Liveness and health check endpoint."""
    return JSONResponse({"status": "healthy"})


@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
@mcp.custom_route("/.well-known/oauth-protected-resource/sse", methods=["GET"])
async def oauth_protected_resource(request: Request) -> JSONResponse:
    """OAuth discovery probes handling for Gemini and other MCP clients."""
    return JSONResponse({
        "resource": "https://localhost",
        "authorization_servers": [],
    })


# Create the Starlette ASGI application from FastMCP
app = mcp.sse_app()

# Add CORS middleware to support browser-based MCP clients
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