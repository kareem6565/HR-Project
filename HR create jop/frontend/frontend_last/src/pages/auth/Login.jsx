import React, { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Mail, Lock, LogIn, AlertCircle } from "lucide-react";
import useAuth from "../../hooks/useAuth";

/**
 * Validate that a redirect target is an internal relative path.
 * Protects against open-redirect attacks attempting to bounce users to external origins.
 */
export function getSafeRedirect(from, fallback = "/dashboard") {
  if (!from) return fallback;
  const target = typeof from === "object" ? from.pathname + (from.search || "") : from;
  if (typeof target !== "string") return fallback;
  if (target.startsWith("/") && !target.startsWith("//") && !target.startsWith("/\\")) {
    return target;
  }
  return fallback;
}

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // If already authenticated, redirect immediately
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    setErrorMessage("");

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setErrorMessage("Please enter both email and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: trimmedEmail, password });
      const destination = getSafeRedirect(location.state?.from, "/dashboard");
      navigate(destination, { replace: true });
    } catch (err) {
      const status = err?.response?.status;
      if (status === 401) {
        // Generic failure message to prevent account enumeration
        setErrorMessage("Invalid email or password.");
      } else if (!err?.response || status >= 500) {
        setErrorMessage(
          "Unable to connect to the authentication server. Please check your network and try again."
        );
      } else {
        setErrorMessage(err?.response?.data?.detail || "Authentication failed. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-card">
      <div className="auth-header">
        <h1>Welcome back</h1>
        <p className="auth-subtitle">Sign in to your HERA account</p>
      </div>

      {errorMessage && (
        <div
          role="alert"
          className="form-error"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "16px",
            padding: "10px 14px",
            background: "#fef3f2",
            border: "1px solid #fee4e2",
            color: "#d92d20",
            borderRadius: "8px",
            fontSize: "13px",
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="auth-form" noValidate>
        <label htmlFor="login-email">
          Email address
          <div className="input-with-icon">
            <Mail size={17} />
            <input
              id="login-email"
              type="email"
              name="email"
              autoComplete="username"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              required
              autoFocus
            />
          </div>
        </label>

        <label htmlFor="login-password">
          Password
          <div className="input-with-icon">
            <Lock size={17} />
            <input
              id="login-password"
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              required
            />
          </div>
        </label>

        <div style={{ marginTop: "24px" }}>
          <button
            className="btn btn-primary wide"
            type="submit"
            disabled={isSubmitting}
            style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "8px" }}
          >
            <LogIn size={16} />
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </div>
      </form>
    </div>
  );
}
