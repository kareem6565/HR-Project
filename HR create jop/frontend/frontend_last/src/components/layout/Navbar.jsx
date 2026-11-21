import React from "react";
import { BriefcaseBusiness, LogOut, Menu, Moon, Sun, X } from "lucide-react";
import useAuth from "../../hooks/useAuth";
import { useTheme } from "../../context/ThemeContext";
import { BRAND } from "../../config/brand";
import { HR_MANAGER_LOGOUT_URL } from "../../config/hrManager";
import { getTitleForPath } from "../../config/routes";

export default function Navbar({ pathname, isNavigationOpen = false, onMenuToggle }) {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const matchedTitle = getTitleForPath(pathname);
  const handleLogout = () =>
    logout(() => window.location.replace(HR_MANAGER_LOGOUT_URL));

  return (
    <header className="topbar">
      <button
        className="mobile-menu-toggle"
        type="button"
        aria-label={isNavigationOpen ? "Close navigation menu" : "Open navigation menu"}
        aria-controls="hera-primary-navigation"
        aria-expanded={isNavigationOpen}
        onClick={onMenuToggle}
      >
        {isNavigationOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
      </button>
      <div>
        <p className="eyebrow">{BRAND.eyebrow}</p>
        <h1>{matchedTitle}</h1>
      </div>

      <div className="top-actions">
        <button
          className="theme-toggle"
          type="button"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          aria-pressed={theme === "dark"}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
          <span className="theme-toggle-label">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>

        {user && (
          <div
            className="user-profile-chip"
            aria-label={`Signed in as ${formatRole(user.role)}`}
          >
            <span className="user-profile-avatar" aria-hidden="true"><BriefcaseBusiness size={15} /></span>
            <span className="user-profile-role">{formatRole(user.role)}</span>
          </div>
        )}

        <button
          className="icon-btn"
          type="button"
          onClick={handleLogout}
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={19} />
        </button>
      </div>
    </header>
  );
}

function formatRole(role) {
  const labels = {
    admin: "Administrator",
    administrator: "Administrator",
    recruiter: "Recruiter",
    hr_manager: "HR Manager",
    hiring_manager: "Hiring Manager",
  };
  const normalized = String(role || "User").trim().toLowerCase();
  return labels[normalized] || normalized.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
