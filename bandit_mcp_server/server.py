from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
import uuid
import os
import json

app = FastAPI()

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class BanditRequest(BaseModel):
    path: str


@app.post("/execute")
def execute_bandit(request: BanditRequest):
    """
    MCP Server endpoint for Bandit execution.
    """
    check_id = uuid.uuid4().hex[:8]
    print(f"========== [BANDIT] BEGIN CHECK id={check_id} path={request.path} ==========")
    try:
        print(f"[BANDIT] Checkpoint: received execute request path={request.path}")

        output_file = f"{OUTPUT_DIR}/bandit_{uuid.uuid4().hex}.json"
        print(f"[BANDIT] Checkpoint: output file prepared output_file={output_file}")

        print("[BANDIT] Checkpoint: starting bandit subprocess")
        process = subprocess.run(
            ["bandit", "-r", request.path, "-f", "json", "-o", output_file],
            capture_output=True,
            text=True
        )
        print(f"[BANDIT] Checkpoint: subprocess finished returncode={process.returncode}")

        if process.returncode not in [0, 1]:
            print("[BANDIT] Checkpoint: subprocess failed with unexpected return code")
            return {
                "status": "error",
                "message": process.stderr
            }

        if not os.path.exists(output_file):
            print("[BANDIT] Checkpoint: output file missing after execution")
            return {
                "status": "error",
                "message": "Bandit output not generated"
            }

        print("[BANDIT] Checkpoint: loading JSON report")
        with open(output_file, "r") as f:
            data = json.load(f)
        print("[BANDIT] Checkpoint: JSON report loaded successfully")

        print("[BANDIT] Checkpoint: returning success response")
        return {
            "status": "success",
            "tool": "bandit",
            "results": data
        }
    finally:
        print(f"========== [BANDIT] END CHECK id={check_id} ==========")