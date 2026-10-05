import subprocess
from mcp.server.fastmcp import FastMCP

# Pass host and port directly to FastMCP initialization
mcp = FastMCP("HostTerminalBridge", host="0.0.0.0", port=8000)

@mcp.tool()
def exec_command(command: str) -> str:
    """Executes a command directly on the host system via nsenter."""
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

if __name__ == "__main__":
    # Call run with only the transport specified
    mcp.run(transport="sse")