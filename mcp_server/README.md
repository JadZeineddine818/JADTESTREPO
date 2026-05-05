# AISecureOrch MCP Server

This is the MCP interface layer for AISecureOrch.

It exposes official MCP tools (for VS Code/Cursor MCP clients) and forwards calls to the existing `mcp_host` orchestrator:

- `run_bandit(path)`
- `run_sonar(path)`
- `run_safety(path)`
- `run_zap(target)`
- `run_all_local(path)`

## How it fits

MCP Client (VS Code/Cursor) -> `mcp_server` (this folder) -> `mcp_host` -> tool services

## Setup

1. Install dependencies:

```bash
pip install -r mcp_server/requirements.txt
```

2. Ensure `mcp_host` is running and reachable (default: `http://localhost:8000`).

3. Optional environment variables:

- `MCP_HOST_URL` (default: `http://localhost:8000`)
- `MCP_REQUEST_TIMEOUT` (default: `300` seconds)

## Run manually (stdio)

```bash
python mcp_server/server.py
```

## Add in MCP client config

Example MCP server entry:

```json
{
  "mcpServers": {
    "aisecureorch": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": {
        "MCP_HOST_URL": "http://localhost:8000"
      }
    }
  }
}
```

Use this configuration in your editor MCP settings and then connect to the `aisecureorch` server.
