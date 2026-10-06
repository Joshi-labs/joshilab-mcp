import asyncio
import subprocess
import unittest
import urllib.parse
from unittest.mock import patch
from starlette.testclient import TestClient

import server
from server import app, exec_command, mcp, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET


class TestServerRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)

    def test_root_get(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("name"), server.SERVER_NAME)
        self.assertIn("/mcp", data.get("mcp"))

    def test_root_post(self):
        response = self.client.post("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def test_health_endpoints(self):
        for path in ["/health", "/healthz"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"status": "healthy"})

    def test_oauth_protected_resource_endpoints(self):
        for path in [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-protected-resource/sse",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn("resource", data)
                self.assertIn("authorization_servers", data)

    def test_oauth_authorization_server_metadata(self):
        for path in [
            "/.well-known/oauth-authorization-server",
            "/.well-known/openid-configuration",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn("authorization_endpoint", data)
                self.assertIn("token_endpoint", data)

    def test_oauth_authorize_and_token_flow(self):
        # 1. Authorize redirect
        redirect_uri = "https://vertexaisearch.cloud.google.com/oauth-redirect"
        auth_url = f"/oauth/authorize?response_type=code&client_id={OAUTH_CLIENT_ID}&redirect_uri={redirect_uri}&state=gemini_state"
        res = self.client.get(auth_url, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        location = res.headers.get("location")
        self.assertTrue(location.startswith(redirect_uri))
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        self.assertIn("code", parsed)
        self.assertEqual(parsed.get("state"), ["gemini_state"])
        code = parsed["code"][0]

        # 2. Token exchange with valid credentials
        token_res = self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
        })
        self.assertEqual(token_res.status_code, 200)
        token_data = token_res.json()
        self.assertIn("access_token", token_data)
        self.assertEqual(token_data.get("token_type"), "Bearer")

        # 3. Token exchange with invalid credentials
        bad_res = self.client.post("/oauth/token", data={
            "client_id": "wrong-client",
            "client_secret": "wrong-secret",
        })
        self.assertEqual(bad_res.status_code, 401)

    def test_streamable_mcp_initialization(self):
        for path in ["/mcp", "/sse"]:
            with self.subTest(path=path):
                res = self.client.post(
                    path,
                    headers={"Accept": "application/json, text/event-stream"},
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "Gemini", "version": "1.0"},
                        },
                    },
                )
                self.assertEqual(res.status_code, 200)

    def test_cors_headers(self):
        headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        }
        response = self.client.options("/", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            response.headers.get("access-control-allow-origin"),
            ["*", "https://example.com"],
        )


class TestExecCommandTool(unittest.TestCase):
    def test_empty_command(self):
        self.assertEqual(exec_command(""), "Error: Command cannot be empty.")
        self.assertEqual(exec_command("   "), "Error: Command cannot be empty.")

    @patch("subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Hello from host", stderr=""
        )
        result = exec_command("echo 'Hello from host'")
        self.assertEqual(result, "Hello from host")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "nsenter")
        self.assertIn("-t", cmd)
        self.assertIn("1", cmd)
        self.assertIn("/bin/bash", cmd)
        self.assertIn("echo 'Hello from host'", cmd)

    @patch("subprocess.run")
    def test_failing_command(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=42, stdout="", stderr="command failed"
        )
        result = exec_command("exit 42")
        self.assertIn("Exit code 42", result)
        self.assertIn("[STDERR]\ncommand failed", result)

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nsenter", timeout=5))
    def test_timeout_handling(self, mock_run):
        result = exec_command("sleep 10", timeout=5)
        self.assertIn("timed out after 5 seconds", result)

    def test_fastmcp_tool_registered(self):
        async def check_tools():
            tools = await mcp.list_tools()
            tool_names = [tool.name for tool in tools]
            self.assertIn("exec_command", tool_names)

        asyncio.run(check_tools())


if __name__ == "__main__":
    unittest.main()
