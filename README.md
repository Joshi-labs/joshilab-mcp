# joshilab-mcp: Host Terminal Bridge

A containerized Model Context Protocol (MCP) server providing host command execution via **Streamable HTTP** and **SSE**. Built with Python FastMCP and Starlette, designed for native integration with Google Gemini, Claude Desktop, and modern MCP clients.

---

## Features

- **MCP Tools**: Exposes `exec_command` to run arbitrary commands directly on the host system using `nsenter`.
- **Streamable HTTP & SSE**: Full support for both modern Streamable HTTP (`/mcp`, `/sse`) and legacy SSE.
- **Gemini Connected Apps Ready**: Complete OAuth 2.0 implementation (`/oauth/authorize`, `/oauth/token`) and RFC 9728 discovery metadata (`/.well-known/oauth-protected-resource`).
- **Health Checks**: `/health` and `/healthz` endpoints with Docker `HEALTHCHECK`.
- **CORS Enabled**: Permissive CORS headers for browser-based MCP clients.
- **Configurable**: Configurable via environment variables with auto-printed credentials banner in logs.

---

## Gemini Custom Connected App Setup

In the Google Gemini interface (**Connect to an MCP server**):

| Field | Value |
|---|---|
| **MCP server URL** | `https://host.vpjoshi.in/mcp` |
| **Client ID** | `joshilab-client` (or value of `OAUTH_CLIENT_ID`) |
| **Client secret** | `joshilab-secret-2026` (or value of `OAUTH_CLIENT_SECRET`) |

> The credentials are also printed clearly in your container logs upon startup.

---

## Quick Start

### Using Docker Compose (Recommended)

```bash
docker compose up -d --build
```

To view the server logs and see your OAuth credentials banner:

```bash
docker compose logs -f joshilab-mcp
```

### Using Docker Run

```bash
docker run -d \
  --name joshilab-mcp \
  --restart unless-stopped \
  --privileged \
  --pid host \
  --network host \
  -e PUBLIC_URL="https://host.vpjoshi.in" \
  -e OAUTH_CLIENT_ID="joshilab-client" \
  -e OAUTH_CLIENT_SECRET="joshilab-secret-2026" \
  ghcr.io/joshi-labs/joshilab-mcp:latest
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind IP address |
| `PORT` | `8000` | Port for the HTTP/MCP server |
| `PUBLIC_URL` | `https://host.vpjoshi.in` | Public URL advertised in discovery probes |
| `OAUTH_CLIENT_ID` | `joshilab-client` | OAuth 2.0 client ID for Gemini |
| `OAUTH_CLIENT_SECRET` | `joshilab-secret-2026` | OAuth 2.0 client secret for Gemini |
| `SERVER_NAME` | `HostTerminalBridge` | MCP server identification name |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/mcp` | `GET`, `POST`, `DELETE` | Modern Streamable HTTP MCP endpoint (Gemini default) |
| `/sse` | `GET`, `POST` | Dual Streamable HTTP / SSE endpoint |
| `/` | `GET`, `POST` | Health & endpoint discovery probe |
| `/health`, `/healthz` | `GET` | Health check endpoint |
| `/.well-known/oauth-protected-resource` | `GET` | RFC 9728 OAuth discovery probe |
| `/.well-known/oauth-authorization-server` | `GET` | RFC 8414 Authorization server metadata |
| `/oauth/authorize` | `GET` | OAuth authorization code endpoint |
| `/oauth/token` | `POST` | OAuth token exchange endpoint |

---

## Local Development & Testing

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest httpx
   ```

2. **Run tests**:
   ```bash
   pytest -v
   ```

3. **Run the server**:
   ```bash
   python server.py
   ```
