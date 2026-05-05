from fastapi import FastAPI
from pydantic import BaseModel
import requests
import subprocess
import os
import time
import uuid

app = FastAPI()

SONAR_HOST = os.getenv("SONAR_HOST", "http://sonarqube:9000")
SONAR_TOKEN = os.getenv("SONAR_TOKEN")
SONAR_SCANNER_TIMEOUT_SEC = int(os.getenv("SONAR_SCANNER_TIMEOUT_SEC", "60"))


class ScanRequest(BaseModel):
    path: str


def wait_for_sonar():
    print("[SONAR] Checkpoint: waiting for SonarQube readiness")
    for _ in range(60):
        try:
            r = requests.get(f"{SONAR_HOST}/api/system/status", timeout=10)
            if r.status_code == 200 and r.json().get("status") == "UP":
                print("[SONAR] Checkpoint: SonarQube is ready")
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("SonarQube not ready")


def run_sonar_scanner(project_path: str, project_key: str):
    print(f"[SONAR] Checkpoint: preparing scanner command project_key={project_key} path={project_path}")
    cmd = [
        "sonar-scanner",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectBaseDir={project_path}",
        f"-Dsonar.sources=.", 
        f"-Dsonar.host.url={SONAR_HOST}",
        f"-Dsonar.login={SONAR_TOKEN}",
    ]

    print("Running command:", cmd)

    print(f"[SONAR] Checkpoint: starting sonar-scanner subprocess timeout={SONAR_SCANNER_TIMEOUT_SEC}s")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SONAR_SCANNER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        print("[SONAR] Checkpoint: sonar-scanner timed out")
        return {
            "error": "Sonar scan timed out",
            "skipped": True,
            "reason": (
                f"Sonar scanner did not finish within {SONAR_SCANNER_TIMEOUT_SEC} seconds; "
                "skipped so other tools can continue."
            ),
        }

    print(f"[SONAR] Checkpoint: sonar-scanner finished returncode={result.returncode}")

    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

    if result.returncode != 0:
        print("[SONAR] Checkpoint: sonar-scanner failed")
        detail = (result.stderr or result.stdout or "").strip()
        return {
            "error": "Sonar scanner failed",
            "details": detail[:4000] if detail else "unknown scanner error",
            "returncode": result.returncode,
        }

    print("[SONAR] Checkpoint: sonar-scanner completed successfully")
    return None


@app.post("/execute")
def execute_scan(request: ScanRequest):
    exec_id = uuid.uuid4().hex[:8]
    print(f"========== [SONAR] BEGIN EXECUTION id={exec_id} path={request.path} ==========")
    try:
        print(f"[SONAR] Checkpoint: received execute request path={request.path}")

        try:
            wait_for_sonar()
        except RuntimeError as exc:
            print("[SONAR] Checkpoint: SonarQube readiness failed")
            return {"error": "SonarQube not ready", "details": str(exc)}

        print("[SONAR] Checkpoint: readiness check passed")

        project_key = "AISecureOrch_Dynamic"
        print(f"[SONAR] Checkpoint: using project key project_key={project_key}")

        scan_err = run_sonar_scanner(request.path, project_key)
        if scan_err:
            return scan_err

        print("[SONAR] Checkpoint: scanner execution completed")

        print("[SONAR] Checkpoint: waiting for background processing")
        time.sleep(10)

        print("[SONAR] Checkpoint: fetching issues from SonarQube API")
        try:
            issues = requests.get(
               f"{SONAR_HOST}/api/issues/search",
               auth=(SONAR_TOKEN, ""),
               params={
                 "componentKeys": project_key,
                 "ps": 500,  # get more results
                 "resolved": "false",
                 "types": "VULNERABILITY,BUG,CODE_SMELL",
              },
              timeout=60,
            )  
        except requests.RequestException as exc:
            return {"error": "Sonar issues API request failed", "details": str(exc)}

        print(f"[SONAR] Checkpoint: issues API responded status_code={issues.status_code}")

        if issues.status_code != 200:
            print("[SONAR] Checkpoint: issues API returned non-200 response")
            return {"error": "Sonar issues API returned non-200", "body": issues.text[:2000]}

        print("[SONAR] Checkpoint: returning issues payload")
        return issues.json()
    except Exception as exc:
        print(f"[SONAR] Checkpoint: unexpected error {exc!r}")
        return {"error": "Sonar execution error", "details": str(exc)}
    finally:
        print(f"========== [SONAR] END EXECUTION id={exec_id} ==========")
