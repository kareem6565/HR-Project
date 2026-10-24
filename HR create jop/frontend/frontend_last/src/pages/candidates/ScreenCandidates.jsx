import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  Sparkles,
  Trash2,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { getJobs } from "../../services/jobService";
import { createScreeningBatch, getJobBatches } from "../../services/screeningBatchService";
import ScreeningBatchProgress from "../../components/screening/ScreeningBatchProgress";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import {
  formatFileSize,
  validateFile,
} from "./screenCandidateUtils";

export default function ScreenCandidates() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [files, setFiles] = useState([]); // Array of { file, fingerprint, name, size, status: 'ready' }
  const [rejectedFiles, setRejectedFiles] = useState([]); // Array of { id, name, size, reason, code }
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [errorType, setErrorType] = useState("");
  const [loadError, setLoadError] = useState("");
  const [loadingJobs, setLoadingJobs] = useState(true);

  const [activeBatchId, setActiveBatchId] = useState("");
  const [batchData, setBatchData] = useState(null);
  const [recentBatches, setRecentBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [batchesLoadError, setBatchesLoadError] = useState("");

  const loadJobs = async () => {
    setLoadingJobs(true);
    setLoadError("");
    try {
      const list = await getJobs();
      setJobs(list || []);
      const firstActive = (list || []).find((j) => String(j.status).toLowerCase() === "active");
      setJobId(firstActive?.id || list?.[0]?.id || "");
    } catch {
      setLoadError("Couldn't load your jobs from the backend. Try again.");
    } finally {
      setLoadingJobs(false);
    }
  };

  const loadBatches = async (selectedJobId) => {
    if (!selectedJobId) {
      setRecentBatches([]);
      setBatchesLoadError("");
      setLoadingBatches(false);
      return;
    }
    setLoadingBatches(true);
    setBatchesLoadError("");
    try {
      const batches = await getJobBatches(selectedJobId, 5);
      setRecentBatches(batches || []);
    } catch {
      setRecentBatches([]);
      setBatchesLoadError("Couldn't load recent screening batches. Try again.");
    } finally {
      setLoadingBatches(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    loadBatches(jobId);
  }, [jobId]);

  const selectedJob = jobs.find((j) => String(j.id) === String(jobId));

  const handleIncomingFiles = (incomingList) => {
    const incoming = Array.from(incomingList || []);
    if (!incoming.length) return;

    const currentFingerprints = new Set(files.map((f) => f.fingerprint));
    const newValid = [];
    const newRejected = [];

    for (const file of incoming) {
      const validation = validateFile(file, currentFingerprints);
      if (validation.valid) {
        currentFingerprints.add(validation.fingerprint);
        newValid.push({
          file,
          fingerprint: validation.fingerprint,
          name: file.name,
          size: file.size,
          status: "ready",
        });
      } else {
        newRejected.push({
          id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          name: file.name,
          size: file.size,
          reason: validation.reason,
          code: validation.code,
        });
      }
    }

    if (newValid.length > 0) {
      setFiles((prev) => [...prev, ...newValid]);
    }
    if (newRejected.length > 0) {
      setRejectedFiles((prev) => [...prev, ...newRejected]);
    }
  };

  const onFileInputChange = (e) => {
    if (e.target?.files) {
      handleIncomingFiles(e.target.files);
      e.target.value = "";
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer?.files) {
      handleIncomingFiles(e.dataTransfer.files);
    }
  };

  const removeValidFile = (fingerprint) => {
    setFiles((prev) => prev.filter((f) => f.fingerprint !== fingerprint));
  };

  const removeRejectedFile = (id) => {
    setRejectedFiles((prev) => prev.filter((rf) => rf.id !== id));
  };

  const clearRejectedFiles = () => {
    setRejectedFiles([]);
  };

  const start = async () => {
    setError("");
    setErrorType("");
    if (!jobId) {
      setError("Pick a job to screen candidates against first.");
      return;
    }
    if (!files.length) {
      setError("Please upload at least one valid PDF or DOCX CV.");
      return;
    }
    setSubmitting(true);
    try {
      const data = await createScreeningBatch({
        jobId,
        files: files.map((item) => item.file),
      });
      setActiveBatchId(data.batch_id || data.id);
      setBatchData(data);
      setFiles([]);
      loadBatches(jobId);
    } catch (err) {
      const isRateLimit =
        err?.response?.status === 429 || err?.response?.data?.error_type === "rate_limit";
      setErrorType(isRateLimit ? "rate_limit" : "");
      setError(
        isRateLimit
          ? "AI provider rate limit reached. Check the provider configuration in Settings."
          : err?.response?.data?.detail || err?.message || "Could not start screening batch. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };



  return (
    <>
      <section className="content-grid screen-candidates-grid" aria-label="Candidate screening setup">
        <div className="panel screen-setup-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">STEP 1 · JOB & CRITERIA</p>
              <h3>Create Screening</h3>
            </div>
          </div>
          <label>
            Job
            <select
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              disabled={submitting || loadingJobs || !!loadError || jobs.length === 0}
            >
              {!jobId && <option value="">Select a job…</option>}
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.title}
                  {String(job.status).toLowerCase() !== "active"
                    ? ` (${job.status})`
                    : ""}
                  {job.location ? ` — ${job.location}` : ""}
                </option>
              ))}
            </select>
          </label>

          {loadingJobs && <LoadingSpinner label="Loading jobs…" />}
          {loadError && (
            <ErrorState message={loadError} onRetry={loadJobs} />
          )}
          {!loadingJobs && !loadError && jobs.length === 0 && (
            <div className="screen-empty-state">
              <strong>No jobs available for screening yet</strong>
              <p>Create a job first, then return here to add candidate CVs.</p>
              <Link className="btn btn-primary" to="/jobs/new">Create a job</Link>
            </div>
          )}

          {selectedJob && (
            <div className="job-summary-card">
              <div className="job-summary-meta">
                <span className="badge badge-teal">{selectedJob.title}</span>
                {selectedJob.department && (
                  <span className="muted-note">Dept: {selectedJob.department}</span>
                )}
                {selectedJob.location && (
                  <span className="muted-note">Loc: {selectedJob.location}</span>
                )}
                {selectedJob.type && (
                  <span className="muted-note">Type: {selectedJob.type}</span>
                )}
                <span
                  className={`badge badge-${
                    String(selectedJob.status).toLowerCase() === "active" ? "green" : "grey"
                  }`}
                >
                  {selectedJob.status || "draft"}
                </span>
              </div>

              {selectedJob.description && (
                <p style={{ marginTop: 8, fontSize: 13, color: "var(--hera-ink)" }}>
                  {selectedJob.description}
                </p>
              )}

              <div
                style={{
                  marginTop: 12,
                  borderTop: "1px solid var(--hera-border)",
                  paddingTop: 10,
                }}
              >
                <p className="eyebrow" style={{ marginBottom: 6, fontSize: "10px" }}>
                  RECORDED CRITERIA & REQUIREMENTS
                </p>

                {selectedJob.requirements?.length > 0 ? (
                  <div style={{ marginBottom: 8 }}>
                    <strong style={{ fontSize: "12px", display: "block", marginBottom: 4 }}>
                      Requirements:
                    </strong>
                    <ul
                      style={{
                        margin: "0 0 8px 18px",
                        padding: 0,
                        fontSize: "12px",
                        color: "var(--hera-ink)",
                      }}
                    >
                      {selectedJob.requirements.map((req, idx) => (
                        <li key={idx} dir="auto" style={{ marginBottom: 2 }}>
                          {req}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {selectedJob.requiredSkills?.length > 0 ? (
                  <div style={{ marginBottom: 8 }}>
                    <strong style={{ fontSize: "12px", display: "block", marginBottom: 4 }}>
                      Required Skills:
                    </strong>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {selectedJob.requiredSkills.map((skill, idx) => (
                        <span key={idx} className="badge badge-blue" style={{ fontSize: "11px" }}>
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {!selectedJob.requirements?.length && !selectedJob.requiredSkills?.length && (
                  <p className="muted-note" style={{ fontSize: "12px", margin: "4px 0" }}>
                    No explicit criteria or skills configured on this job. Evaluator will screen against the general job description.
                  </p>
                )}

                <p
                  className="muted-note"
                  style={{
                    fontSize: "11px",
                    marginTop: 8,
                    color: "var(--hera-muted)",
                  }}
                >
                  Truthful criteria notice: Loaded directly from the job record. HERA does not fabricate criteria weights or mock approval statuses.
                </p>
              </div>
            </div>
          )}

          {selectedJob && (
            <div style={{ marginTop: 16 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 8,
                }}
              >
                <strong style={{ fontSize: "12px", color: "var(--hera-ink)" }}>
                  Recent screening batches
                </strong>
                {loadingBatches && <span role="status" style={{ fontSize: "11px", color: "var(--hera-muted)" }}>Loading…</span>}
              </div>
              {batchesLoadError ? (
                <ErrorState message={batchesLoadError} onRetry={() => loadBatches(jobId)} />
              ) : loadingBatches ? null : recentBatches.length === 0 ? (
                <div className="screen-empty-state screen-empty-state-compact">
                  <strong>No screening batches for this job yet</strong>
                  <p>After you submit CVs, their processing status will appear here.</p>
                </div>
              ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {recentBatches.map((batch) => {
                  const isCurrent = activeBatchId === batch.id;
                  const dateStr = batch.created_at
                    ? new Date(batch.created_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "";
                  const statusVariant =
                    batch.status === "completed"
                      ? "green"
                      : batch.status === "processing"
                      ? "blue"
                      : batch.status === "failed"
                      ? "red"
                      : "grey";
                  return (
                    <div
                      key={batch.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 10px",
                        background: isCurrent ? "rgba(99, 102, 241, 0.08)" : "var(--hera-card-bg, #fff)",
                        border: isCurrent
                          ? "1px solid var(--hera-primary, #6366f1)"
                          : "1px solid var(--hera-border, #e2e8f0)",
                        borderRadius: 6,
                        fontSize: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 600, color: "var(--hera-ink)" }}>{dateStr}</span>
                        <span
                          className={`badge badge-${statusVariant}`}
                          style={{ fontSize: "10px", padding: "1px 6px" }}
                        >
                          {batch.status}
                        </span>
                        <span style={{ color: "var(--hera-muted)", fontSize: "11px" }}>
                          {batch.counts?.completed ?? 0}/{batch.total_files} done
                          {batch.counts?.failed ? ` · ${batch.counts.failed} failed` : ""}
                        </span>
                      </div>
                      <button
                        type="button"
                        className={`btn ${isCurrent ? "btn-primary" : "btn-secondary"} btn-small`}
                        style={{ padding: "3px 8px", fontSize: "11px" }}
                        onClick={() => {
                          setActiveBatchId(batch.id);
                          setBatchData(null);
                        }}
                      >
                        {isCurrent ? "Active" : "View"}
                      </button>
                    </div>
                  );
                })}
              </div>
              )}
            </div>
          )}
        </div>

        <div className="panel screen-upload-panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">STEP 2 · CANDIDATE CVS</p>
              <h3>Add resumes</h3>
            </div>
            <span className="count">{files.length} valid file{files.length === 1 ? "" : "s"}</span>
          </div>

          <label
            className={`dropzone ${isDragging ? "dragging" : ""}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              multiple
              onChange={onFileInputChange}
              disabled={submitting}
              aria-label="Upload candidate CV files"
            />
            <div className="upload-icon">
              <UploadCloud size={25} aria-hidden="true" />
            </div>
            <strong>Drop PDF or DOCX CVs here</strong>
            <span>or click to browse · Max 5 MB per file · PDF and DOCX only</span>
          </label>

          {files.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  margin: "8px 0 4px",
                }}
              >
                <strong style={{ fontSize: "12px", color: "var(--hera-ink)" }}>
                  Selected Resumes ({files.length})
                </strong>
              </div>
              <div className="file-list">
                {files.map((f) => (
                  <div className="file file-valid" key={f.fingerprint}>
                    <FileText
                      size={18}
                      aria-hidden="true"
                      style={{ color: "var(--hera-teal)", flexShrink: 0 }}
                    />
                    <div>
                      <strong dir="auto">{f.name}</strong>
                      <span className="file-meta">
                        {formatFileSize(f.size)} ·{" "}
                        <span
                          className="badge badge-green"
                          style={{ fontSize: "10px", padding: "1px 6px" }}
                        >
                          Ready
                        </span>
                      </span>
                    </div>
                    <button
                      type="button"
                      className="btn-file-action"
                      onClick={() => removeValidFile(f.fingerprint)}
                      disabled={submitting}
                      aria-label={`Remove ${f.name}`}
                      title={`Remove ${f.name}`}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {rejectedFiles.length > 0 && (
            <div className="rejected-files-box" role="alert" aria-label="Rejected files">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <AlertCircle
                    size={16}
                    style={{ color: "var(--decision-reject, #b42318)" }}
                    aria-hidden="true"
                  />
                  <strong style={{ fontSize: "12px", color: "var(--decision-reject, #b42318)" }}>
                    Rejected Files ({rejectedFiles.length})
                  </strong>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-small"
                  onClick={clearRejectedFiles}
                  style={{ fontSize: "11px", padding: "3px 8px" }}
                >
                  Clear rejected list
                </button>
              </div>
              <p
                style={{
                  fontSize: "11px",
                  color: "var(--hera-muted)",
                  margin: "0 0 8px",
                }}
              >
                These files were not added to the screening batch because they did not pass pre-submission checks:
              </p>
              <div className="file-list">
                {rejectedFiles.map((rf) => (
                  <div className="file file-rejected" key={rf.id}>
                    <AlertCircle
                      size={18}
                      aria-hidden="true"
                      style={{ color: "var(--decision-reject, #b42318)", flexShrink: 0 }}
                    />
                    <div>
                      <strong dir="auto">{rf.name}</strong>
                      <span className="file-meta">
                        {formatFileSize(rf.size)} ·{" "}
                        <span
                          className="badge badge-red"
                          style={{ fontSize: "10px", padding: "1px 6px" }}
                        >
                          Invalid
                        </span>
                      </span>
                      <div className="file-reason">{rf.reason}</div>
                    </div>
                    <button
                      type="button"
                      className="btn-file-action"
                      onClick={() => removeRejectedFile(rf.id)}
                      aria-label={`Dismiss rejected file ${rf.name}`}
                      title={`Dismiss ${rf.name}`}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {submitting && (
            <div className="submission-progress-banner" role="status" aria-live="polite">
              <RefreshCw size={18} className="spin" aria-hidden="true" />
              <div>
                <strong>Submission in progress...</strong>
                <p style={{ margin: "2px 0 0", fontSize: "12px" }}>
                  Uploading {files.length} resume(s) to server and creating screening batch. Please wait...
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="form-error" role="alert">
              {error}
              {errorType === "rate_limit" && (
                <div className="rate-limit-help">
                  Add your own Soal API key in{" "}
                  <Link to="/settings">Settings</Link> to keep screening.
                </div>
              )}
            </div>
          )}

          <button
            className="primary wide"
            onClick={start}
            disabled={submitting || loadingJobs || !!loadError || !jobs.length || files.length === 0}
            type="button"
          >
            <Sparkles size={18} aria-hidden="true" />{" "}
            {submitting ? "Submitting batch..." : "Start Batch Screening"}
          </button>
        </div>
      </section>

      {activeBatchId && (
        <ScreeningBatchProgress
          key={activeBatchId}
          batchId={activeBatchId}
          initialData={batchData}
          job={selectedJob}
        />
      )}
    </>
  );
}
