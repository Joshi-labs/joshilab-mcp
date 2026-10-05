import subprocess
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP
mcp = FastMCP("HostTerminalBridge", host="0.0.0.0", port=8000)

@mcp.tool()
def exec_command(command: str) -> str:
    """Executes arbitrary commands directly on the host system via nsenter."""
    cmd = [
        "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--",
        "/bin/bash", "-c", command
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        output = (result.stdout + ("\n[STDERR]\n" + result.stderr if result.stderr else "")).strip()
        return output if output else f"(Exit code {result.returncode}, no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds."
    except Exception as e:
        return f"Execution failed: {str(e)}"

# Access the underlying Starlette/FastAPI application inside FastMCP
app = mcp._app

# 1. Handle root GET and POST so Gemini probes don't 404
@app.get("/")
@app.post("/")
async def root():
    return JSONResponse({
        "status": "ok",
        "name": "HostTerminalBridge",
        "mcp": "/sse"
    })

# 2. Handle the OAuth discovery probes that Gemini sends
@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/sse")
async def oauth_protected_resource():
    return JSONResponse({
        "resource": "https://localhost",
        "authorization_servers": []
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)