import { useEffect, useState } from "react";
import { checkHealth, createJob, getJob, getJobCandidates, identity } from "./api";

const TABS = {
  health: "Health",
  jobs: "Jobs",
  pool: "Candidate Pool",
};

function ErrorMessage({ message }) {
  if (!message) return null;
  return <div className="error-box">{message}</div>;
}

function HealthTab() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError("");
    try {
      const data = await checkHealth();
      setStatus(data);
    } catch (err) {
      setError(err?.message || String(err));
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <h2>Backend health</h2>
      {!identity.configured && (
        <p className="hint">
          Set <code>VITE_ORG_ID</code> and <code>VITE_USER_ID</code> in your
          .env for org-scoped calls. Health itself is public.
        </p>
      )}
      <button onClick={run} disabled={loading}>
        {loading ? "Checking..." : "Check /api/v1/health"}
      </button>
      <ErrorMessage message={error} />
      {status && (
        <pre className="result">{JSON.stringify(status, null, 2)}</pre>
      )}
    </div>
  );
}

function JobsTab() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [created, setCreated] = useState(null);
  const [lookupId, setLookupId] = useState("");
  const [lookedUp, setLookedUp] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const job = await createJob({ title, raw_description: description || null });
      setCreated(job);
      setLookupId(job.id);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onLookup(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const job = await getJob(lookupId);
      setLookedUp(job);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
      setLookedUp(null);
    } finally {
      setBusy(false);
    }
  }

  function renderJob(job) {
    if (!job) return null;
    return (
      <pre className="result">{JSON.stringify(job, null, 2)}</pre>
    );
  }

  return (
    <div className="card">
      <h2>Create a job</h2>
      <form onSubmit={onCreate} className="form">
        <label>
          Title
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Senior Backend Engineer"
            required
          />
        </label>
        <label>
          Raw description (optional)
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Job requirements / description"
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Creating..." : "Create job"}
        </button>
      </form>
      <ErrorMessage message={error} />
      {created && (
        <>
          <p className="ok">Created. Job id: <code>{created.id}</code></p>
          {renderJob(created)}
        </>
      )}

      <h2>Look up a job</h2>
      <form onSubmit={onLookup} className="form">
        <label>
          Job id
          <input
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            placeholder="Paste a job id (UUID)"
            required
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Loading..." : "Look up"}
        </button>
      </form>
      {lookedUp && renderJob(lookedUp)}
    </div>
  );
}

function PoolTab() {
  const [jobId, setJobId] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onLoad(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await getJobCandidates(jobId);
      setRows(data);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || String(err));
      setRows(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Job candidate pool (Phase 4.5)</h2>
      <p className="hint">
        Loads <code>GET /api/v1/jobs/&#123;id&#125;/candidates</code> and shows
        the ranked, grouped candidates.
      </p>
      <form onSubmit={onLoad} className="form">
        <label>
          Job id
          <input
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            placeholder="Paste a job id (UUID)"
            required
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Loading..." : "Load candidate pool"}
        </button>
      </form>
      <ErrorMessage message={error} />
      {rows && rows.length === 0 && (
        <p className="hint">No candidates for this job yet.</p>
      )}
      {rows && rows.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Full name</th>
              <th>Email</th>
              <th>Score</th>
              <th>Group</th>
              <th>Status</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.application_id}>
                <td>{row.full_name}</td>
                <td>{row.email || "—"}</td>
                <td>{row.score ?? "—"}</td>
                <td>
                  <span className={`badge badge-${row.group}`}>{row.group}</span>
                </td>
                <td>{row.status}</td>
                <td>{row.decision || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("health");

  return (
    <div className="page">
      <header className="header">
        <h1>AI HR Assistant — test frontend</h1>
        <div className="identity">
          {identity.configured ? (
            <span className="ok">Identity: org {identity.organizationId}</span>
          ) : (
            <span className="warn">
              No VITE_ORG_ID / VITE_USER_ID set — org-scoped calls will fail.
            </span>
          )}
        </div>
      </header>

      <nav className="tabs">
        {Object.entries(TABS).map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "tab active" : "tab"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="content">
        {tab === "health" && <HealthTab />}
        {tab === "jobs" && <JobsTab />}
        {tab === "pool" && <PoolTab />}
      </main>
    </div>
  );
}
