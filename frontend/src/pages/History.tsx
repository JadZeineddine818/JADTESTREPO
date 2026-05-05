// src/pages/History.tsx
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

export default function History() {
  const navigate = useNavigate();
  const [scans, setScans] = useState<any[]>([]);

  useEffect(() => {
  const token = localStorage.getItem("token");

  fetch("http://localhost:8000/scans", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  })
    .then((res) => res.json())
    .then((data) => {
      setScans(data);
    })
    .catch((err) => console.error("Error fetching scans:", err));
}, []);

  return (
    <div className="page">
      <h1 className="pageTitle">Scan History</h1>
      <p className="subtitle">Click a row to open scan details.</p>

      <div className="tableCard">
        <table className="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Target</th>
              <th>Input</th>
              <th>Report</th>
              <th>Status</th>
              <th>Date</th>
            </tr>
          </thead>

          <tbody>
            {scans.length === 0 ? (
              <tr>
                <td colSpan={6} className="mutedCell">
                  No scans yet. Start one from <b>New Scan</b>.
                </td>
              </tr>
            ) : (
              scans.map((s) => (
                <tr
                  key={s.id}
                  className="rowHover"
                  onClick={() => navigate(`/scan/${Number(s.id)}`)}
                >
                  <td className="mono">#{s.id}</td>
                  <td className="truncate">{s.target}</td>
                  <td>{s.input}</td>
                  <td>{s.report}</td>
                  <td>
                    <span className={`pill ${s.status}`}>{s.status}</span>
                  </td>
                  <td>{s.date}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}