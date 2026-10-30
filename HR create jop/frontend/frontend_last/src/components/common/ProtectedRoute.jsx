import React from "react";
import { Navigate, useLocation, Link } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import LoadingSpinner from "./LoadingSpinner";
import { ShieldAlert, RefreshCw } from "lucide-react";

/**
 * Route protection guard for authenticated application sections.
 *
 * Guarantees:
 * - Sensitive business/candidate data is never rendered before auth is resolved.
 * - Unauthenticated callers are redirected to /login with internal return state.
 * - Temporarily unavailable backend surfaces a recoverable error state.
 * - Role-restricted routes display an access-denied state without logging out.
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { status, user, error, checkAuth } = useAuth();
  const location = useLocation();

  if (status === "initializing") {
    return (
      <div className="auth-loading-screen" style={{ minHeight: "60vh", display: "grid", placeItems: "center" }}>
        <LoadingSpinner label="Authenticating..." />
      </div>
    );
  }

  if (status === "unavailable") {
    return (
      <div className="auth-error-screen" style={{ minHeight: "60vh", display: "grid", placeItems: "center", padding: "40px" }}>
        <div className="auth-card panel" style={{ textAlign: "center", padding: "32px", maxWidth: "440px" }}>
          <div style={{ color: "#d92d20", marginBottom: "16px", display: "flex", justifyContent: "center" }}>
            <ShieldAlert size={36} />
          </div>
          <h2>Authentication Unavailable</h2>
          <p className="auth-subtitle" style={{ marginTop: "8px", marginBottom: "20px" }}>
            {error || "Unable to reach the authentication service. Please check your connection and try again."}
          </p>
          <button className="btn btn-primary wide" type="button" onClick={checkAuth}>
            <RefreshCw size={16} /> Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (status === "unauthenticated" || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const userRoles = Array.isArray(user.roles) && user.roles.length > 0
      ? user.roles
      : [user.role].filter(Boolean);
    const isAllowed = allowedRoles.some((role) => {
      if (userRoles.includes(role)) return true;
      return (role === "admin" || role === "administrator") &&
        userRoles.some((userRole) => userRole === "admin" || userRole === "administrator");
    });

    if (!isAllowed) {
      return (
        <div className="page-content" style={{ padding: "40px" }}>
          <div className="panel" style={{ textAlign: "center", padding: "40px", maxWidth: "500px", margin: "40px auto" }}>
            <div style={{ color: "#f79009", marginBottom: "16px", display: "flex", justifyContent: "center" }}>
              <ShieldAlert size={36} />
            </div>
            <h2>Access Restricted</h2>
            <p className="auth-subtitle" style={{ margin: "12px 0 24px" }}>
              This section is restricted to <strong>{allowedRoles.join(", ")}</strong> accounts. Your account has <strong>{userRoles.join(", ") || "unknown"}</strong> access.
            </p>
            <Link to="/dashboard" className="btn btn-primary">
              Return to Dashboard
            </Link>
          </div>
        </div>
      );
    }
  }

  return children;
}
