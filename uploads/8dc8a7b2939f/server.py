from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
import uuid
import json
from typing import Any, Dict, List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from pdf_generator import generate_pdf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") # gpt 4o mini
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1")
# OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

MCP_HOST_URL = os.getenv("MCP_HOST_URL", "http://mcp_host:8000")
MCP_LOOP_MAX_STEPS = int(os.getenv("MCP_LOOP_MAX_STEPS", "6"))

# ollama_client = OpenAI(
#     base_url=OLLAMA_BASE_URL,
#     api_key=OLLAMA_API_KEY,
# )
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

class UserRequest(BaseModel):
    input: str


class ReportRequest(BaseModel):
    input: str
    results: dict


class IterativeScanRequest(BaseModel):
    input: str


MCP_TOOL_SCHEMAS = [
    {
        "type": "function",
        "name": "run_bandit",
        "description": "Run Bandit static scan on a local file/folder path.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "run_sonar",
        "description": "Run Sonar scan on a local file/folder path.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "run_safety",
        "description": "Run Safety dependency scan using a project folder path.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "run_zap",
        "description": "Run ZAP dynamic scan on an HTTP/HTTPS URL target.",
        "parameters": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
            "additionalProperties": False,
        },
    },
]


MCP_TO_HOST_TOOL_MAP = {
    "run_bandit": "scan_with_bandit",
    "run_sonar": "scan_with_sonar",
    "run_safety": "scan_with_safety",
    "run_zap": "scan_with_zap",
}


def call_gpt(messages):
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=messages,
    )
    return response.output_text or ""


def call_openai_with_tools(
    input_payload: Any,
    previous_response_id: str = None
) -> Any:

    # Convert your structured messages into plain text
    if isinstance(input_payload, list):
        text_input = ""
        for msg in input_payload:
            if isinstance(msg, dict) and "content" in msg:
                if isinstance(msg["content"], list):
                    for c in msg["content"]:
                        if isinstance(c, dict) and "text" in c:
                            text_input += c["text"] + "\n"
                elif isinstance(msg["content"], str):
                    text_input += msg["content"] + "\n"
    else:
        text_input = str(input_payload)

    request_kwargs: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "input": text_input,   
        "tools": MCP_TOOL_SCHEMAS,
    }

    if previous_response_id:
        request_kwargs["previous_response_id"] = previous_response_id

    return client.responses.create(**request_kwargs)


def execute_mcp_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    host_tool_name = MCP_TO_HOST_TOOL_MAP.get(tool_name)
    if not host_tool_name:
        return {"error": f"Unsupported MCP tool: {tool_name}"}

    if host_tool_name == "scan_with_zap":
        payload_args = {"target": tool_args.get("target")}
        print(f" [ZAP_CHECKPOINT] mapped {tool_name} -> {host_tool_name} target={payload_args.get('target')}")
    else:
        payload_args = {"path": tool_args.get("path")}

    try:
        if host_tool_name == "scan_with_zap":
            print(" [ZAP_CHECKPOINT] dispatching request to mcp_host /execute_tools")
        response = requests.post(
            f"{MCP_HOST_URL}/execute_tools",
            json={"tools": [{"name": host_tool_name, "arguments": payload_args}]},
            timeout=1200
        )
    except requests.RequestException as exc:
        if host_tool_name == "scan_with_zap":
            print(f" [ZAP_CHECKPOINT] request exception before execution: {str(exc)}")
        return {"error": "Failed to call mcp_host", "details": str(exc)}

    if response.status_code != 200:
        if host_tool_name == "scan_with_zap":
            print(f" [ZAP_CHECKPOINT] mcp_host returned status={response.status_code}")
        return {
            "error": "mcp_host returned non-200",
            "status_code": response.status_code,
            "body": response.text,
        }

    try:
        payload = response.json()
    except ValueError:
        if host_tool_name == "scan_with_zap":
            print(" [ZAP_CHECKPOINT] mcp_host response is not valid JSON")
        return {"error": "mcp_host returned invalid JSON", "body": response.text}

    result = payload.get("results", {}).get(host_tool_name, {})
    if host_tool_name == "scan_with_zap":
        has_error = isinstance(result, dict) and bool(result.get("error"))
        print(f"{'❌' if has_error else '✅'} [ZAP_CHECKPOINT] completed end-to-end")
    return result


def run_iterative_mcp_loop(user_input: str) -> Dict[str, Any]:
    # ✅ HANDLE PASTED FILE CONTENT SAFELY
    if not user_input.startswith("http") and not os.path.exists(user_input):
        print("[AI_LOOP] Detected raw content → converting to temp file")

        temp_dir = "/workspace/temp_scans"
        os.makedirs(temp_dir, exist_ok=True)

        file_name = f"scan_{uuid.uuid4().hex}.py"
        temp_path = os.path.join(temp_dir, file_name)

        with open(temp_path, "w") as f:
            f.write(user_input)

        print(f"[AI_LOOP] Temp file created: {temp_path}")

        user_input = temp_path  # ✅ IMPORTANT: replace input with path

    initial_input: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": """
You are a strict cybersecurity orchestration agent.

YOU MUST FOLLOW THESE RULES:

1) If input starts with "http":
   → ONLY call run_zap
   → arguments = {"target": "<url>"}

2) If input is a SINGLE FILE (.py, .js, etc):
   → call:
       - run_bandit
       - run_sonar
   → DO NOT call run_zap
   → DO NOT call run_safety

3) If input is a FOLDER:
   → call:
       - run_bandit
       - run_sonar
   → call run_safety ONLY if requirements.txt exists

4) NEVER mix URL tools with file tools

5) STRICT ARGUMENTS:
   - run_zap → "target"
   - others → "path"

6) You may call multiple tools across iterations.

7) AFTER all tools finish:
   → generate a clear structured cybersecurity report
   → DO NOT hallucinate missing scans
   → DO NOT invent vulnerabilities

Be precise and strict.
"""
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_input  # ✅ now it may be a temp file path
                }
            ],
        },
    ]

    print(f" [AI_LOOP] started target={user_input}")

    aggregated_results: Dict[str, Any] = {}
    iteration_count = 0
    final_report = ""
    previous_response_id = None
    next_input: Any = initial_input

    try:
        while iteration_count < MCP_LOOP_MAX_STEPS:
            iteration_count += 1

            completion = call_openai_with_tools(
                input_payload=next_input,
                previous_response_id=previous_response_id,
            )

            previous_response_id = completion.id

            response_items = list(getattr(completion, "output", []) or [])
            tool_calls = [
                item for item in response_items
                if getattr(item, "type", "") == "function_call"
            ]

            if iteration_count == 1:
                if tool_calls:
                    print(f" [AI_LOOP] iter=1 tool-calling enabled ({len(tool_calls)} call(s))")
                else:
                    print(" [AI_LOOP] iter=1 no tool calls → direct answer")

            # ✅ IF NO TOOL → FINAL REPORT
            if not tool_calls:
                final_report = completion.output_text or ""
                break

            selected_tools = [getattr(t, "name", "") for t in tool_calls]
            print(f" [AI_LOOP] iter={iteration_count} tools={selected_tools}")

            next_input = []

            for tool_call in tool_calls:
                tool_name = getattr(tool_call, "name", "")

                try:
                    tool_args = json.loads(getattr(tool_call, "arguments", "") or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                print(f" [AI_LOOP] tool={tool_name} args={tool_args}")

                tool_result = execute_mcp_tool(tool_name, tool_args)

                if isinstance(tool_result, dict) and tool_result.get("error"):
                    print(f" ❌ [AI_LOOP] {tool_name} failed: {tool_result.get('error')}")
                else:
                    print(f" ✅ [AI_LOOP] {tool_name} executed")

                aggregated_results.setdefault(tool_name, []).append({
                    "arguments": tool_args,
                    "result": tool_result,
                })

                next_input.append({
                    "type": "tool_result",
                    "tool_call_id": getattr(tool_call, "call_id", ""),
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(tool_result)
                        }
                    ]
                })

    finally:
        print("────────── [AI_LOOP] END RUN ──────────")

    if not final_report:
        final_report = "No final report generated."

    return {
        "final_report": final_report,
        "results": aggregated_results,
        "iterations": iteration_count,
    }
def save_content_to_temp_file(content: str) -> str:
    temp_dir = "/workspace/temp_scans"
    os.makedirs(temp_dir, exist_ok=True)

    file_name = f"scan_{uuid.uuid4().hex}.py"
    file_path = os.path.join(temp_dir, file_name)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"[TEMP FILE] Created: {file_path}")

    return file_path


# Interpret Endpoint
@app.post("/interpret")
def interpret(request: UserRequest):

    messages = [
        {
            "role": "system",
            "content": """
You are a cybersecurity decision agent.

You MUST return ONLY valid JSON.
Do NOT return explanations.
Do NOT return markdown.
Do NOT return text before or after JSON.

Return JSON in EXACTLY this format:

{
  "tools": [
    {
      "name": "tool_name",
      "arguments": { ... }
    }
  ]
}

STRICT TOOL ARGUMENT RULES:

1) If input starts with "http":
   - Use tool name: "scan_with_zap"
   - Arguments MUST be:
     {
       "target": "<full_url>"
     }

2) If input is a single Python file (ends with .py):
   - Use:
     - "scan_with_bandit"
     - "scan_with_sonar"
   - Arguments MUST be:
     {
       "path": "<file_path>"
     }

3) If input is a local project folder:
   - Use:
     - "scan_with_bandit"
     - "scan_with_sonar"
     - "scan_with_safety"
   - Arguments MUST be:
     {
       "path": "<folder_path>"
     }

4) NEVER use "path" for scan_with_zap.
5) NEVER use "target" for bandit, sonar, or safety.
6) Never call ZAP for local filesystem paths.

Return ONLY the JSON object.
"""
        },
        {"role": "user", "content": request.input}
    ]

    response = call_gpt(messages)

    return json.loads(response)

#generate report
@app.post("/generate_report")
def generate_report(request: ReportRequest):

    messages = [
       {
 "role": "system",
 "content": """
You are a senior cybersecurity analyst and penetration tester.

Your task is to generate a highly professional, industry-grade security assessment report based on automated scan results.

The report MUST follow best practices used in real-world penetration testing reports and align with OWASP Top 10 standards.

---------------------------------------
REPORT STRUCTURE (MANDATORY)
---------------------------------------

1. Executive Summary
- Provide a clear, concise overview of the security posture.
- Highlight the most critical risks.
- Explain overall system risk level (Low / Medium / High / Critical).

2. Risk Overview
- Summarize the number of findings by severity:
  Critical, High, Medium, Low, Informational
- Provide a short explanation of what these risks mean for the system.

3. Detailed Findings

Group vulnerabilities STRICTLY by severity in this order:
- Critical Vulnerabilities
- High Vulnerabilities
- Medium Vulnerabilities
- Low Vulnerabilities
- Informational Findings

For EACH finding, use this format:

### Finding <number> — <Vulnerability Name>

Severity: <Critical / High / Medium / Low / Informational>

CVSS Score (estimated): <0.0 – 10.0>

OWASP Category:
- Map the vulnerability to OWASP Top 10 (e.g., A01: Broken Access Control, A03: Injection, etc.)

Affected Component:
<file path / URL / module>

Description:
- Explain the vulnerability clearly
- Include why it is dangerous
- Mention how it occurs

Impact:
- Describe what an attacker can achieve
- Include technical and business impact

Proof of Concept (if possible):
- Briefly describe how it could be exploited

Recommended Remediation:
- Provide clear, actionable fix steps
- Include best practices

---------------------------------------

4. Recommendations (Global)

- Provide general security improvements
- Suggest secure coding practices
- Mention dependency updates, input validation, authentication, etc.

---------------------------------------

5. Conclusion

- Summarize overall system security
- Highlight urgency of fixing critical issues

---------------------------------------

IMPORTANT RULES:

- Use professional, formal language (like a real pentest report)
- Do NOT invent vulnerabilities — only use provided scan results
- If scan results are limited, infer responsibly but do not hallucinate
- Ensure clarity and readability for both technical and non-technical stakeholders
- Keep formatting clean and structured
"""
      },
        {
            "role": "user",
            "content": f"""
User Input:
{request.input}

Scan Results:
{json.dumps(request.results, indent=2)}

Generate a complete professional penetration testing report using the scan results.
Ensure all vulnerabilities are categorized, explained, and mapped to OWASP Top 10 with CVSS estimation.
"""
        }
    ]

    report = call_gpt(messages)

    pdf_path = generate_pdf(report)

    return {
        "final_report": report,
        "pdf_report": pdf_path
    }


@app.post("/analyze_iterative")
def analyze_iterative(request: IterativeScanRequest):
    loop_output = run_iterative_mcp_loop(request.input)

    # 🔥 Use your professional report generator
    report_response = generate_report(
        ReportRequest(
            input=request.input,
            results=loop_output["results"]
        )
    )

    return {
        "final_report": report_response["final_report"],
        "pdf_report": report_response["pdf_report"],
        "results": loop_output["results"],
        "iterations": loop_output["iterations"],
    }


# Download Report Endpoint
@app.get("/download_report")
def download_report(path: str):
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="security_report.pdf"
    )