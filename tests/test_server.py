import asyncio
import os
import unittest
from starlette.testclient import TestClient

import server
from server import app, exec_command, mcp


class TestServerRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root_get(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("name"), server.SERVER_NAME)
        self.assertEqual(data.get("mcp"), "/sse")

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
            "/.well-known/oauth-protected-resource/sse",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn("resource", data)
                self.assertIn("authorization_servers", data)

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

    def test_successful_command(self):
        if os.name == "nt":
            result = exec_command("Write-Output 'Hello from MCP'")
        else:
            result = exec_command("echo 'Hello from MCP'")
        self.assertIn("Hello from MCP", result)

    def test_failing_command(self):
        if os.name == "nt":
            result = exec_command("exit 42")
        else:
            result = exec_command("exit 42")
        self.assertIn("Exit code 42", result)

    def test_timeout_handling(self):
        if os.name == "nt":
            result = exec_command("Start-Sleep -Seconds 5", timeout=1)
        else:
            result = exec_command("sleep 5", timeout=1)
        self.assertIn("timed out after 1 seconds", result)

    def test_fastmcp_tool_registered(self):
        async def check_tools():
            tools = await mcp.list_tools()
            tool_names = [tool.name for tool in tools]
            self.assertIn("exec_command", tool_names)

        asyncio.run(check_tools())


if __name__ == "__main__":
    unittest.main()
