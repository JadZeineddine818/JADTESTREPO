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




@app.get("/")
def root():
    return {"status": "MCP server is running"}


# ✅ MOUNT MCP TO HTTP
app.mount("/mcp", mcp.sse_app())
