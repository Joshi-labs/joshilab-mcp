import subprocess
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("HostTerminalBridge")

@mcp.tool()
def exec_command(command: str) -> str:
    """
    Executes an arbitrary shell command directly on the host root system.
    Runs inside the host's PID 1 namespaces using nsenter without restrictions.
    """
    cmd = [
        "nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--",
        "/bin/bash", "-c", command
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # Prevent infinite hangs on long-running processes
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(f"[STDERR]\n{stderr}")
            
        combined_output = "\n".join(output_parts).strip()
        
        if not combined_output:
            return f"(Command executed with exit code {result.returncode}, no output)"
            
        return combined_output

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds."
    except Exception as e:
        return f"Execution failed: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)