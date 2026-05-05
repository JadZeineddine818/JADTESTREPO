// src/pages/Dashboard.tsx
import { useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

type DashboardSummary = {
  totalScans: number;
  completed: number;
  failed: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  recent: {
    id: string | "-";
    target: string;
    status: "Idle" | "Scanning" | "Completed" | "Failed";
    risk: "Low" | "Medium" | "High" | "Critical";
  };
};

const emptySummary: DashboardSummary = {
  totalScans: 0,
  completed: 0,
  failed: 0,
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
  recent: { id: "-", target: "-", status: "Idle", risk: "Low" },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }

    fetch("http://localhost:8000/dashboard", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load dashboard");
        return res.json();
      })
      .then((data: DashboardSummary) => setSummary(data))
      .catch((err) => {
        console.error("Error fetching dashboard summary:", err);
        setSummary(emptySummary);
      })
      .finally(() => setLoading(false));
  }, []);

  const totalFindings = useMemo(
    () => summary.critical + summary.high + summary.medium + summary.low,
    [summary.critical, summary.high, summary.medium, summary.low]
  );

  return (
    <div className="page">
      <div className="row spaceBetween">
        <div>
          <h1 className="pageTitle">Dashboard</h1>
          <p className="subtitle">
            Overview based on persisted scan records from the backend database.
          </p>
        </div>

        <div className="row">
          <button className="btn" onClick={() => navigate("/history")}>
            View History
          </button>
          <button className="btn primary" onClick={() => navigate("/new-scan")}>
            New Scan
          </button>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ marginTop: 16 }}>
          <p className="subtitle" style={{ margin: 0 }}>
            Loading dashboard data...
          </p>
        </div>
      )}

      {/* KPI cards */}
      <div className="kpiGrid">
        <div className="kpiCard">
          <div className="kpiLabel">Total Scans</div>
          <div className="kpiValue">{summary.totalScans}</div>
        </div>
        <div className="kpiCard">
          <div className="kpiLabel">Completed</div>
          <div className="kpiValue">{summary.completed}</div>
        </div>
        <div className="kpiCard">
          <div className="kpiLabel">Failed</div>
          <div className="kpiValue">{summary.failed}</div>
        </div>
        <div className="kpiCard">
          <div className="kpiLabel">Total Findings</div>
          <div className="kpiValue">{totalFindings}</div>
        </div>
      </div>

      {/* Severity Distribution */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="row spaceBetween">
          <h2 className="sectionTitle" style={{ margin: 0 }}>
            Severity Distribution
          </h2>
          <span className="smallMuted">Derived from findings[] across all scans</span>
        </div>

        {totalFindings === 0 ? (
          <p style={{ marginTop: 12, opacity: 0.75 }}>
            No findings yet. Run a URL/Upload scan (Completed) to populate this distribution.
          </p>
        ) : (
          <div style={{ marginTop: 12 }}>
            <div className="sevGrid">
              <div className="sevBox">
                <div className="sevLabel">Critical</div>
                <div className="sevNum">{summary.critical}</div>
              </div>
              <div className="sevBox">
                <div className="sevLabel">High</div>
                <div className="sevNum">{summary.high}</div>
              </div>
              <div className="sevBox">
                <div className="sevLabel">Medium</div>
                <div className="sevNum">{summary.medium}</div>
              </div>
              <div className="sevBox">
                <div className="sevLabel">Low</div>
                <div className="sevNum">{summary.low}</div>
              </div>
            </div>

            {/* bars */}
            <div className="barWrap">
              <Bar label="Critical" value={summary.critical} total={totalFindings} />
              <Bar label="High" value={summary.high} total={totalFindings} />
              <Bar label="Medium" value={summary.medium} total={totalFindings} />
              <Bar label="Low" value={summary.low} total={totalFindings} />
            </div>
          </div>
        )}
      </div>

      {/* Latest Scan */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="row spaceBetween">
          <div>
            <h2 className="sectionTitle" style={{ margin: 0 }}>
              Latest Scan
            </h2>
            <p className="subtitle" style={{ marginTop: 6 }}>
              Most recent scan snapshot.
            </p>
          </div>

          <div className="row">
            <button
              className="btn"
              disabled={summary.recent.id === "-"}
              onClick={() => navigate(`/scan/${summary.recent.id}`)}
            >
              View details
            </button>

            <button
              className="btn primary"
              disabled={summary.recent.id === "-"}
              onClick={() => navigate(`/reports/${summary.recent.id}`)}
            >
              View report
            </button>
          </div>
        </div>

        <div className="kvGrid" style={{ marginTop: 10 }}>
          <div className="kv">
            <div className="k">ID</div>
            <div className="v mono">{summary.recent.id === "-" ? "-" : `#${summary.recent.id}`}</div>
          </div>
          <div className="kv">
            <div className="k">Target</div>
            <div className="v">{summary.recent.target}</div>
          </div>
          <div className="kv">
            <div className="k">Status</div>
            <div className="v">
              <span className={`pill ${summary.recent.status}`}>{summary.recent.status}</span>
            </div>
          </div>
          <div className="kv">
            <div className="k">Risk</div>
            <div className="v">
              <span className={riskClass(summary.recent.risk)}>{summary.recent.risk}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function riskClass(risk: "Low" | "Medium" | "High" | "Critical") {
  if (risk === "Critical") return "sev sevCritical";
  if (risk === "High") return "sev sevHigh";
  if (risk === "Medium") return "sev sevMedium";
  return "sev sevLow";
}

function Bar({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((value / total) * 100);
  return (
    <div className="barRow">
      <div className="barLabel">{label}</div>
      <div className="barTrack">
        <div className="barFill" style={{ width: `${pct}%` }} />
      </div>
      <div className="barPct">{pct}%</div>
    </div>
  );
}