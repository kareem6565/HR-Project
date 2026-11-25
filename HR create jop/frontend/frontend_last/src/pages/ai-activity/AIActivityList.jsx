import React, { useEffect, useState } from "react";
import { RefreshCw, CheckCircle2, XCircle, RotateCw } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import { getAIActivityRuns, getAIActivityStats, getAIProviderRequests, retryRun } from "../../services/aiActivityService";
import { getAIErrorMessage } from "../../utils/aiError";

export default function AIActivityList() {
  const [runs, setRuns] = useState([]);
  const [stats, setStats] = useState(null);
  const [providerRequests, setProviderRequests] = useState([]);
  const [providerRequestsError, setProviderRequestsError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryingId, setRetryingId] = useState(null);
  const [retryError, setRetryError] = useState("");

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
    getAIProviderRequests()
      .then((items) => {
        setProviderRequests(items);
        setProviderRequestsError(false);
      })
      .catch(() => setProviderRequestsError(true));
  };

  useEffect(load, []);

  const onRetry = async (id) => {
    setRetryingId(id);
    setRetryError("");
    try {
      await retryRun(id);
      load();
    } catch (requestError) {
      setRetryError(getAIErrorMessage(requestError, "Could not retry this workflow."));
    } finally {
      setRetryingId(null);
    }
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

      <section className="panel provider-requests-panel" aria-labelledby="provider-requests-title">
        <div className="provider-requests-heading">
          <div>
            <p className="eyebrow">REQUEST DIAGNOSTICS</p>
            <h3 id="provider-requests-title">Recent AI provider requests</h3>
            <p className="muted-note">Payload-free trace data. Use the request IDs to match an app error with server logs.</p>
          </div>
        </div>
        {providerRequestsError ? (
          <p className="provider-requests-empty" role="status">Provider request log could not be loaded. Check admin access and the API logs.</p>
        ) : !providerRequests.length ? (
          <p className="provider-requests-empty">No provider requests recorded yet.</p>
        ) : (
          <div className="provider-requests-scroll" role="region" aria-label="Recent AI provider requests" tabIndex={0}>
            <table className="provider-requests-table">
              <thead><tr><th scope="col">Result</th><th scope="col">Feature</th><th scope="col">Provider / model</th><th scope="col">Time</th><th scope="col">Duration</th><th scope="col">Tokens in / out</th><th scope="col">Request IDs</th></tr></thead>
              <tbody>{providerRequests.map((request) => (
                <tr key={request.id}>
                  <td><span className={`badge badge-${request.status === "success" ? "green" : request.status === "error" ? "red" : "yellow"}`}>{request.status}{request.errorCode ? ` · ${request.errorCode}` : ""}</span>{request.providerStatus ? <small className="provider-request-subline">HTTP {request.providerStatus}</small> : null}</td>
                  <td>{request.feature}</td>
                  <td>{request.provider}<small className="provider-request-subline">{request.model}</small></td>
                  <td>{request.timestamp || "—"}</td>
                  <td>{request.duration}</td>
                  <td>{request.inputTokens ?? "—"} / {request.outputTokens ?? "—"}</td>
                  <td><code className="provider-request-id">App: {request.requestId}</code><code className="provider-request-id">Provider: {request.providerRequestId}</code></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
      {retryError && <p className="hera-note hera-error" role="alert">{retryError}</p>}

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
