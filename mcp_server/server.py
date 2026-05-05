import os
from typing import Any, Dict, List

import requests
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP


MCP_HOST_URL = os.getenv("MCP_HOST_URL", "http://mcp_host:8000")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("MCP_REQUEST_TIMEOUT", "300"))

mcp = FastMCP("AISecureOrch Security MCP")

app = FastAPI()


@app.post("/execute")
def execute_tool(request: dict):
    tool_name = request.get("tool")
    args = request.get("arguments", {})

    if tool_name == "run_zap":
        return run_zap(**args)
    elif tool_name == "run_bandit":
        return run_bandit(**args)
    elif tool_name == "run_sonar":
        return run_sonar(**args)
    elif tool_name == "run_safety":
        return run_safety(**args)
    else:
        return {"error": "Unknown tool"}


def _post_execute_tools(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Call existing orchestrator endpoint and normalize errors."""
    try:
        response = requests.post(
            f"{MCP_HOST_URL}/execute_tools",
            json={"tools": tools},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {
            "status": "error",
            "message": "Failed to reach mcp_host service",
            "details": str(exc),
        }

    if response.status_code != 200:
        return {
            "status": "error",
            "message": "mcp_host returned non-200 response",
            "status_code": response.status_code,
            "body": response.text,
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "status": "error",
            "message": "mcp_host returned invalid JSON",
            "body": response.text,
        }

    return {
        "status": "success",
        "results": payload.get("results", {}),
    }


@mcp.tool()
def run_bandit(path: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://bandit_mcp_server:8001/execute",
            json={"path": path},
            timeout=300
        )
        return response.json()
    except Exception as e:
        return {
            "error": "Bandit scan failed",
            "details": str(e)
        }


@mcp.tool()
def run_sonar(path: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://sonar_mcp_server:8002/execute",
            json={"path": path},
            timeout=300
        )
        return response.json()
    except Exception as e:
        return {
            "error": "Sonar scan failed",
            "details": str(e)
        }


@mcp.tool()
def run_safety(path: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://safety_mcp_server:8004/execute",
            json={"path": path},
            timeout=300
        )
        return response.json()
    except Exception as e:
        return {
            "error": "Safety scan failed",
            "details": str(e)
        }


@mcp.tool()
def run_zap(target: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://zap_mcp_server:8003/execute",
            json={"target": target},
            timeout=1200   # ⚠️ VERY IMPORTANT (ZAP is slow)
        )
        return response.json()
    except Exception as e:
        return {
            "error": "ZAP scan failed",
            "details": str(e)
        }

@mcp.tool()
def run_all_local(path: str) -> Dict[str, Any]:
    """Run Bandit + Sonar + Safety for a local project path."""
    return _post_execute_tools(
        [
            {"name": "scan_with_bandit", "arguments": {"path": path}},
            {"name": "scan_with_sonar", "arguments": {"path": path}},
            {"name": "scan_with_safety", "arguments": {"path": path}},
        ]
    )


@app.get("/")
def root():
    return {"status": "MCP server is running"}


# ✅ MOUNT MCP TO HTTP
app.mount("/mcp", mcp.sse_app())
