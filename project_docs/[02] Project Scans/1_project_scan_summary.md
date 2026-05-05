# AISecureOrch Project Scan Summary

## Overview
This repository is a containerized security orchestration platform that combines multiple scanners (Bandit, Safety, SonarQube, ZAP), an API orchestrator (`mcp_host`), an AI reporting service (`ai_agent`), and a React frontend dashboard.

The current implementation is beyond a skeleton: core services, Docker wiring, auth flow, scan persistence, and report generation are already present.

## What Has Been Implemented

### 1) Orchestration and Service Topology
- `docker-compose.yml` defines a multi-service architecture with:
  - `postgres` for persistence
  - `mcp_host` as the central backend API/orchestrator
  - scanner microservices: `bandit_mcp_server`, `safety_mcp_server`, `sonar_mcp_server`, `zap_mcp_server`
  - external analysis engines: `sonarqube` and `zap`
  - `ai_agent` for tool-selection interpretation and report generation
  - `frontend` served by Nginx
- Inter-service networking is configured via `mcp_network`.

### 2) Main Backend (`mcp_host`)
- Authentication:
  - `/register` and `/login` implemented.
  - Passwords are hashed with bcrypt via `passlib`.
  - JWT token issuing and token-based dependency guard implemented.
- Scan orchestration:
  - `/analyze` calls `ai_agent` to decide tools, executes tool calls, then calls `ai_agent` again to generate a final report.
  - `/execute_tools` provides direct execution of selected tools.
- Persistence:
  - SQLAlchemy models for `User` and `Scan`.
  - Postgres by default (SQLite file also present in folder).
  - Scan history and detail endpoints: `/scans`, `/scan/{scan_id}`.

### 3) AI Service (`ai_agent`)
- `/interpret`:
  - Uses an LLM (OpenRouter endpoint) with strict prompt rules to output JSON specifying tools and arguments.
- `/generate_report`:
  - Produces structured security report text from aggregated scan output.
  - Calls PDF generator and returns both text report and PDF path.
- `/download_report`:
  - Allows retrieval of generated PDF files.
- `pdf_generator.py`:
  - Generates formatted PDFs with header/footer and pagination.

### 4) Scanner Microservices
- `bandit_mcp_server`:
  - Runs `bandit -r`, stores JSON output in `outputs/`, and returns parsed results.
- `safety_mcp_server`:
  - Runs Safety against `requirements.txt` and returns normalized vulnerability findings.
- `sonar_mcp_server`:
  - Waits for SonarQube readiness, runs sonar-scanner, then fetches issues via Sonar API.
- `zap_mcp_server`:
  - Waits for ZAP, runs spider + active scan, returns capped/filtered alerts.

### 5) Frontend Dashboard (`frontend`)
- Tech stack: React + TypeScript + Vite, production-served by Nginx.
- Auth pages:
  - `Login.tsx`, `Register.tsx` connected to backend auth endpoints.
- Main UX pages:
  - `Dashboard.tsx`: summary KPIs and latest scan view.
  - `NewScan.tsx`: submit URL/file/question and display returned report.
  - `History.tsx`: fetches scan history from backend.
  - `ScanDetails.tsx`: fetches specific scan details and displays report.
  - `Reports.tsx`: local-store-driven report visualization UI.
- Client-side store (`src/data/store.tsx`) holds scan state, findings, summary, and report metadata.

## What Each Top-Level Folder Represents
- `ai_agent/`: AI reasoning + report generation + PDF export API.
- `mcp_host/`: core backend API (auth, orchestration, DB persistence, scan history).
- `bandit_mcp_server/`: Bandit wrapper service.
- `safety_mcp_server/`: Safety wrapper service.
- `sonar_mcp_server/`: Sonar scanner/issue retrieval wrapper service.
- `zap_mcp_server/`: OWASP ZAP wrapper service.
- `frontend/`: user dashboard and workflow UI.
- `outputs/`: generated scanner output artifacts (currently used by Bandit service).
- `reports/`: report artifacts at repository level (also `ai_agent/reports` volume-mounted).
- `scanners/`: currently mostly empty placeholder package directory.

## Current Status Assessment

### Working/Implemented Well
- End-to-end architecture is clearly laid out and dockerized.
- Backend auth and scan persistence are implemented.
- Scanner service wrappers are functional and independently callable.
- AI-based report generation and PDF export are integrated.
- Frontend has a complete workflow shell (auth, create scan, history, detail views).

### Notable Gaps or Integration Risks
- Endpoint mismatch:
  - `frontend/src/pages/NewScan.tsx` calls `http://localhost:8005/agent_flow`.
  - `ai_agent/server.py` does not expose `/agent_flow`.
  - Existing orchestration endpoint is `/analyze` on `mcp_host` (`:8000`).
- Minor routing inconsistency:
  - `App.tsx` defines `/scan/:id` route more than once.
- Mixed data model usage on frontend:
  - Some pages rely on local store mock/demo findings while others pull from backend.
  - This can cause inconsistent report/detail behavior depending on navigation flow.
- Secrets/config hardcoding:
  - JWT `SECRET_KEY` is hardcoded in backend code.
  - DB credentials are plain in compose defaults (acceptable for local dev, risky for production).
- Documentation drift:
  - Root README references older flow (`docker exec ... python main.py`) not fully aligned with current service split.

## Suggested Next Cleanup Priorities
1. Align frontend scan submission to backend orchestrator (`mcp_host /analyze`) or add missing `ai_agent /agent_flow`.
2. Consolidate frontend data source (backend-first, store as cache only).
3. Move secrets to environment variables and rotate default keys/passwords.
4. Update README to reflect current microservice architecture and actual run flow.
5. Add basic integration tests for auth + scan submission + report retrieval.
