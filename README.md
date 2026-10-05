# joshilab-mcp: Host Terminal Bridge

A containerized Model Context Protocol (MCP) server providing host command execution over Server-Sent Events (SSE). Built with Python FastMCP and Starlette, designed for integration with Gemini, Claude Desktop, and other MCP clients.

---

## Features

- **MCP Tools**: Exposes `exec_command` to run arbitrary commands directly on the host system using `nsenter`.
- **Client Compatibility**: Native handling for Gemini OAuth discovery probes (`/.well-known/oauth-protected-resource`) and root discovery probes (`GET /`, `POST /`).
- **Health Checks**: `/health` and `/healthz` endpoints with Docker `HEALTHCHECK` support.
- **CORS Enabled**: Permissive CORS headers for browser-based MCP clients and web interfaces.
- **Configurable**: Fully configurable via environment variables (`HOST`, `PORT`, `SERVER_NAME`, `USE_NSENTER`).
- **CI/CD Ready**: Automated tests and GitHub Container Registry (GHCR) publishing workflow.

---

## Quick Start

### Using Docker Compose (Recommended)

```bash
docker compose up -d
```

To build locally from source:

```bash
docker compose up -d --build
```

### Using Docker Run

```bash
docker run -d \
  --name joshilab-mcp \
  --restart unless-stopped \
  --privileged \
  --pid host \
  --network host \
  ghcr.io/joshi-labs/joshilab-mcp:latest
```

> **Note**: `--privileged` and `--pid host` are required for `nsenter` to escape container namespaces and execute commands on the host root system.

---

## MCP Client Configuration

Connect your MCP client to the server using the SSE transport endpoint:

```json
{
  "mcpServers": {
    "host-terminal": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind IP address for the HTTP/SSE server |
| `PORT` | `8000` | Port for the HTTP/SSE server |
| `SERVER_NAME` | `HostTerminalBridge` | MCP server identification name |
| `USE_NSENTER` | `1` (if `nsenter` found) | `1` to execute via `nsenter`, `0` for direct shell execution |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/sse` | `GET` | MCP Server-Sent Events (SSE) stream |
| `/messages/` | `POST` | MCP client-to-server JSON-RPC message endpoint |
| `/` | `GET`, `POST` | Health & MCP endpoint discovery probe |
| `/health`, `/healthz` | `GET` | Health check endpoint |
| `/.well-known/oauth-protected-resource` | `GET` | Gemini OAuth discovery probe |
| `/.well-known/oauth-protected-resource/sse` | `GET` | Gemini OAuth SSE discovery probe |

---

## Local Development & Testing

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest httpx
   ```

2. **Run tests**:
   ```bash
   pytest
   ```
   Or using Python's built-in test runner:
   ```bash
   python -m unittest discover -s tests
   ```

3. **Run the server**:
   ```bash
   python server.py
   ```
