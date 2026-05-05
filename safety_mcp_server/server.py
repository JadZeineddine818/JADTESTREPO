from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import json
import os
import re
from typing import Any, Dict, List
from datetime import datetime

app = FastAPI()


def _log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class ScanRequest(BaseModel):
    path: str


def _extract_json_payload(raw_text: str) -> Any:
    """
    Safety may print banners/warnings before JSON output.
    Try full parse first, then parse from the first JSON bracket onward.
    """
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("empty output")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback for noisy output: extract the first JSON array/object block.
    object_match = re.search(r"\{.*\}", text, re.S)
    if object_match:
        return json.loads(object_match.group(0))

    array_match = re.search(r"\[.*\]", text, re.S)
    if array_match:
        return json.loads(array_match.group(0))

    raise ValueError("no JSON object/array found in output")


def _normalize_safety_findings(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, list):
        vulnerabilities = parsed
    elif isinstance(parsed, dict):
        vulnerabilities = parsed.get("vulnerabilities", [])
    else:
        vulnerabilities = []

    findings = []
    for vuln in vulnerabilities:
        findings.append({
            "tool": "safety",
            "package": vuln.get("package_name") or vuln.get("package"),
            "installed_version": vuln.get("installed_version") or vuln.get("analyzed_version"),
            "vulnerability_id": vuln.get("vulnerability_id") or vuln.get("id"),
            "severity": "High",
            "description": vuln.get("advisory") or vuln.get("description"),
            "recommendation": "Upgrade package to a secure version"
        })
    return findings


def _find_requirements_file(base_path: str) -> str:
    """
    Find requirements.txt at root or nested folders.
    Prefer the shallowest match so uploaded folder roots win.
    """
    direct_path = os.path.join(base_path, "requirements.txt")
    if os.path.exists(direct_path):
        return direct_path

    candidates: List[str] = []
    for root, _, files in os.walk(base_path):
        if "requirements.txt" in files:
            candidates.append(os.path.join(root, "requirements.txt"))

    if not candidates:
        return ""

    candidates.sort(key=lambda p: p.count(os.sep))
    return candidates[0]


@app.post("/execute")
def execute_scan(request: ScanRequest):
    _log(f"[SAFETY] Checkpoint: received execute request path={request.path}")

    requirements_path = _find_requirements_file(request.path)
    _log(f"[SAFETY] Checkpoint: resolved requirements path={requirements_path}")

    if not os.path.exists(requirements_path):
        _log("[SAFETY] Checkpoint: requirements.txt not found")
        return {"error": "No requirements.txt found in project"}

    _log("[SAFETY] Checkpoint: starting safety subprocess")
    process = subprocess.run(
        [
            "safety",
            "check",
            "-r",
            requirements_path,
            "--json"
        ],
        capture_output=True,
        text=True
    )
    _log(f"[SAFETY] Checkpoint: subprocess finished returncode={process.returncode}")
    _log("[SAFETY] Checkpoint: raw stdout begin")
    _log(process.stdout or "<empty>")
    _log("[SAFETY] Checkpoint: raw stdout end")
    _log("[SAFETY] Checkpoint: raw stderr begin")
    _log(process.stderr or "<empty>")
    _log("[SAFETY] Checkpoint: raw stderr end")

    try:
        _log("[SAFETY] Checkpoint: parsing safety JSON output")
        parsed_output = _extract_json_payload(process.stdout)
    except Exception as exc:
        _log("[SAFETY] Checkpoint: failed to parse safety JSON output")
        preview = (process.stdout or "")[:400]
        return {
            "error": "Safety did not return valid JSON",
            "details": str(exc),
            "stdout_preview": preview,
        }

    findings = _normalize_safety_findings(parsed_output)
    _log(f"[SAFETY] Checkpoint: processing vulnerabilities count={len(findings)}")

    _log(f"[SAFETY] Checkpoint: returning findings total={len(findings)}")
    return {
        "total_vulnerabilities": len(findings),
        "findings": findings
    }