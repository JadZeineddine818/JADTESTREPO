// src/pages/Report.tsx
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useStore } from "../data/store";

export default function Report() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { scans } = useStore();

  const scan = scans.find((s) => s.id === id);

  const counts = useMemo(() => {
    const findings = scan?.findings ?? [];
    const c = { Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 };
    for (const f of findings) c[f.severity] = (c[f.severity] ?? 0) + 1;
    return c;
  }, [scan]);

  if (!scan) {
    return (
      <div className="page">
        <h1 className="pageTitle">Report</h1>
        <p className="subtitle">Scan not found.</p>
        <button className="btn" onClick={() => navigate("/history")}>Back</button>
      </div>
    );
  }

  const total = counts.Critical + counts.High + counts.Medium + counts.Low + counts.Info;

  return (
    <div className="page">
      <div className="row spaceBetween">
        <div>
          <h1 className="pageTitle">Report</h1>
          <p className="subtitle">
            {scan.reportType ?? "N/A"} report for <b className="mono">#{scan.id}</b>
          </p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => navigate(`/scan/${scan.id}`)}>Scan Details</button>
          <button className="btn" onClick={() => navigate("/history")}>History</button>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h2 className="sectionTitle" style={{ marginBottom: 10 }}>Severity Overview</h2>
          {total === 0 ? (
            <p className="subtitle">No findings for this scan.</p>
          ) : (
            <div className="reportChartRow">
              <Donut
                values={[
                  { label: "Critical", value: counts.Critical },
                  { label: "High", value: counts.High },
                  { label: "Medium", value: counts.Medium },
                  { label: "Low", value: counts.Low },
                ]}
              />
              <div className="reportLegend">
                <LegendItem label="Critical" value={counts.Critical} className="sev sevCritical" />
                <LegendItem label="High" value={counts.High} className="sev sevHigh" />
                <LegendItem label="Medium" value={counts.Medium} className="sev sevMedium" />
                <LegendItem label="Low" value={counts.Low} className="sev sevLow" />
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="sectionTitle" style={{ marginBottom: 10 }}>
            {scan.reportType === "Technical" ? "Technical Summary" : "Executive Summary"}
          </h2>

          {scan.reportType === "Technical" ? (
            <ul className="list">
              <li>Evidence is shown per finding (tool, URL/file, request/response snippet).</li>
              <li>Recommendations are concrete: encoding, headers, upgrades, monitoring.</li>
              <li>Next step: export PDF (later backend) + attach compliance mapping.</li>
            </ul>
          ) : (
            <ul className="list">
              <li>Top risks: prioritize High/Critical first.</li>
              <li>Quick wins: missing headers + dependency upgrades.</li>
              <li>Recommended action: run remediation, rescan, track trend over time.</li>
            </ul>
          )}

          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn primary" disabled>
              Export PDF (next)
            </button>
            <button className="btn" disabled>
              Export HTML (next)
            </button>
          </div>

          <p className="hint">Export buttons are disabled until backend report generator is connected.</p>
        </div>
      </div>
    </div>
  );
}

function LegendItem({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="legendItem">
      <span className={className}>{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}

/**
 * Minimal donut chart using SVG strokes.
 * We don't set colors here; we rely on CSS variables per slice.
 */
function Donut({ values }: { values: { label: string; value: number }[] }) {
  const total = values.reduce((a, b) => a + b.value, 0);
  const size = 160;
  const r = 62;
  const c = 2 * Math.PI * r;

  let offset = 0;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="donut">
      <circle cx={size / 2} cy={size / 2} r={r} className="donutTrack" />
      {values.map((v) => {
        const frac = total === 0 ? 0 : v.value / total;
        const dash = frac * c;
        const seg = (
          <circle
            key={v.label}
            cx={size / 2}
            cy={size / 2}
            r={r}
            className={`donutSlice donut_${v.label}`}
            strokeDasharray={`${dash} ${c - dash}`}
            strokeDashoffset={-offset}
          />
        );
        offset += dash;
        return seg;
      })}
      <text x="50%" y="48%" textAnchor="middle" className="donutCenter">
        {total}
      </text>
      <text x="50%" y="60%" textAnchor="middle" className="donutSub">
        findings
      </text>
    </svg>
  );
}