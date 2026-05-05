from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
import json
from typing import Any, Dict, List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI
from pdf_generator import generate_pdf
from datetime import datetime


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1")
# OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
# OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


MCP_LOOP_MAX_STEPS = int(os.getenv("MCP_LOOP_MAX_STEPS", "6"))
TOOL_REQUEST_TIMEOUT_DEFAULT = int(os.getenv("MCP_TOOL_REQUEST_TIMEOUT", "1200"))
# Sonar: scanner capped at 120s server-side + sleep + issues API — keep HTTP slack here.
TOOL_REQUEST_TIMEOUT_SONAR = int(os.getenv("MCP_TOOL_REQUEST_TIMEOUT_SONAR", "120"))
USE_MCP_DIRECT = os.getenv("USE_MCP_DIRECT", "false").lower() == "true"

# ollama_client = OpenAI(
#     base_url=OLLAMA_BASE_URL,
#     api_key=OLLAMA_API_KEY,
# )
client = OpenAI()

class UserRequest(BaseModel):
    input: str


class ReportRequest(BaseModel):
    input: str
    results: dict


class IterativeScanRequest(BaseModel):
    input: str
    report_type: str = "Executive"


def _log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def _extract_final_text(completion: Any) -> str:
    """Resolve assistant text from Responses API (output_text or nested content)."""
    direct = getattr(completion, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct

    chunks: List[str] = []
    for item in getattr(completion, "output", []) or []:
        for block in getattr(item, "content", None) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text:
                chunks.append(text)
        item_text = getattr(item, "text", None)
        if isinstance(item_text, str) and item_text:
            chunks.append(item_text)

    joined = "".join(chunks).strip()
    if joined:
        _log("⚠️ [AI_LOOP] output_text empty; used fallback text extraction from output blocks")
    return joined


def _format_tool_outcomes_markdown(aggregated_results: Dict[str, Any]) -> str:
    lines: List[str] = ["### Tool outcomes", ""]
    if not aggregated_results:
        lines.append("- No tools were executed.")
        return "\n".join(lines)

    for tool_name in sorted(aggregated_results.keys()):
        runs = aggregated_results.get(tool_name) or []
        if not runs:
            lines.append(f"- **{tool_name}**: Unknown (no run record)")
            continue
        last = runs[-1].get("result")
        if isinstance(last, dict) and last.get("error"):
            err = last.get("error")
            detail = (
                last.get("reason")
                or last.get("details")
                or last.get("body")
                or ""
            )
            detail_s = str(detail).strip().replace("\n", " ")
            if len(detail_s) > 400:
                detail_s = detail_s[:400] + "…"
            extra = f" — {detail_s}" if detail_s else ""
            skipped = last.get("skipped")
            if skipped:
                extra = (extra + " (skipped)") if extra else " (skipped)"
            lines.append(f"- **{tool_name}**: Failed — {err}{extra}")
        else:
            lines.append(f"- **{tool_name}**: Succeeded")

    return "\n".join(lines)


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


def _synthesize_fallback_report(
    user_input: str,
    aggregated_results: Dict[str, Any],
    report_type: str,
) -> str:
    try:
        payload = json.dumps(aggregated_results, indent=2, default=str)
    except TypeError:
        payload = str(aggregated_results)
    max_len = 120000
    if len(payload) > max_len:
        payload = payload[:max_len] + "\n... (truncated)"

    messages = [
        {
            "role": "system",
            "content": (
                "You write cybersecurity assessment reports from tool JSON only. "
                "Output markdown. Follow the Executive vs Technical structure requested by the user. "
                "Always include ### Tool outcomes: list run_bandit, run_sonar, run_safety, run_zap "
                "as Succeeded or Failed with reasons quoted from error/details fields."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Report mode: {report_type}\n\n"
                f"Scan target / input:\n{user_input}\n\n"
                f"Aggregated tool results:\n```json\n{payload}\n```\n\n"
                "Write the full report. Clearly explain any failed or skipped tools."
            ),
        },
    ]
    text = call_gpt(messages)
    return (text or "").strip()


def call_openai_with_tools(
    input_payload: Any,
    previous_response_id: str = None
) -> Any:
    request_kwargs: Dict[str, Any] = {
        "model": OPENAI_MODEL,
        "input": input_payload,
        "tools": MCP_TOOL_SCHEMAS,
    }
    if previous_response_id:
        request_kwargs["previous_response_id"] = previous_response_id
    return client.responses.create(**request_kwargs)


def execute_mcp_tool(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://mcp_server:8006/execute",   # ✅ NEW TARGET
            json={
                "tool": tool_name,
                "arguments": tool_args
            },
            timeout=600
        )

        return response.json()

    except Exception as e:
        return {
            "error": "MCP call failed",
            "details": str(e)
        }

def execute_mcp_tool_direct(tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """
    NEW MCP execution (direct via MCP server)
    SAFE: does not replace old logic
    """
    try:
        result = mcp_client.call_tool(tool_name, tool_args)
        return result
    except Exception as e:
        return {
            "error": "MCP direct execution failed",
            "details": str(e)
        }


def run_iterative_mcp_loop(user_input: str, report_type: str = "Executive") -> Dict[str, Any]:
    mode = (report_type or "Executive").strip().lower()
    if mode == "technical":
        reporting_instruction = (
            "Generate a TECHNICAL report. Output must be markdown and must strictly follow this structure:\n"
            "# Technical Security Report\n"
            "## Executive Summary\n"
            "- Total vulnerabilities: <number>\n"
            "- High-risk issues: <number and short statement>\n"
            "- Overall risk level: <Critical|High|Medium|Low>\n"
            "## Technical Details\n"
            "For each finding include:\n"
            "### Finding <number> - <title>\n"
            "- Tool: <tool>\n"
            "- Severity: <severity>\n"
            "- Location/Component: <path or url>\n"
            "- AI Explanation: <detailed technical explanation>\n"
            "- Fix Suggestion: <specific remediation steps>\n"
            "Include the full vulnerability list from available tool outputs.\n"
            "Always include ### Tool outcomes (Bandit, Sonar, Safety, ZAP): Succeeded or Failed with exact reasons from tool outputs.\n"
            "If run_sonar returns error, skipped, or timeout: call it at most once; do not retry Sonar; continue and still deliver the full report.\n"
            "If a tool failed, also add ### Tool Failures with bullets mirroring errors.\n"
        )
    else:
        reporting_instruction = (
            "Generate an EXECUTIVE report. Output must be markdown and must strictly follow this structure:\n"
            "# Executive Security Report\n"
            "## Executive Summary\n"
            "- Total vulnerabilities: <number>\n"
            "- High-risk issues: <number and business impact>\n"
            "- Overall risk level: <Critical|High|Medium|Low>\n"
            "## Technical Details\n"
            "Provide only a concise top-findings view (not exhaustive), and for each include:\n"
            "### Finding <number> - <title>\n"
            "- Severity: <severity>\n"
            "- AI Explanation: <short plain-language explanation>\n"
            "- Fix Suggestion: <practical next step>\n"
            "Always include ### Tool outcomes (Bandit, Sonar, Safety, ZAP): Succeeded or Failed with reasons.\n"
            "If run_sonar fails or times out: do not call run_sonar again; finish the report with other tools.\n"
            "If any tool failed, include ### Tool Failures with bullets.\n"
        )

    initial_input: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a cybersecurity analysis agent. "
                "Use available tools when required. "
                "For URLs use run_zap(target). "
                "For local code paths use run_bandit/run_sonar/run_safety with path. "
                "You may call multiple tools across multiple rounds, then produce a final structured report. "
                "You must NOT generate any report. Only decide tools, execute them, and return results."
            ),
        },
        {"role": "user", "content": user_input},
    ]

    # One-line startup trace for quick loop visibility.
    _log(f"🔎 [AI_LOOP] started target={user_input} report_type={report_type}")

    aggregated_results: Dict[str, Any] = {}
    iteration_count = 0
    final_report = ""
    previous_response_id = None
    next_input: Any = initial_input

    try:
        while iteration_count < MCP_LOOP_MAX_STEPS:
            iteration_count += 1
            completion = call_openai_with_tools(    ##first call to model ai decisioon for tools
                input_payload=next_input,
                previous_response_id=previous_response_id,
            )
            previous_response_id = completion.id

            response_items = list(getattr(completion, "output", []) or [])
            tool_calls = [item for item in response_items if getattr(item, "type", "") == "function_call"]

            if iteration_count == 1:
                tool_call_count = len(tool_calls)
                if tool_call_count > 0:
                    _log(f"✅ [AI_LOOP] iter=1 tool-calling enabled ({tool_call_count} call(s))")
                else:
                    _log("⚠️ [AI_LOOP] iter=1 no tool calls; model returned direct answer")

            has_tool_results = bool(aggregated_results)

            # If no tools selected AND no results yet → force loop
            if not tool_calls and not has_tool_results:
               _log("⚠️ [AI_LOOP] no tools executed yet, forcing another iteration")
               continue

            # 🔥 If ZAP failed → DO NOT STOP (force retry)
            zap_failed = False
            if "run_zap" in aggregated_results:
              last = aggregated_results["run_zap"][-1]["result"]
              if isinstance(last, dict) and last.get("error"):
                zap_failed = True

            if zap_failed:
              _log("⚠️ [AI_LOOP] ZAP failed → forcing retry instead of exiting")
              continue

            if not tool_calls:
              if has_tool_results:
                final_report = _extract_final_text(completion)
                break
              else:
                 _log("⚠️ AI returned no tools and no results → retry")
                 continue

            selected_tools = [getattr(tool_call, "name", "") for tool_call in tool_calls]
            _log(f"🧠 [AI_LOOP] iter={iteration_count} LLM selected tools={selected_tools}")

            next_input = []
            for tool_call in tool_calls:
                tool_name = getattr(tool_call, "name", "")
                try:
                    tool_args = json.loads(getattr(tool_call, "arguments", "") or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                _log(
                    f"🧠 [AI_LOOP] tool={tool_name} args={json.dumps(tool_args, ensure_ascii=False)}"
                )

                if USE_MCP_DIRECT:
                    tool_result = execute_mcp_tool_direct(tool_name, tool_args)
                else:
                    tool_result = execute_mcp_tool(tool_name, tool_args)
                if isinstance(tool_result, dict) and tool_result.get("error"):
                    _log(f"❌ [AI_LOOP] {tool_name} failed: {tool_result.get('error')}")
                else:
                    _log(f"✅ [AI_LOOP] {tool_name} executed")
                aggregated_results.setdefault(tool_name, []).append(
                    {
                        "arguments": tool_args,
                        "result": tool_result,
                    }
                )
                next_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(tool_call, "call_id", ""),
                        "output": json.dumps(tool_result),
                    }
                )
    finally:
        # End-of-run delimiter so consecutive analyze runs are easy to separate in logs.
        _log("────────── [AI_LOOP] END RUN ──────────")

    _PLACEHOLDER = "Tool loop ended before final response."
    if not final_report.strip() or final_report.strip() == _PLACEHOLDER:
        synthesized = _synthesize_fallback_report(
            user_input, aggregated_results, report_type
        )
        if synthesized:
            final_report = synthesized
        elif not final_report.strip():
            final_report = _PLACEHOLDER

    outcomes_md = _format_tool_outcomes_markdown(aggregated_results)
    if outcomes_md and "### Tool outcomes" not in final_report:
        final_report = (final_report or "").rstrip() + "\n\n" + outcomes_md

    return {
        "final_report": final_report,
        "results": aggregated_results,
        "iterations": iteration_count,
    }


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

5. The report must be readable for humans and structured clearly.
"""
      },
        {
            "role": "user",
            "content": f"""
User Input:
{request.input}

Scan Results:
{json.dumps(request.results, indent=2)}

Generate the report strictly following the required structure.
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

    loop_output = run_iterative_mcp_loop(request.input, request.report_type)

    # ✅ FIRST generate report
    report_response = generate_report(
        ReportRequest(
            input=request.input,
            results=loop_output["results"]
        )
    )

    # ✅ THEN generate PDF
    pdf_path = generate_pdf(report_response["final_report"])

    return {
        "final_report": report_response["final_report"],
        "pdf_report": pdf_path,
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