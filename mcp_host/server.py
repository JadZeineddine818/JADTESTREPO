from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Form
from typing import List
from pydantic import BaseModel
import asyncio
import requests
import os
import uuid
import re
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
import zipfile

from database import SessionLocal, engine, Base
from models import User, Scan
from schemas import LoginRequest, RegisterRequest
from auth_utils import verify_password, hash_password

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

SECRET_KEY = "my_super_secret_key_12345"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
SEED_USER_EMAIL = os.getenv("SEED_USER_EMAIL", "admin@example.com")
SEED_USER_PASSWORD = os.getenv("SEED_USER_PASSWORD", "Admin@12345")
AI_AGENT_REQUEST_TIMEOUT = int(os.getenv("AI_AGENT_REQUEST_TIMEOUT", "900"))
TOOL_EXECUTE_HTTP_TIMEOUT = int(os.getenv("MCP_TOOL_EXECUTE_TIMEOUT", "120"))


def seed_default_user():
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == SEED_USER_EMAIL).first()
        if existing_user:
            return

        seeded_user = User(
            email=SEED_USER_EMAIL,
            hashed_password=hash_password(SEED_USER_PASSWORD)
        )
        db.add(seeded_user)
        db.commit()
        print(f"Seed user created: {SEED_USER_EMAIL}")
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    seed_default_user()


# =========================
# AUTH FUNCTION
# =========================
def get_current_user_email(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# =========================
# DB SESSION
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# JWT CREATION
# =========================
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )

    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# =========================
# REQUEST MODELS
# =========================
class UserRequest(BaseModel):
    input: str
    report_type: str = "Executive"


class ToolRequest(BaseModel):
    tool_name: str
    arguments: dict


# =========================
# TOOL REGISTRY
# =========================
TOOL_REGISTRY = {
    "scan_with_bandit": "http://bandit_mcp_server:8001/execute",
    "scan_with_sonar": "http://sonar_mcp_server:8002/execute",
    "scan_with_zap": "http://zap_mcp_server:8003/execute",
    "scan_with_safety": "http://safety_mcp_server:8004/execute",
}


def _call_ai_agent_iterative(scan_input: str, report_type: str = "Executive") -> dict:
    try:
        report_response = requests.post(
            "http://ai_agent:8005/analyze_iterative",
            json={"input": scan_input, "report_type": report_type},
            timeout=AI_AGENT_REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail=f"ai_agent timeout while generating report: {str(exc)}",
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"ai_agent request failed: {str(exc)}",
        )

    if report_response.status_code != 200:
        body_preview = (report_response.text or "")[:400]
        raise HTTPException(
            status_code=502,
            detail=f"ai_agent returned status {report_response.status_code}: {body_preview}",
        )

    try:
        return report_response.json()
    except ValueError as exc:
        body_preview = (report_response.text or "")[:400]
        raise HTTPException(
            status_code=502,
            detail=f"ai_agent returned invalid JSON: {str(exc)} | body_preview={body_preview}",
        )


# =========================
# REGISTER
# =========================
@app.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user:
        return {"success": False, "message": "Email already exists"}

    new_user = User(
        email=request.email,
        hashed_password=hash_password(request.password)
    )

    db.add(new_user)
    db.commit()

    return {"success": True, "message": "User registered successfully"}


# =========================
# LOGIN
# =========================
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        return {"success": False, "message": "Invalid email"}

    if not verify_password(request.password, user.hashed_password):
        return {"success": False, "message": "Invalid password"}

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer"
    }


# =========================
# ANALYZE
# =========================
@app.post("/execute_tools")
def execute_tools(request: dict):
    exec_id = uuid.uuid4().hex[:8]
    print(f"========== [MCP_HOST] BEGIN EXECUTION id={exec_id} ==========")
    tools = request.get("tools", [])
    aggregated_results = {}
    print(f"[MCP_HOST] Checkpoint: tool count={len(tools)}")

    try:
        for tool in tools:
            tool_name = tool.get("name")
            arguments = tool.get("arguments", {})
            print(f"[MCP_HOST] Checkpoint: dispatch tool={tool_name} arguments={arguments}")

            tool_url = TOOL_REGISTRY.get(tool_name)

            if not tool_url:
                print(f"[MCP_HOST] Checkpoint: unknown tool skipped tool={tool_name}")
                aggregated_results[tool_name or "unknown_tool"] = {
                    "error": "Unknown tool",
                    "tool_name": tool_name,
                }
                continue

            try:
                tool_response = requests.post(
                    tool_url, json=arguments, timeout=TOOL_EXECUTE_HTTP_TIMEOUT
                )
            except requests.RequestException as exc:
                aggregated_results[tool_name] = {
                    "error": "Tool service request failed",
                    "details": str(exc),
                    "tool_url": tool_url,
                }
                continue

            print(
                f"[MCP_HOST] Checkpoint: response tool={tool_name} status_code={tool_response.status_code}"
            )

            if tool_response.status_code != 200:
                aggregated_results[tool_name] = {
                    "error": "Tool service returned non-200 response",
                    "status_code": tool_response.status_code,
                    "body": tool_response.text,
                }
                continue

            try:
                aggregated_results[tool_name] = tool_response.json()
            except Exception:
                aggregated_results[tool_name] = {
                    "error": "Invalid JSON",
                    "raw": tool_response.text
                }
        return {
            "results": aggregated_results
        }
    finally:
        print(f"========== [MCP_HOST] END EXECUTION id={exec_id} ==========")
    
@app.post("/analyze")
def analyze(
    request: UserRequest,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email)
):
    user_input = request.input

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    final_report = _call_ai_agent_iterative(user_input, request.report_type)

    try:
        new_scan = Scan(
            user_id=user.id,
            input=user_input,
            status="Completed",
            report=final_report.get("final_report", "No report generated")
        )

        db.add(new_scan)
        db.commit()
        db.refresh(new_scan)
    except Exception as e:
        print("ERROR SAVING:", str(e))

    return {
    "id": new_scan.id,
    "final_report": final_report.get("final_report", ""),
    "pdf_report": final_report.get("pdf_report"),
    "results": final_report.get("results", {}),
    "iterations": final_report.get("iterations", 0),
}


# =========================
# UPLOAD + ANALYZE
# =========================
WORKSPACE_UPLOADS = "/workspace/uploads"


@app.post("/upload_and_analyze")
async def upload_and_analyze(
    files: List[UploadFile] = File(...),
    report_type: str = Form("Executive"),
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    scan_dir_id = uuid.uuid4().hex[:12]
    upload_dir = os.path.join(WORKSPACE_UPLOADS, scan_dir_id)
    os.makedirs(upload_dir, exist_ok=True)

    for upload_file in files:
        rel_path = (upload_file.filename or "uploaded_file").replace("\\", "/")
        dest_path = os.path.join(upload_dir, rel_path)
        parent_dir = os.path.dirname(dest_path)
        if parent_dir and parent_dir != upload_dir:
            os.makedirs(parent_dir, exist_ok=True)

        content = await upload_file.read()
        with open(dest_path, "wb") as f:
            f.write(content)

        if rel_path.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(dest_path, "r") as zf:
                    zf.extractall(upload_dir)
                os.remove(dest_path)
            except zipfile.BadZipFile:
                pass

    final_report = await asyncio.to_thread(
        _call_ai_agent_iterative, upload_dir, report_type
    )

    new_scan = None
    try:
        new_scan = Scan(
            user_id=user.id,
            input=upload_dir,
            status="Completed",
            report=final_report.get("final_report", "No report generated"),
        )
        db.add(new_scan)
        db.commit()
        db.refresh(new_scan)
    except Exception as e:
        print("ERROR SAVING:", str(e))

    return {
        "id": new_scan.id if new_scan else None,
        "final_report": final_report.get("final_report", ""),
        "pdf_report": final_report.get("pdf_report"),
        "results": final_report.get("results", {}),
        "iterations": final_report.get("iterations", 0),
    }


# =========================
# GET SCANS
# =========================
@app.get("/scans")
def get_scans(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email)
):
    user = db.query(User).filter(User.email == user_email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    scans = db.query(Scan).filter(Scan.user_id == user.id).order_by(Scan.id.desc()).all()

    return [
        {
            "id": s.id,
            "target": s.input,
            "input": "URL",
            "report": "Executive",
            "status": s.status,
            "date": s.created_at.strftime("%m/%d/%Y, %I:%M:%S %p")
        }
        for s in scans
    ]


# =========================
# 🔥 NEW: GET SINGLE SCAN
# =========================
@app.get("/scan/{scan_id}")
def get_single_scan(
    scan_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email)
):
    user = db.query(User).filter(User.email == user_email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    scan = db.query(Scan).filter(
        Scan.id == scan_id,
        Scan.user_id == user.id
    ).first()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "id": scan.id,
        "target": scan.input,
        "status": scan.status,
        "date": scan.created_at.strftime("%m/%d/%Y, %I:%M:%S %p"),
        "report": scan.report
    }


@app.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email)
):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    scans = db.query(Scan).filter(Scan.user_id == user.id).order_by(Scan.id.desc()).all()

    total_scans = len(scans)
    completed = sum(1 for s in scans if (s.status or "").lower() == "completed")
    failed = sum(1 for s in scans if (s.status or "").lower() == "failed")

    critical = 0
    high = 0
    medium = 0
    low = 0

    # Best-effort severity extraction from persisted report text.
    for scan in scans:
        report_text = (scan.report or "").lower()
        critical += len(re.findall(r"\bcritical\b", report_text))
        high += len(re.findall(r"\bhigh\b", report_text))
        medium += len(re.findall(r"\bmedium\b", report_text))
        low += len(re.findall(r"\blow\b", report_text))

    recent = scans[0] if scans else None
    recent_payload = {
        "id": "-",
        "target": "-",
        "status": "Idle",
        "risk": "Low",
    }

    if recent:
        recent_report = (recent.report or "").lower()
        if "critical" in recent_report:
            risk = "Critical"
        elif "high" in recent_report:
            risk = "High"
        elif "medium" in recent_report:
            risk = "Medium"
        else:
            risk = "Low"

        recent_payload = {
            "id": str(recent.id),
            "target": recent.input,
            "status": recent.status if recent.status in {"Scanning", "Completed", "Failed"} else "Idle",
            "risk": risk,
        }

    return {
        "totalScans": total_scans,
        "completed": completed,
        "failed": failed,
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "recent": recent_payload,
    }