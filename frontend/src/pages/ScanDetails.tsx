import { useNavigate, useParams } from "react-router-dom";
import { useStore, type Severity, type VulnerabilityFinding } from "../data/store";
import { useEffect, useState } from "react";

function sevClass(sev: Severity) {
  if (sev === "Critical") return "sev sevCritical";
  if (sev === "High") return "sev sevHigh";
  if (sev === "Medium") return "sev sevMedium";
  if (sev === "Low") return "sev sevLow";
  return "sev sevInfo";
}

export default function ScanDetails() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { scans } = useStore();

  const [apiScan, setApiScan] = useState<any>(null);

  // 🔥 FETCH FROM BACKEND
  useEffect(() => {
    const token = localStorage.getItem("token");

    fetch(`http://localhost:8000/scan/${id}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setApiScan(data);
      })
      .catch((err) => {
        console.error("Error fetching scan:", err);
      });
  }, [id]);

  // 🔥 FALLBACK TO STORE (SAFE)
  const storeScan = scans.find((s) => String(s.id) === String(id));

  const scan = apiScan || storeScan;

  if (!scan) {
    return (
      <div className="page">
        <div className="rowBetween">
          <div>
            <h1 className="pageTitle">Scan Details</h1>
            <p className="subtitle">Scan not found.</p>
          </div>
          <button className="btn" onClick={() => navigate("/history")}>
            Back to History
          </button>
        </div>
      </div>
    );
  }

  const findings: VulnerabilityFinding[] = scan.findings || [];

  const handleDownload = () => {
    if (!scan.pdfReport) return;

    const url = `http://localhost:8005/download_report?path=${scan.pdfReport}`;
    window.open(url, "_blank");
  };

  return (
    <div className="page">
      <div className="rowBetween">
        <div>
          <h1 className="pageTitle">Scan Details</h1>
          <p className="subtitle">Professional structured findings.</p>
        </div>
        <button className="btn" onClick={() => navigate("/history")}>
          Back
        </button>
      </div>

      {/* Scan Metadata */}
      <div className="card">
        <div className="kvGrid">
          <div className="kv">
            <div className="k">ID</div>
            <div className="v mono">#{scan.id}</div>
          </div>

          <div className="kv">
            <div className="k">Target</div>
            <div className="v">{scan.target || scan.input}</div>
          </div>

          <div className="kv">
            <div className="k">Input Type</div>
            <div className="v">{scan.inputType?.toUpperCase() || "URL"}</div>
          </div>

          <div className="kv">
            <div className="k">Report</div>
            <div className="v">{scan.reportType ?? "Executive"}</div>
          </div>

          <div className="kv">
            <div className="k">Status</div>
            <div className="v">
              <span className={`pill ${scan.status}`}>{scan.status}</span>
            </div>
          </div>

          <div className="kv">
            <div className="k">Created</div>
            <div className="v">{scan.createdAt || scan.date}</div>
          </div>
        </div>

        {/* DOWNLOAD BUTTON */}
        {scan.pdfReport && (
          <div style={{ marginTop: 20 }}>
            <button className="btn primary" onClick={handleDownload}>
              Download Report
            </button>
          </div>
        )}
      </div>

      {/* Findings Section */}
      {scan.inputType !== "question" && (
        <div className="card">
          <div className="rowBetween">
            <h2 className="sectionTitle">Findings ({findings.length})</h2>
          </div>

          {findings.length === 0 ? (
            <p className="subtitle" style={{ marginTop: 10 }}>
              No findings detected.
            </p>
          ) : (
            <div className="findingsList">
              {findings.map((f, idx) => (
                <div key={f.findingId ?? idx} className="findingCard">
                  <div className="rowBetween">
                    <div>
                      <div className="findingTitle">{f.title}</div>
                      <div className="findingMeta">
                        <span className={sevClass(f.severity)}>{f.severity}</span>
                        <span className="metaDot">•</span>
                        <span className="muted">{f.findingId}</span>
                      </div>
                    </div>
                    <div className="muted">
                      {f.cvss ? `CVSS ${f.cvss.score.toFixed(1)}` : "CVSS -"}
                    </div>
                  </div>

                  <div className="twoCol">
                    <div>
                      <div className="k">CWE</div>
                      <div className="v">
                        {f.cwe ? `${f.cwe.id} — ${f.cwe.name}` : "-"}
                      </div>
                    </div>
                    <div>
                      <div className="k">OWASP</div>
                      <div className="v">{f.owasp?.top10 ?? "-"}</div>
                    </div>
                  </div>

                  <div className="block">
                    <div className="k">Description</div>
                    <div className="v">{f.description}</div>
                  </div>

                  <div className="twoCol">
                    <div className="block">
                      <div className="k">Impact</div>
                      <div className="v">{f.impact}</div>
                    </div>
                    <div className="block">
                      <div className="k">Recommendation</div>
                      <div className="v">{f.recommendation}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI REPORT */}
      {(scan.aiAnswer || scan.report) && (
        <div className="card" style={{ marginTop: 20 }}>
          <h2 className="sectionTitle">AI Security Analysis Report</h2>
          <div
            style={{
              marginTop: 15,
              whiteSpace: "pre-wrap",
              lineHeight: 1.6,
            }}
          >
            {scan.aiAnswer || scan.report}
          </div>
        </div>
      )}
    </div>
  );
}