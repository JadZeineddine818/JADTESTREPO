import { NavLink } from "react-router-dom";
import "../styles/sidebar.css";
import {
  LayoutDashboard,
  ScanSearch,
  History,
  FileText,
  LogOut
} from "lucide-react";

export default function Sidebar() {
  const loggedInUser = localStorage.getItem("loggedInUser");

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("loggedInUser");
    window.location.href = "/login";
  };

  return (
    <div className="sidebar">
      <h2 className="logo">AiSecureOrch</h2>

      <nav className="nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `navItem ${isActive ? "active" : ""}`}
        >
          <LayoutDashboard size={18} className="navIcon" />
          Dashboard
        </NavLink>

        <NavLink
          to="/new-scan"
          className={({ isActive }) => `navItem ${isActive ? "active" : ""}`}
        >
          <ScanSearch size={18} className="navIcon" />
          New Scan
        </NavLink>

        <NavLink
          to="/history"
          className={({ isActive }) => `navItem ${isActive ? "active" : ""}`}
        >
          <History size={18} className="navIcon" />
          History
        </NavLink>

        <NavLink
          to="/reports"
          className={({ isActive }) => `navItem ${isActive ? "active" : ""}`}
        >
          <FileText size={18} className="navIcon" />
          Reports
        </NavLink>
      </nav>

      <div className="userInfo">
        <p className="userLabel">Logged in as</p>
        <p className="userEmail">{loggedInUser || "Unknown user"}</p>
      </div>

      <div className="logoutContainer">
        <button className="logoutButton" onClick={handleLogout}>
          <LogOut size={18} className="navIcon" />
          Logout
        </button>
      </div>
    </div>
  );
}