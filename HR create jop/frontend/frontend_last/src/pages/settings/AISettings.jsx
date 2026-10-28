import React, { useEffect, useState } from "react";
import { RefreshCw, KeyRound, CheckCircle2, XCircle, Sun, Moon, Activity } from "lucide-react";
import { Link } from "react-router-dom";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import {
  getAISettings,
  verifyApiKey,
} from "../../services/aiSettingsService";
import { useTheme } from "../../context/ThemeContext";

const SOURCE_LABELS = {
  environment: "Server env (.env)",
  runtime: "Runtime (this session)",
  none: "No key configured",
};

export default function AISettings() {
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKeyField] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");
  const [verifyResult, setVerifyResult] = useState(null);

  const load = () => {
    setLoading(true);
    setError(false);
    getAISettings()
      .then(setSettings)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const verify = async (useProbe = false) => {
    setBusy("verify");
    setFormError("");
    setNotice("");
    setVerifyResult(null);
    try {
      const keyToTest = useProbe && apiKey.trim() ? apiKey.trim() : undefined;
      const result = await verifyApiKey(keyToTest);
      setVerifyResult(result);
      if (result.ok) {
        setNotice(result.message || "AI provider connection verified successfully.");
      } else {
        setFormError(result.message || "AI provider verification failed.");
      }
    } catch (err) {
      setFormError(err?.response?.data?.detail || "Verification request failed.");
    } finally {
      setBusy("");
    }
  };

  if (loading) return <LoadingSpinner label="Loading AI settings..." />;
  if (error || !settings)
    return <ErrorState message="Unable to load AI settings. Try again." onRetry={load} />;

  const soalActive = settings.provider === "soal";

  return (
    <section>
      <div className="content-grid settings-grid">
        <div className="panel">
          <div className="panel-title">
          <div>
            <p className="eyebrow">AI PROVIDER</p>
            <h3>AI Settings</h3>
          </div>
          <button className="btn btn-secondary" onClick={load}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>

        <div className="dev-note">
          <strong>Environment-Managed Configuration</strong>
          <span>
            AI provider credentials are managed securely by system operators via server environment variables (.env).
            Runtime key modification is disabled to ensure tenant isolation and prevent cross-organization configuration changes.
          </span>
        </div>

        <div className="stats-grid" style={{ marginBottom: "1rem" }}>
          <div className="stat-card">
            <div className="stat-info">
              <span>Provider</span>
              <strong>{settings.provider}</strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>Model</span>
              <strong>{settings.model || "—"}</strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>API key</span>
              <strong style={{ color: settings.has_api_key ? "#12B76A" : "#F79009" }}>
                {settings.has_api_key ? "Configured" : "Missing"}
              </strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>Key source</span>
              <strong>{SOURCE_LABELS[settings.api_key_source] || settings.api_key_source}</strong>
            </div>
          </div>
        </div>

        {!soalActive && (
          <p className="muted-note">
            Soal is not currently configured as the active provider. System operators can set SOAL_API_KEY in the server environment.
          </p>
        )}

        {(formError || notice) && (
          <div className={formError ? "form-error" : "success-message"}>{formError || notice}</div>
        )}

        <label>
          Test / Probe API key (Optional)
          <div className="input-with-icon">
            <KeyRound size={17} />
            <input
              name="apiKey"
              type="password"
              placeholder="Enter a key to test connectivity (probe only, not saved)"
              value={apiKey}
              onChange={(e) => setApiKeyField(e.target.value)}
              autoComplete="off"
            />
          </div>
        </label>

        <div className="btn-row">
          <button className="btn btn-primary" onClick={() => verify(false)} disabled={busy === "verify"}>
            <CheckCircle2 size={16} /> {busy === "verify" ? "Verifying..." : "Verify Active Provider"}
          </button>
          {apiKey.trim() && (
            <button className="btn btn-secondary" onClick={() => verify(true)} disabled={busy === "verify"}>
              <CheckCircle2 size={16} /> Test Probe Key
            </button>
          )}
        </div>

        {verifyResult && (
          <div className={verifyResult.ok ? "success-message" : "form-error"}>
            {verifyResult.ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{" "}
            {verifyResult.message}
          </div>
        )}
        </div>

        <div className="panel appearance-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">APPEARANCE</p>
              <h3>Theme</h3>
            </div>
          </div>
          <p className="muted-note">Choose the appearance for HERA on this device.</p>
          <div className="theme-options" role="group" aria-label="Appearance theme">
            <button
              type="button"
              className={`theme-option${theme === "light" ? " is-selected" : ""}`}
              aria-pressed={theme === "light"}
              onClick={() => setTheme("light")}
            >
              <Sun size={18} aria-hidden="true" />
              <span>Light</span>
            </button>
            <button
              type="button"
              className={`theme-option${theme === "dark" ? " is-selected" : ""}`}
              aria-pressed={theme === "dark"}
              onClick={() => setTheme("dark")}
            >
              <Moon size={18} aria-hidden="true" />
              <span>Dark</span>
            </button>
          </div>
          <div className="settings-diagnostics">
            <p className="eyebrow">SYSTEM OPERATORS</p>
            <p>Technical workflow traces and AI execution diagnostics.</p>
            <Link className="btn btn-secondary" to="/ai-activity">
              <Activity size={16} aria-hidden="true" /> Open AI Activity
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
