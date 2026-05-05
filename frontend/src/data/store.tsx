// src/data/store.tsx
import { createContext, useContext, useMemo, useState } from "react";

export type ScanStatus = "Queued" | "Scanning" | "Completed" | "Failed";
export type ScanInputType =
  | "url"
  | "upload"
  | "question"
  | "projectPath"
  | "fileContent";
export type ReportType = "Executive" | "Technical";

export type Severity = "Critical" | "High" | "Medium" | "Low" | "Info";

export type Evidence = {
  tool: "ZAP" | "Bandit" | "Safety" | "SonarQube" | "Manual";
  location?: {
    url?: string;
    file?: string;
    line?: number;
    parameter?: string;
  };
  request?: string;
  responseSnippet?: string;
  codeSnippet?: string;
};

export type VulnerabilityFinding = {
  findingId: string;
  title: string;
  severity: Severity;

  cwe?: {
    id: string;
    name: string;
    url?: string;
  };

  owasp?: {
    top10?: string;
    category?: string;
  };

  cvss?: {
    score: number;
    vector?: string;
  };

  description: string;
  impact: string;
  recommendation: string;

  confidence: "High" | "Medium" | "Low";
  tags?: string[];

  evidence: Evidence[];
};

export type ScanItem = {
  id: string;
  inputType: ScanInputType;
  target: string;
  reportType: ReportType | null;
  status: ScanStatus;
  createdAt: string;

  findings: VulnerabilityFinding[];

  aiAnswer?: string;

  aiReport?: string;

  // ✅ NEW PDF REPORT FIELD
  pdfReport?: string;
};

export type ScanSummary = {
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

type StoreState = {
  summary: ScanSummary;
  scans: ScanItem[];

  addScan: (inputType: ScanInputType, target: string, reportType: ReportType | null) => string;
  attachFileToScan: (id: string, file: File) => void;

  completeScanWithFindings: (
    id: string,
    findings: VulnerabilityFinding[],
    pdfReport?: string
  ) => void;

  failScan: (id: string) => void;

  setAiAnswer: (id: string, answer: string) => void;
  setAiReport: (id: string, report: string) => void;
};

const initialSummary: ScanSummary = {
  totalScans: 0,
  completed: 0,
  failed: 0,
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
  recent: { id: "-", target: "-", status: "Idle", risk: "Low" },
};

function nowText() {
  return new Date().toLocaleString();
}

function makeId() {
  return Math.random().toString(36).slice(2, 8).toUpperCase();
}

function riskFromFindings(findings: VulnerabilityFinding[]): ScanSummary["recent"]["risk"] {
  if (findings.some((f) => f.severity === "Critical")) return "Critical";
  if (findings.some((f) => f.severity === "High")) return "High";
  if (findings.some((f) => f.severity === "Medium")) return "Medium";
  return "Low";
}

function countsFromFindings(findings: VulnerabilityFinding[]) {
  let critical = 0, high = 0, medium = 0, low = 0;

  for (const f of findings) {
    if (f.severity === "Critical") critical++;
    else if (f.severity === "High") high++;
    else if (f.severity === "Medium") medium++;
    else if (f.severity === "Low") low++;
  }

  return { critical, high, medium, low };
}

const safeDefaultStore: StoreState = {
  summary: initialSummary,
  scans: [],
  addScan: () => "-",
  attachFileToScan: () => {},
  completeScanWithFindings: () => {},
  failScan: () => {},
  setAiAnswer: () => {},
  setAiReport: () => {},
};

const StoreContext = createContext<StoreState>(safeDefaultStore);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [summary, setSummary] = useState<ScanSummary>(initialSummary);
  const [scans, setScans] = useState<ScanItem[]>([]);

  const addScan = (inputType: ScanInputType, target: string, reportType: ReportType | null) => {
    const id = makeId();

    const item: ScanItem = {
      id,
      inputType,
      target,
      reportType,
      status: "Scanning",
      createdAt: nowText(),
      findings: [],
      aiAnswer: inputType === "question" ? "Answer will appear here after you ask." : undefined,
    };

    setScans((prev) => [item, ...prev]);

    setSummary((prev) => ({
      ...prev,
      recent: { id, target, status: "Scanning", risk: "Low" },
    }));

    return id;
  };

  const attachFileToScan = (id: string, file: File) => {
    setScans((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, target: file.name || "Uploaded File", inputType: "upload" } : s
      )
    );
  };

  const completeScanWithFindings = (
    id: string,
    findings: VulnerabilityFinding[],
    pdfReport?: string
  ) => {
    setScans((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...s, status: "Completed", findings, pdfReport }
          : s
      )
    );

    const c = countsFromFindings(findings);
    const risk = riskFromFindings(findings);

    setSummary((prev) => ({
      ...prev,
      totalScans: prev.totalScans + 1,
      completed: prev.completed + 1,
      critical: prev.critical + c.critical,
      high: prev.high + c.high,
      medium: prev.medium + c.medium,
      low: prev.low + c.low,
      recent: { ...prev.recent, id, status: "Completed", risk },
    }));
  };

  const failScan = (id: string) => {
    setScans((prev) => prev.map((s) => (s.id === id ? { ...s, status: "Failed" } : s)));

    setSummary((prev) => ({
      ...prev,
      totalScans: prev.totalScans + 1,
      failed: prev.failed + 1,
      recent: { ...prev.recent, id, status: "Failed", risk: "High" },
    }));
  };

  const setAiAnswer = (id: string, answer: string) => {
    setScans((prev) => prev.map((s) => (s.id === id ? { ...s, aiAnswer: answer } : s)));
  };

  const setAiReport = (id: string, report: string) => {
    setScans((prev) => prev.map((s) => (s.id === id ? { ...s, aiReport: report } : s)));
  };

  const value = useMemo(
    () => ({
      summary,
      scans,
      addScan,
      attachFileToScan,
      completeScanWithFindings,
      failScan,
      setAiAnswer,
      setAiReport,
    }),
    [summary, scans]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  return useContext(StoreContext);
}
