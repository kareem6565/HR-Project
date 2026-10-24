import React from "react";
import { LogOut, User as UserIcon } from "lucide-react";
import useAuth from "../../hooks/useAuth";
import { BRAND } from "../../config/brand";
import { getTitleForPath } from "../../config/routes";

export default function Navbar({ pathname }) {
  const { user, logout } = useAuth();

  const matchedTitle = getTitleForPath(pathname);

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{BRAND.eyebrow}</p>
        <h1>{matchedTitle}</h1>
      </div>

      <div className="top-actions">

        {user && (
          <div
            className="user-profile-chip"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "6px 12px",
              border: "1px solid #eef2f6",
              borderRadius: "12px",
              background: "#f8fafc",
            }}
          >
            <div
              className="avatar"
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {user.full_name ? user.full_name.charAt(0).toUpperCase() : <UserIcon size={16} />}
            </div>
            <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2 }}>
              <strong style={{ fontSize: 13, color: "#344054" }}>
                {user.full_name || user.email}
              </strong>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                <span
                  style={{
                    fontSize: 10,
                    textTransform: "uppercase",
                    fontWeight: 700,
                    padding: "1px 6px",
                    borderRadius: 4,
                    background: user.role === "admin" ? "var(--hera-teal-light)" : "#f2f4f7",
                    color: user.role === "admin" ? "var(--hera-teal)" : "#475467",
                  }}
                >
                  {user.role}
                </span>
                <span style={{ fontSize: 11, color: "#98a2b3" }}>{user.email}</span>
              </div>
            </div>
          </div>
        )}

        <button
          className="icon-btn"
          type="button"
          onClick={logout}
          title="Sign out"
          aria-label="Sign out"
        >
          <LogOut size={19} />
        </button>
      </div>
    </header>
  );
}