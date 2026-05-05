import os
from typing import Any, Dict, List

import requests
from mcp.server.fastmcp import FastMCP


MCP_HOST_URL = os.getenv("MCP_HOST_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("MCP_REQUEST_TIMEOUT", "300"))

mcp = FastMCP("AISecureOrch Security MCP")


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
    """Run Bandit scan for a local file or folder path."""
    return _post_execute_tools(
        [{"name": "scan_with_bandit", "arguments": {"path": path}}]
    )


@mcp.tool()
def run_sonar(path: str) -> Dict[str, Any]:
    """Run Sonar scan for a local file or folder path."""
    return _post_execute_tools(
        [{"name": "scan_with_sonar", "arguments": {"path": path}}]
    )


@mcp.tool()
def run_safety(path: str) -> Dict[str, Any]:
    """Run Safety dependency scan for a project folder path."""
    return _post_execute_tools(
        [{"name": "scan_with_safety", "arguments": {"path": path}}]
    )


@mcp.tool()
def run_zap(target: str) -> Dict[str, Any]:
    """Run ZAP scan for an HTTP/HTTPS target URL."""
    return _post_execute_tools(
        [{"name": "scan_with_zap", "arguments": {"target": target}}]
    )


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


if __name__ == "__main__":
    # Stdio transport is the default and is compatible with MCP clients in IDEs.
    mcp.run()
