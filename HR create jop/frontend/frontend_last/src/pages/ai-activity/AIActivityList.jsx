import React, { useEffect, useState } from "react";
import { RefreshCw, CheckCircle2, XCircle, RotateCw } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import { getAIActivityRuns, getAIActivityStats, retryRun } from "../../services/aiActivityService";

export default function AIActivityList() {
  const [runs, setRuns] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryingId, setRetryingId] = useState(null);

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([getAIActivityRuns(), getAIActivityStats()])
      .then(([r, s]) => {
        setRuns(r);
        setStats(s);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

  const onRetry = async (id) => {
    setRetryingId(id);
    await retryRun(id);
    setRetryingId(null);
    load();
  };

  if (loading) return <LoadingSpinner label="Loading AI activity..." />;
  if (error) return <ErrorState message="Unable to load AI activity. Please try again." onRetry={load} />;

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">AI ACTIVITY</p>
          <h2>Workflow observability — not an AI agent. These are execution traces.</h2>
        </div>
        <button className="btn btn-secondary" onClick={load}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-info">
              <span>Total Runs (24h)</span>
              <strong>{stats.totalRuns24h}</strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>Successful</span>
              <strong style={{ color: "#12B76A" }}>{stats.successful}</strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>Failed</span>
              <strong style={{ color: "#F04438" }}>{stats.failed}</strong>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-info">
              <span>Avg Latency</span>
              <strong>{stats.avgLatency}</strong>
            </div>
          </div>
        </div>
      )}

      {!runs.length ? (
        <EmptyState message="No AI activity in the last 24 hours." />
      ) : (
        <div className="run-list">
          {runs.map((run) => (
            <div className="panel run-card" key={run.id}>
              <div className="run-header">
                <div className="run-header-left">
                  <span className={`run-status-icon ${run.status}`}>
                    {run.status === "success" ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                  </span>
                  <div>
                    <strong>
                      {run.title} — {run.candidateName}
                    </strong>
                    <p className="muted-note">
                      Job: {run.job} · Provider: {run.provider} · Model: {run.model}
                    </p>
                  </div>
                </div>
                <div className="run-header-right">
                  <div>
                    <span className="muted-note">{run.timestamp}</span>
                    <p className="muted-note">Total: {run.totalDuration}</p>
                  </div>
                  <span className={`badge badge-${run.status === "success" ? "green" : "red"}`}>
                    {run.status === "success" ? "success" : "error"}
                  </span>
                  <button className="btn btn-secondary btn-small">View Trace</button>
                  {run.status === "error" && (
                    <button
                      className="btn btn-secondary btn-small"
                      onClick={() => onRetry(run.id)}
                      disabled={retryingId === run.id}
                    >
                      <RotateCw size={14} /> {retryingId === run.id ? "Retrying..." : "Retry"}
                    </button>
                  )}
                </div>
              </div>

              <div className="run-steps">
                {run.steps.map((step, i) => (
                  <React.Fragment key={step.name}>
                    <div className="run-step">
                      <span className={`run-step-icon ${step.status}`}>
                        {step.status === "success" ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                      </span>
                      <span className="run-step-name">{step.name}</span>
                      <span className="run-step-duration">{step.duration}</span>
                    </div>
                    {i < run.steps.length - 1 && <div className="run-step-connector" />}
                  </React.Fragment>
                ))}
              </div>

              <div className="run-meta">
                Run ID: <code>{run.runId}</code> &nbsp;·&nbsp; Schema: <code>{run.schema}</code> &nbsp;·&nbsp;
                Prompt: <code>{run.prompt}</code>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}