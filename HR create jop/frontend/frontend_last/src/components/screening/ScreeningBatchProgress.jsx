import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  ExternalLink,
  Copy,
  AlertTriangle,
} from "lucide-react";
import {
  getScreeningBatch,
  retryBatchItem,
} from "../../services/screeningBatchService";
import { formatFileSize } from "../../pages/candidates/screenCandidateUtils";
import useCountUp from "../../hooks/useCountUp";

const SCREENING_STAGE_COUNT = 5;
const SCREENING_STAGE_INFO = {
  claimed: { step: 1, label: "Preparing job criteria" },
  load_job_context: { step: 1, label: "Preparing job criteria" },
  storage_read: { step: 2, label: "Opening the CV" },
  cv_text_extraction: { step: 2, label: "Reading the CV" },
  candidate_creation: { step: 3, label: "Preparing candidate profile" },
  resume_storage: { step: 3, label: "Preparing candidate profile" },
  candidate_profile_extraction: { step: 3, label: "Extracting skills and experience" },
  application_creation: { step: 4, label: "Checking the CV against the job" },
  candidate_evaluation: { step: 4, label: "Checking the CV against the job" },
  batch_finalize: { step: 4, label: "Saving screening results" },
  retry_scheduled: { step: 1, label: "Retrying after a temporary issue" },
};

export default function ScreeningBatchProgress({
  batchId,
  initialData = null,
  job = null,
  onBatchData = null,
}) {
  const navigate = useNavigate();
  const [batchData, setBatchData] = useState(initialData);
  const [retrying, setRetrying] = useState({});
  const [pollError, setPollError] = useState("");
  const [pollPaused, setPollPaused] = useState(false);
  const [pollTrigger, setPollTrigger] = useState(0);

  const inFlightRef = useRef(false);
  const consecutiveErrorsRef = useRef(0);

  // Controlled, non-overlapping polling with terminal-state stop and unmount cleanup
  useEffect(() => {
    if (!batchId || pollPaused) return;

    let mounted = true;
    let timerId = null;

    const checkBatch = async () => {
      if (!mounted) return;
      if (inFlightRef.current) {
        // React StrictMode can restart this effect while the previous request
        // is still settling. Keep polling once that request releases the lock.
        timerId = setTimeout(checkBatch, 250);
        return;
      }
      inFlightRef.current = true;
      try {
        const data = await getScreeningBatch(batchId);
        if (!mounted || !data) return;

        setBatchData(data);
        onBatchData?.(data);
        consecutiveErrorsRef.current = 0;
        setPollError("");

        // Check if all items are in terminal states
        const queuedCount = data.counts?.queued ?? data.queued_items ?? 0;
        const runningCount = data.counts?.running ?? data.running_items ?? 0;
        const isTerminal =
          data.status === "completed" ||
          data.status === "failed" ||
          data.status === "done" ||
          (queuedCount === 0 && runningCount === 0);

        if (!isTerminal && mounted) {
          timerId = setTimeout(checkBatch, 2000);
        }
      } catch (err) {
        if (!mounted) return;
        consecutiveErrorsRef.current += 1;

        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          setPollError(
            "Authentication required to view this batch. Please log in again."
          );
          setPollPaused(true);
        } else if (status === 404) {
          setPollError("Screening batch was not found or has expired.");
          setPollPaused(true);
        } else {
          // Network or transient server error - DO NOT treat as batch failure
          if (consecutiveErrorsRef.current >= 3) {
            setPollError(
              getProgressErrorMessage(err)
            );
            setPollPaused(true);
          } else {
            setPollError("Temporary connection issue while checking batch status. Retrying automatically...");
            timerId = setTimeout(checkBatch, 3000);
          }
        }
      } finally {
        inFlightRef.current = false;
      }
    };

    checkBatch();

    return () => {
      mounted = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [batchId, onBatchData, pollPaused, pollTrigger]);

  const handleManualRefresh = () => {
    setPollPaused(false);
    consecutiveErrorsRef.current = 0;
    setPollError("");
    setPollTrigger((prev) => prev + 1);
  };

  const handleRetryItem = async (itemId) => {
    setRetrying((prev) => ({ ...prev, [itemId]: true }));
    setPollError("");
    try {
      await retryBatchItem(itemId);
      // Immediately kick off next poll
      setPollTrigger((prev) => prev + 1);
    } catch (err) {
      setPollError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to retry batch item."
      );
    } finally {
      setRetrying((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  if (!batchData) {
    return (
      <section className="panel screening-connection-panel" style={{ marginTop: 24 }} aria-label="Screening status">
        {pollError ? (
          <div
            className="form-error"
            role="alert"
            style={{
              margin: "12px 0",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{pollError}</span>
            {pollPaused && (
              <button type="button" className="btn btn-secondary btn-small" onClick={handleManualRefresh}>
                Try again
              </button>
            )}
          </div>
        ) : (
          <div className="screening-connection-state" role="status" aria-live="polite">
            <progress className="screening-progress-bar screening-connection-bar" max={1} aria-label="Loading screening progress" />
            <div>
              <strong>Loading your CV’s screening progress</strong>
              <p className="muted-note">Your upload is in the queue. The current step will appear here shortly.</p>
            </div>
          </div>
        )}
      </section>
    );
  }

  const rawStatus = (batchData.status || "queued").toLowerCase();
  const isDone = rawStatus === "done" || rawStatus === "completed";
  const isFailed = rawStatus === "failed";
  const isRunning =
    rawStatus === "running" || (batchData.running_items || 0) > 0;

  const statusBadgeTone = isDone
    ? "green"
    : isFailed
    ? "red"
    : isRunning
    ? "blue"
    : "amber";

  const totalFiles =
    batchData.counts?.total ??
    batchData.total_files ??
    batchData.total_items ??
    0;
  const queuedFiles =
    batchData.counts?.queued ?? batchData.queued_items ?? 0;
  const runningFiles =
    batchData.counts?.running ?? batchData.running_items ?? 0;
  const doneFiles =
    batchData.counts?.completed ?? batchData.done_items ?? 0;
  const failedFiles =
    batchData.counts?.failed ?? batchData.failed_items ?? 0;
  const duplicateFiles =
    batchData.counts?.duplicate ?? batchData.duplicate_items ?? 0;
  const cancelledFiles =
    batchData.counts?.cancelled ?? batchData.cancelled_items ?? 0;
  const terminalFiles = Math.min(
    totalFiles,
    doneFiles + failedFiles + duplicateFiles + cancelledFiles
  );
  const progressPercent =
    totalFiles > 0 ? Math.round((terminalFiles / totalFiles) * 100) : null;

  const jobId = batchData.job_id || job?.id;
  const jobTitle = job?.title || batchData.job_title || jobId;

  return (
    <div className="panel" style={{ marginTop: 24 }}>
      <div className="panel-title">
        <div>
          <p className="eyebrow">ASYNC SCREENING BATCH</p>
          <h3>
            Batch Progress &mdash;{" "}
            <span className={`badge badge-${statusBadgeTone}`}>
              {runningFiles > 0 ? (
                <RefreshCw size={13} className="spin" aria-hidden="true" />
              ) : isDone ? (
                <CheckCircle2 size={13} aria-hidden="true" />
              ) : isFailed ? (
                <AlertCircle size={13} aria-hidden="true" />
              ) : (
                <Clock size={13} aria-hidden="true" />
              )}
              {rawStatus.toUpperCase()}
            </span>
          </h3>
          <p className="muted-note" style={{ marginTop: 4 }}>
            Batch ID: <code>{batchData.batch_id || batchData.id}</code>
            {jobTitle && (
              <>
                {" "}
                | Job: <strong>{jobTitle}</strong>
              </>
            )}
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {jobId && (
            <button
              type="button"
              className="btn btn-primary btn-small"
              onClick={() => navigate(`/matching-results?jobId=${jobId}`)}
              aria-label="View job matching results"
            >
              View Job Results <ExternalLink size={13} aria-hidden="true" />
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => navigate("/candidates")}
            aria-label="View all candidates"
          >
            All Candidates <ExternalLink size={13} aria-hidden="true" />
          </button>
        </div>
      </div>

      {pollError && (
        <div
          className="form-error"
          role="alert"
          style={{
            margin: "12px 0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={16} aria-hidden="true" />
            <span>{pollError}</span>
          </div>
          {pollPaused && (
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={handleManualRefresh}
              style={{ padding: "3px 8px", fontSize: "11px" }}
            >
              Resume Polling
            </button>
          )}
        </div>
      )}

      <section className={`screening-progress motion-rise${terminalFiles < totalFiles ? " screening-live" : ""}`} aria-label="Screening progress">
        <div className="screening-progress-heading">
          <span>Files processed</span>
          {progressPercent === null ? (
            <span className="muted-note">Waiting for batch totals</span>
          ) : (
            <strong>{progressPercent}%</strong>
          )}
        </div>
        {progressPercent !== null && (
          <progress
            className="screening-progress-bar"
            value={terminalFiles}
            max={totalFiles}
            aria-label="Screening batch progress"
            aria-valuetext={`${terminalFiles} of ${totalFiles} files reached a final state`}
          />
        )}
        <p className="muted-note">
          {progressPercent === null
            ? "Progress will appear when the batch reports its file count."
            : `${terminalFiles} of ${totalFiles} files reached a final state. Failed and duplicate files are included in progress.`}
        </p>
      </section>

      {/* Truthful counts derived from real API response */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
          gap: 12,
          margin: "16px 0",
        }}
      >
        <div className="stat-card" style={{ padding: 12 }}>
          <div className="stat-info">
            <span>Total CVs</span>
            <strong><CountUpValue value={totalFiles} /></strong>
          </div>
        </div>
        <div className="stat-card" style={{ padding: 12 }}>
          <div className="stat-info">
            <span>Queued</span>
            <strong style={{ color: "var(--color-amber, #f59e0b)" }}>
              <CountUpValue value={queuedFiles} />
            </strong>
          </div>
        </div>
        <div className="stat-card" style={{ padding: 12 }}>
          <div className="stat-info">
            <span>Processing</span>
            <strong style={{ color: "var(--color-blue, #3b82f6)" }}>
              <CountUpValue value={runningFiles} />
            </strong>
          </div>
        </div>
        <div className="stat-card" style={{ padding: 12 }}>
          <div className="stat-info">
            <span>Done</span>
            <strong style={{ color: "var(--evidence-supported, #067647)" }}>
              <CountUpValue value={doneFiles} />
            </strong>
          </div>
        </div>
        <div className="stat-card" style={{ padding: 12 }}>
          <div className="stat-info">
            <span>Failed</span>
            <strong style={{ color: "var(--decision-reject, #b42318)" }}>
              <CountUpValue value={failedFiles} />
            </strong>
          </div>
        </div>
        {duplicateFiles > 0 && (
          <div className="stat-card" style={{ padding: 12 }}>
            <div className="stat-info">
              <span>Duplicates</span>
              <strong style={{ color: "var(--hera-muted, #66736F)" }}>
                <CountUpValue value={duplicateFiles} />
              </strong>
            </div>
          </div>
        )}
      </div>

      {/* Per-item status table showing partial success and retry where permitted */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>File</th>
              <th>Status</th>
              <th>Score</th>
              <th>Details</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {(batchData.items || []).map((item) => {
              const rawScore =
                item.score !== null && item.score !== undefined
                  ? Number(item.score)
                  : null;
              const scoreDisplay =
                rawScore !== null && Number.isFinite(rawScore)
                  ? Math.round(rawScore)
                  : null;

              let tone = "grey";
              let Icon = Clock;
              if (item.status === "done") {
                tone = "green";
                Icon = CheckCircle2;
              } else if (item.status === "running") {
                tone = "blue";
                Icon = RefreshCw;
              } else if (item.status === "failed") {
                tone = "red";
                Icon = AlertCircle;
              } else if (item.status === "duplicate") {
                tone = "grey";
                Icon = Copy;
              } else if (item.status === "queued") {
                tone = "amber";
                Icon = Clock;
              }

              // Server allows retry only on failed items
              const canRetry = item.status === "failed";

              return (
                <tr key={item.id}>
                  <td>
                    <div>
                      <strong dir="auto">
                        {item.original_filename ||
                          item.filename ||
                          "Candidate Resume"}
                      </strong>
                      <div className="muted-note">
                        {item.file_size ? formatFileSize(item.file_size) : ""}
                        {item.retry_count > 0 || item.attempts > 0
                          ? ` · Attempt ${(item.retry_count || item.attempts)}/${item.max_attempts || 3}`
                          : ""}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`badge badge-${tone}`}>
                      <Icon
                        size={13}
                        className={item.status === "running" ? "spin" : ""}
                        aria-hidden="true"
                      />
                      {item.status}
                    </span>
                  </td>
                  <td>
                    {scoreDisplay !== null ? (
                      <strong className="score-text">{scoreDisplay}</strong>
                    ) : (
                      <span className="muted-note">—</span>
                    )}
                  </td>
                  <td>
                    {item.status === "failed" ? (
                      <div className="screening-item-error" dir="auto" role="alert">
                        <span>{item.error_message || "We couldn't finish screening this CV. Try again."}</span>
                        {item.error_code && <code>{item.error_code}</code>}
                      </div>
                    ) : item.status === "duplicate" ? (
                      <span className="muted-note">
                        {item.error_message || "Duplicate CV file content"}
                      </span>
                    ) : item.status === "running" ? (
                      <ScreeningItemProgress item={item} />
                    ) : item.status === "queued" && item.error_message ? (
                      <span className="muted-note">{item.error_message}</span>
                    ) : item.status === "done" ? (
                      <span className="muted-note">
                        Profile created & evaluated
                      </span>
                    ) : (
                      <span className="muted-note">
                        Queued for worker
                      </span>
                    )}
                  </td>
                  <td>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "center",
                      }}
                    >
                      {/* Retry only allowed by server when status is failed */}
                      {canRetry && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-small"
                          onClick={() => handleRetryItem(item.id)}
                          disabled={retrying[item.id]}
                          aria-label={`Retry processing ${item.original_filename || item.filename}`}
                        >
                          {retrying[item.id] ? "Retrying..." : "Retry"}
                        </button>
                      )}

                      {/* Partial success: successful items remain reviewable */}
                      {item.application_id && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-small"
                          onClick={() =>
                            navigate(
                              `/applications/${item.application_id}/review`
                            )
                          }
                          aria-label={`Review evaluation for ${item.original_filename || item.filename}`}
                        >
                          Review <ExternalLink size={13} aria-hidden="true" />
                        </button>
                      )}

                      {item.candidate_id && !item.application_id && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-small"
                          onClick={() =>
                            navigate(`/candidates/${item.candidate_id}`)
                          }
                          aria-label={`View profile for ${item.original_filename || item.filename}`}
                        >
                          Profile <ExternalLink size={13} aria-hidden="true" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScreeningItemProgress({ item }) {
  const progress = SCREENING_STAGE_INFO[item.stage] || {
    step: 1,
    label: "Preparing to screen this CV",
  };

  return (
    <div className="screening-item-progress" role="status" aria-live="polite">
      <span>{progress.label}</span>
      <progress
        className="screening-progress-bar"
        value={progress.step}
        max={SCREENING_STAGE_COUNT}
        aria-label={`${progress.label}, step ${progress.step} of ${SCREENING_STAGE_COUNT}`}
        aria-valuetext={`Step ${progress.step} of ${SCREENING_STAGE_COUNT}: ${progress.label}`}
      />
      <small className="muted-note">Step {progress.step} of {SCREENING_STAGE_COUNT}</small>
    </div>
  );
}

function getProgressErrorMessage(error) {
  const status = error?.response?.status;
  if (error?.code === "ECONNABORTED" || error?.code === "ETIMEDOUT") {
    return "The server took too long to return screening progress. Check the preview API, then try again.";
  }
  if (status >= 500) {
    const requestId = error?.response?.data?.request_id || error?.response?.headers?.["x-request-id"];
    return `The server couldn't load screening progress.${requestId ? ` Reference: ${requestId}` : " Check the backend logs, then try again."}`;
  }
  return "We couldn't connect to screening progress after several attempts. Check your connection and try again.";
}

function CountUpValue({ value }) {
  const display = useCountUp(typeof value === "number" ? value : 0);
  return <>{typeof value === "number" ? display : value}</>;
}
