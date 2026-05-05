import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useStore } from "../data/store";
import type { ReportType, ScanInputType } from "../data/store";

export default function NewScan() {
  const navigate = useNavigate();

  const {
    addScan,
    completeScanWithFindings,
    setAiAnswer
  } = useStore();

  const [inputType, setInputType] = useState<ScanInputType>("url");
  const [reportType, setReportType] = useState<ReportType>("Executive");
  const [url, setUrl] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [question, setQuestion] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
  const [loading, setLoading] = useState(false);

  // ✅ NEW STATE (SAFE ADD)
  const [scanResult, setScanResult] = useState<any>(null);

  const formatErrorDetail = (detail: unknown): string => {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((x: { msg?: string }) => x?.msg ?? JSON.stringify(x))
        .join("\n");
    }
    if (detail != null && typeof detail === "object") {
      return JSON.stringify(detail);
    }
    return "Backend returned an error.";
  };

  const isJwtUsable = (token: string) => {
    const parts = token.split(".");
    if (parts.length !== 3) return false;

    try {
      const payload = JSON.parse(atob(parts[1]));
      if (typeof payload?.exp !== "number") return true;
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  };

  const canStart = useMemo(() => {
    if (inputType === "url") return url.trim().length > 0;
    if (inputType === "projectPath") return projectPath.trim().length > 0;
    if (inputType === "fileContent") return fileContent.trim().length > 0;
    if (inputType === "upload") return files.length > 0;
    if (inputType === "question") return question.trim().length > 0;
    return false;
  }, [inputType, url, projectPath, fileContent, files, question]);

  const handleStart = async () => {
    if (!canStart) return;

    let target = "";

    if (inputType === "url") target = url.trim();
    if (inputType === "projectPath") target = projectPath.trim();
    if (inputType === "fileContent") target = fileContent.trim();
    if (inputType === "upload") target = files.length === 1 ? files[0].name : `${files.length} files uploaded`;
    if (inputType === "question") target = question.trim();

    const rpt: ReportType | null =
      inputType === "question" ? null : reportType;

    const id = addScan(inputType, target, rpt);

    setLoading(true);

    try {
      const token = localStorage.getItem("token");
      if (!token || !isJwtUsable(token)) {
        localStorage.removeItem("token");
        setAiAnswer(id, "Your session is missing. Please log in.");
        navigate("/login");
        return;
      }

      let response: Response;

      if (inputType === "upload") {
        const formData = new FormData();
        for (const f of files) {
          const relativePath =
            (f as File & { webkitRelativePath?: string }).webkitRelativePath ||
            f.name;
          formData.append("files", f, relativePath);
        }
        formData.append("report_type", reportType || "Executive");
        response = await fetch("http://localhost:8000/upload_and_analyze", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        });
      } else {
        response = await fetch("http://localhost:8000/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            input: target,
            report_type: reportType || "Executive",
          }),
        });
      }

      const data = await response.json();

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem("token");
          setAiAnswer(id, "Session expired. Please log in again.");
          navigate("/login");
          return;
        }
        const errMsg = formatErrorDetail(data.detail);
        setAiAnswer(id, errMsg);
        setScanResult({
          final_report: errMsg,
          pdf_report: null,
          results: {},
          iterations: 0,
        });
        return;
      }

      const realId = data.id ?? id;

      setAiAnswer(
        realId,
        data.final_report || "No report returned from backend."
      );

      completeScanWithFindings(
        realId,
        [],
        data.pdf_report
      );

      // ✅ REPLACED NAVIGATION WITH LOCAL DISPLAY
      setScanResult(data);

    } catch (error) {
      console.error("API error:", error);
      setAiAnswer(id, "Error connecting to backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="pageHeader">
        <div>
          <h1 className="pageTitle">New Orchestrated Scan</h1>
          <p className="subtitle">
            Real backend connected.
          </p>
        </div>
      </div>

      <div className="segmentedWrap">
        <button
          className={inputType === "url" ? "segBtn active" : "segBtn"}
          onClick={() => setInputType("url")}
        >
          URL Scan
        </button>

        <button
          className={inputType === "upload" ? "segBtn active" : "segBtn"}
          onClick={() => setInputType("upload")}
        >
          Upload Code/File
        </button>
        
        <button
          className={inputType === "projectPath" ? "segBtn active" : "segBtn"}
          onClick={() => setInputType("projectPath")}
        >
          Project Folder Path
        </button>

        <button
          className={inputType === "fileContent" ? "segBtn active" : "segBtn"}
          onClick={() => setInputType("fileContent")}
        >
          Paste File Content
        </button>

        <button
          className={inputType === "question" ? "segBtn active" : "segBtn"}
          onClick={() => setInputType("question")}
        >
          Ask a Question
        </button>
      </div>

      {inputType === "url" && (
        <div className="card formCard">
          <label className="label">Target URL</label>
          <input
            className="input"
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
      )}

      {inputType === "upload" && (
        <div className="card formCard">
          <label className="label">Upload Mode</label>
          <div className="segmentedWrap" style={{ marginBottom: 12 }}>
            <button
              className={uploadMode === "file" ? "segBtn active" : "segBtn"}
              onClick={() => { setUploadMode("file"); setFiles([]); }}
            >
              Single File
            </button>
            <button
              className={uploadMode === "folder" ? "segBtn active" : "segBtn"}
              onClick={() => { setUploadMode("folder"); setFiles([]); }}
            >
              Folder
            </button>
          </div>
          <label className="label">
            {uploadMode === "file" ? "Upload File (.py, .zip, …)" : "Upload Project Folder"}
          </label>
          {uploadMode === "file" ? (
            <input
              key="single-file-input"
              type="file"
              ref={(el) => {
                if (!el) return;
                el.removeAttribute("webkitdirectory");
                el.removeAttribute("directory");
              }}
              onChange={(e) =>
                setFiles(e.target.files ? Array.from(e.target.files) : [])
              }
            />
          ) : (
            <input
              key="folder-input"
              type="file"
              multiple
              ref={(el) => {
                if (!el) return;
                el.setAttribute("webkitdirectory", "");
                el.setAttribute("directory", "");
              }}
              onChange={(e) =>
                setFiles(e.target.files ? Array.from(e.target.files) : [])
              }
            />
          )}
          {files.length > 0 && (
            <p className="smallMuted" style={{ marginTop: 8 }}>
              {files.length} file{files.length > 1 ? "s" : ""} selected
            </p>
          )}
        </div>
      )}

      {inputType === "projectPath" && (
        <div className="card formCard">
          <label className="label">Project Folder Path</label>
          <input
            className="input"
            placeholder="C:\\Projects\\my-app"
            value={projectPath}
            onChange={(e) => setProjectPath(e.target.value)}
          />
        </div>
      )}

      {inputType === "fileContent" && (
        <div className="card formCard">
          <label className="label">Paste File Content</label>
          <textarea
            className="textarea"
            placeholder="Paste source code or file content here..."
            value={fileContent}
            onChange={(e) => setFileContent(e.target.value)}
          />
        </div>
      )}

      {inputType === "question" && (
        <div className="card formCard">
          <label className="label">Your Question</label>
          <textarea
            className="textarea"
            placeholder="Ask a security question…"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </div>
      )}

      {inputType !== "question" && (
        <div className="card formCard">
          <label className="label">Report Mode</label>
          <select
            className="select"
            value={reportType}
            onChange={(e) =>
              setReportType(e.target.value as ReportType)
            }
          >
            <option value="Executive">Executive Report</option>
            <option value="Technical">Technical Report</option>
          </select>
        </div>
      )}

      <div className="actionRow">
        <button
          className="btn primary largeBtn"
          disabled={!canStart || loading}
          onClick={handleStart}
        >
          {loading ? "Running..." : "Start Scan"}
        </button>

        <button
          className="btn ghostBtn"
          onClick={() => navigate("/history")}
        >
          View History
        </button>
      </div>

      {/* ✅ NEW RESULT DISPLAY (SAFE ADD) */}
      {scanResult && (
        <div className="card" style={{ marginTop: 20 }}>
          <h2 className="sectionTitle">Scan Result</h2>

          <div style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
            {scanResult.final_report}
          </div>

          {scanResult.pdf_report && (
            <button
              className="btn primary"
              style={{ marginTop: 15 }}
              onClick={() => {
                window.open(
                  `http://localhost:8005/download_report?path=${scanResult.pdf_report}`,
                  "_blank"
                );
              }}
            >
              Download Report
            </button>
          )}
        </div>
      )}
    </div>
  );
}