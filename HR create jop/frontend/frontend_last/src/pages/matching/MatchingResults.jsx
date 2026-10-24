import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search, ChevronDown, ChevronRight, Briefcase, GitCompareArrows } from "lucide-react";
import ScoreCard from "../../components/common/ScoreCard";
import Badge from "../../components/common/Badge";
import PipelineActions from "../../components/common/PipelineActions";
import { GroupPill } from "../../components/common/RankedCandidateList";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import Pagination from "../../components/common/Pagination";
import { getRanking, recordPipelineDecision } from "../../services/matchingService";
import { getJobs } from "../../services/jobService";
import { getReviewBundle } from "../../services/reviewService";
import { formatScore } from "../../utils/score";

// Candidate ranking scoped strictly to one selected job (UI-04).
//
// Rules enforced:
// 1. Candidate ranking must never combine candidates from unrelated jobs.
//    If no job is selected in URL or state, a clear Job Picker is shown.
// 2. All filters (jobId, search, status, group, minScore, sort, page) are
//    persisted in URL query parameters so refresh or link sharing preserves them.
// 3. Backend groups (must_review, consider, lower_priority) are authoritative.
// 4. Low-priority candidates are kept visible and reviewable in a collapsible
//    section so they are never hidden or lost.
// 5. Quick decision actions open a deliberate confirmation modal with optional
//    reason and clear action labels, preventing accidental or unexplained clicks.

const STATUS_TO_DECISION = {
  advanced: "advance",
  hold: "hold",
  rejected: "reject",
};

const DECISION_NAMES = {
  advance: "Advance",
  hold: "Hold",
  reject: "Reject",
};

const DECISION_VARIANTS = {
  advance: "primary",
  hold: "secondary",
  reject: "danger",
};

const PAGE_SIZE = 25;
const MAX_COMPARE_CANDIDATES = 3;

function evidenceLabel(item) {
  const ref = item?.requirement_ref;
  if (typeof ref === "string") return ref;
  if (ref && typeof ref === "object") {
    return ref.text || ref.skill || ref.requirement || ref.requirement_key || "Requirement";
  }
  return "Requirement";
}

function evidenceForRequirement(bundle, requirementKey) {
  return (bundle?.evidence || []).find((item) => {
    const key = item?.requirement_ref?.requirement_key;
    return key === requirementKey;
  });
}

// Groups the backend-classified evidence into display buckets.
export function splitEvidence(evidence = []) {
  const buckets = { matched: [], partial: [], missing: [] };
  for (const item of evidence) {
    const bucket = item?.evidenceType;
    if (buckets[bucket]) buckets[bucket].push(item?.text || item?.requirementKey || "");
  }
  return buckets;
}

export default function MatchingResults() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJobId = searchParams.get("jobId") || "";

  const [rows, setRows] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Decision confirmation modal state
  const [pendingDecision, setPendingDecision] = useState(null); // { row, decision }
  const [decisionReason, setDecisionReason] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [successNotice, setSuccessNotice] = useState("");

  // Collapsible lower-priority section state
  const [showLowerPriority, setShowLowerPriority] = useState(false);
  const [compareIds, setCompareIds] = useState([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareBundles, setCompareBundles] = useState([]);
  const [compareError, setCompareError] = useState("");
  const [compareNotice, setCompareNotice] = useState("");

  useEffect(() => {
    setCompareIds([]);
    setCompareBundles([]);
    setCompareOpen(false);
  }, [selectedJobId]);

  const toggleCompare = (row) => {
    setCompareNotice("");
    if (compareIds.includes(row.applicationId)) {
      setCompareIds(compareIds.filter((id) => id !== row.applicationId));
      return;
    }
    if (compareIds.length >= MAX_COMPARE_CANDIDATES) {
      setCompareNotice(`Compare up to ${MAX_COMPARE_CANDIDATES} candidates at a time.`);
      return;
    }
    setCompareIds([...compareIds, row.applicationId]);
  };

  const openComparison = async () => {
    if (compareIds.length < 2) return;
    setCompareOpen(true);
    setCompareLoading(true);
    setCompareError("");
    setCompareBundles([]);
    try {
      const bundles = await Promise.all(compareIds.map((id) => getReviewBundle(id)));
      if (bundles.some((bundle) => String(bundle.application?.job_id) !== String(selectedJobId))) {
        throw new Error("Candidates must belong to the selected job to compare their evidence.");
      }
      setCompareBundles(bundles);
    } catch (err) {
      setCompareError(
        err?.response?.data?.detail || err?.message || "Unable to load candidate evidence for comparison."
      );
    } finally {
      setCompareLoading(false);
    }
  };

  // Search parameters persisted in URL
  const skillSearch = searchParams.get("search") || "";
  const statusFilter = searchParams.get("status") || "all";
  const groupFilter = searchParams.get("group") || "all";
  const minScore = Number(searchParams.get("minScore") || 0);
  const sortOrder = searchParams.get("sort") || "score_desc";
  const page = Number(searchParams.get("page") || 1);

  const updateParams = (updates) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([k, v]) => {
      if (v === null || v === undefined || v === "" || v === "all" || v === 0) {
        next.delete(k);
      } else {
        next.set(k, String(v));
      }
    });
    if (!("page" in updates)) {
      next.delete("page");
    }
    setSearchParams(next);
  };

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([getRanking(), getJobs()])
      .then(([r, j]) => {
        setRows(r);
        setJobs(j);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

  const onInitiateDecision = (row, decision) => {
    setPendingDecision({ row, decision });
    setDecisionReason("");
    setActionError(null);
    setSuccessNotice("");
  };

  const onConfirmDecision = async () => {
    if (!pendingDecision) return;
    setSubmittingDecision(true);
    setActionError(null);
    try {
      await recordPipelineDecision(
        pendingDecision.row.applicationId,
        pendingDecision.decision,
        decisionReason || undefined
      );
      setSuccessNotice(
        `Recorded ${DECISION_NAMES[pendingDecision.decision]} for ${pendingDecision.row.candidateName}.`
      );
      setPendingDecision(null);
      setDecisionReason("");
      load();
    } catch (err) {
      setActionError(
        err?.response?.data?.detail ||
          err?.message ||
          `Could not record ${pendingDecision.decision}. Please try again.`
      );
    } finally {
      setSubmittingDecision(false);
    }
  };

  const selectedJob = useMemo(() => {
    return jobs.find((j) => String(j.id) === String(selectedJobId)) || null;
  }, [jobs, selectedJobId]);

  // Candidates scoped strictly to the selected job
  const jobCandidates = useMemo(() => {
    if (!selectedJobId) return [];
    return rows.filter((r) => String(r.jobId) === String(selectedJobId));
  }, [rows, selectedJobId]);

  // Filtered and sorted candidates within the selected job
  const filteredCandidates = useMemo(() => {
    return jobCandidates
      .filter((r) => {
        if (statusFilter !== "all" && r.status !== statusFilter) return false;
        if (groupFilter !== "all" && r.group !== groupFilter) return false;
        if (minScore > 0 && (r.score === null || r.score < minScore)) return false;
        if (skillSearch) {
          const target = `${r.candidateName} ${r.jobTitle} ${r.status}`.toLowerCase();
          if (!target.includes(skillSearch.toLowerCase())) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortOrder === "name_asc") {
          return a.candidateName.localeCompare(b.candidateName);
        }
        if (sortOrder === "score_asc") {
          if (a.score === null && b.score === null) return 0;
          if (a.score === null) return 1;
          if (b.score === null) return -1;
          return a.score - b.score;
        }
        // Default: score_desc
        if (a.score === null && b.score === null) return 0;
        if (a.score === null) return 1;
        if (b.score === null) return -1;
        return b.score - a.score;
      });
  }, [jobCandidates, statusFilter, groupFilter, minScore, skillSearch, sortOrder]);

  // Partition candidates into primary and lower-priority (for collapsible section)
  const { primaryCandidates, lowerPriorityCandidates } = useMemo(() => {
    if (groupFilter === "lower_priority") {
      return { primaryCandidates: filteredCandidates, lowerPriorityCandidates: [] };
    }
    const primary = [];
    const lower = [];
    for (const c of filteredCandidates) {
      if (c.group === "lower_priority") {
        lower.push(c);
      } else {
        primary.push(c);
      }
    }
    return { primaryCandidates: primary, lowerPriorityCandidates: lower };
  }, [filteredCandidates, groupFilter]);

  // Paginated slice for the primary candidates list (25 per page)
  const paginatedPrimary = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return primaryCandidates.slice(start, start + PAGE_SIZE);
  }, [primaryCandidates, page]);

  if (loading) return <LoadingSpinner label="Loading matching results..." />;
  if (error) return <ErrorState message="Unable to load matching results. Please try again." onRetry={load} />;

  const renderCandidateRow = (r, rankIndex) => {
    const evidence = splitEvidence(r.evidence);
    return (
      <div
        className="panel ranking-row clickable"
        key={r.id}
        tabIndex={0}
        role="link"
        aria-label={`Review ${r.candidateName} for ${r.jobTitle}`}
        onClick={() =>
          navigate(`/applications/${r.applicationId}/review`, {
            state: {
              candidateIds: filteredCandidates.map((c) => c.applicationId),
              jobId: selectedJobId,
            },
          })
        }
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            navigate(`/applications/${r.applicationId}/review`, {
              state: {
                candidateIds: filteredCandidates.map((c) => c.applicationId),
                jobId: selectedJobId,
              },
            });
          }
        }}
      >
        <div className="ranking-rank">{r.score === null ? "—" : `#${rankIndex + 1}`}</div>

        <div className="ranking-candidate">
          <div className="mini-avatar">
            {r.candidateName
              .split(" ")
              .map((x) => x[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div>
            <strong dir="auto">{r.candidateName}</strong>
            <span dir="auto">{r.jobTitle}</span>
          </div>
        </div>

        <ScoreCard
          score={r.score}
          group={r.group}
          matching={evidence.matched}
          partial={evidence.partial}
          missing={evidence.missing}
          compact
        />

        {r.group ? <GroupPill group={r.group} /> : null}

        <Badge status={r.status} />

        <div onClick={(e) => e.stopPropagation()}>
          <label className="ranking-compare-select" onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={compareIds.includes(r.applicationId)}
              onChange={() => toggleCompare(r)}
              aria-label={`Select ${r.candidateName} for comparison`}
            />
            <span>Compare</span>
          </label>
          <PipelineActions
            currentStatus={STATUS_TO_DECISION[r.status]}
            onDecision={(decision) => onInitiateDecision(r, decision)}
            size="small"
            disabled={submittingDecision && pendingDecision?.row?.applicationId === r.applicationId}
          />
        </div>
      </div>
    );
  };

  return (
    <section>
      {!selectedJobId ? (
        <div className="job-picker-container">
          <div className="section-head" style={{ marginBottom: 16 }}>
            <div>
              <p className="eyebrow">MATCHING RESULTS</p>
              <h2>Select a Job to View Candidate Ranking</h2>
              <p className="muted-note">
                Candidate matching and rankings are scoped to one job. Choose a position to review candidates.
              </p>
            </div>
          </div>

          {!jobs.length ? (
            <EmptyState message="No jobs available. Create a job first to view candidate matches." />
          ) : (
            <div
              className="jobs-picker-grid"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 16,
              }}
            >
              {jobs.map((job) => {
                const count = rows.filter((r) => String(r.jobId) === String(job.id)).length;
                return (
                  <div
                    key={job.id}
                    className="panel job-picker-card clickable"
                    tabIndex={0}
                    role="button"
                    aria-label={`Select ${job.title} to view rankings`}
                    onClick={() => updateParams({ jobId: job.id })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        updateParams({ jobId: job.id });
                      }
                    }}
                    style={{
                      padding: 20,
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      border: "1px solid var(--color-border)",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <Briefcase size={16} className="good-icon" />
                        <span className="pill" style={{ margin: 0 }}>
                          {job.department || "General"}
                        </span>
                      </div>
                      <h3 style={{ margin: "0 0 6px 0", fontSize: 17 }}>{job.title}</h3>
                      <p className="muted-note" style={{ fontSize: 13, margin: 0 }}>
                        {job.location || "Remote"} · {job.type || "Full-time"}
                      </p>
                    </div>

                    <div
                      style={{
                        marginTop: 18,
                        paddingTop: 12,
                        borderTop: "1px solid var(--color-border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <span className="chip neutral">{count} candidate{count === 1 ? "" : "s"}</span>
                      <span className="btn btn-secondary btn-small">View Ranking &rarr;</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="section-head">
            <div>
              <p className="eyebrow">MATCHING RESULTS</p>
              <h2>Candidate Ranking · {selectedJob?.title || "Job"}</h2>
              <p className="muted-note">
                Showing candidates ranked for {selectedJob?.title || "selected job"}.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => updateParams({ jobId: null })}
              aria-label="Switch selected job"
            >
              Change Job
            </button>
          </div>

          <div className="matching-compare-toolbar" role="group" aria-label="Candidate comparison">
            <div>
              <strong>Compare candidates</strong>
              <span>Select 2–{MAX_COMPARE_CANDIDATES} for a side-by-side view of this job’s persisted scores and evidence.</span>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={compareIds.length < 2}
              onClick={openComparison}
            >
              <GitCompareArrows size={16} /> Compare selected ({compareIds.length})
            </button>
          </div>
          {compareNotice && <p className="form-error" role="status">{compareNotice}</p>}

          <div className="toolbar">
            <div className="search">
              <Search size={18} aria-hidden="true" />
              <input
                placeholder="Search by candidate or status..."
                value={skillSearch}
                onChange={(e) => updateParams({ search: e.target.value })}
                aria-label="Search by candidate or status"
              />
            </div>

            <select
              value={selectedJobId}
              onChange={(e) => updateParams({ jobId: e.target.value })}
              aria-label="Filter results by job"
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title}
                </option>
              ))}
            </select>

            <select
              value={groupFilter}
              onChange={(e) => updateParams({ group: e.target.value })}
              aria-label="Filter results by backend score band"
            >
              <option value="all">All Groups</option>
              <option value="must_review">Must Review (70+)</option>
              <option value="consider">Consider (40-69)</option>
              <option value="lower_priority">Lower Priority (&lt;40)</option>
            </select>

            <select
              value={minScore}
              onChange={(e) => updateParams({ minScore: Number(e.target.value) })}
              aria-label="Filter results by minimum score"
            >
              <option value={0}>Any Score</option>
              <option value={40}>40+ (Consider & Above)</option>
              <option value={70}>70+ (Must Review)</option>
              <option value={85}>85+ (Strong Match)</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => updateParams({ status: e.target.value })}
              aria-label="Filter results by application status"
            >
              <option value="all">All Statuses</option>
              <option value="ready_for_review">Ready for Review</option>
              <option value="advanced">Advanced</option>
              <option value="hold">Hold</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {actionError && (
            <p className="form-error" role="alert">
              {actionError}
            </p>
          )}

          {successNotice && (
            <div className="polite-notice" role="status" aria-live="polite" style={{ marginBottom: 12 }}>
              {successNotice}
            </div>
          )}

          {!filteredCandidates.length ? (
            <EmptyState message="No candidates match your filters for this job." />
          ) : (
            <>
              <div
                className="ranking-list"
                aria-label={`Candidate ranking for ${selectedJob?.title || "selected job"}`}
              >
                {paginatedPrimary.map((r, i) => renderCandidateRow(r, (page - 1) * PAGE_SIZE + i))}
              </div>

              <Pagination
                total={primaryCandidates.length}
                pageSize={PAGE_SIZE}
                page={page}
                onPageChange={(nextPage) => updateParams({ page: nextPage })}
              />

              {lowerPriorityCandidates.length > 0 && (
                <div className="lower-priority-wrapper" style={{ marginTop: 24 }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowLowerPriority((prev) => !prev)}
                    aria-expanded={showLowerPriority}
                    aria-controls="lower-priority-candidates-list"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      fontWeight: 600,
                      marginBottom: 12,
                    }}
                  >
                    {showLowerPriority ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <span>
                      {showLowerPriority ? "Hide" : "Show"} Lower Priority Candidates ({lowerPriorityCandidates.length})
                    </span>
                  </button>

                  {showLowerPriority && (
                    <div
                      id="lower-priority-candidates-list"
                      className="ranking-list"
                      aria-label="Lower Priority Candidates"
                    >
                      {lowerPriorityCandidates.map((r, i) =>
                        renderCandidateRow(r, primaryCandidates.length + i)
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}

      {pendingDecision && (
        <Modal
          open={!!pendingDecision}
          onClose={() => {
            if (!submittingDecision) {
              setPendingDecision(null);
              setDecisionReason("");
              setActionError(null);
            }
          }}
          title={`Confirm ${DECISION_NAMES[pendingDecision.decision]}: ${pendingDecision.row.candidateName}`}
        >
          <p>
            Are you sure you want to record the decision <strong>{DECISION_NAMES[pendingDecision.decision]}</strong> for candidate{" "}
            <strong>{pendingDecision.row.candidateName}</strong> for <strong>{pendingDecision.row.jobTitle}</strong>?
          </p>

          <label
            htmlFor="decision-reason"
            style={{ display: "block", marginTop: 14, marginBottom: 4, fontWeight: 600, fontSize: 13 }}
          >
            Reason (optional):
          </label>
          <textarea
            id="decision-reason"
            rows={3}
            placeholder="Enter reason for audit record (optional)…"
            value={decisionReason}
            onChange={(e) => setDecisionReason(e.target.value)}
            disabled={submittingDecision}
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              fontFamily: "inherit",
              fontSize: 13,
            }}
          />

          {actionError && (
            <p className="form-error" role="alert" style={{ marginTop: 12 }}>
              {actionError}
            </p>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setPendingDecision(null);
                setDecisionReason("");
                setActionError(null);
              }}
              disabled={submittingDecision}
            >
              Cancel
            </button>
            <button
              type="button"
              className={`btn btn-${DECISION_VARIANTS[pendingDecision.decision] || "primary"}`}
              onClick={onConfirmDecision}
              disabled={submittingDecision}
            >
              {submittingDecision ? "Saving…" : `Confirm ${DECISION_NAMES[pendingDecision.decision]}`}
            </button>
          </div>
        </Modal>
      )}
      <Modal
        open={compareOpen}
        title={`Compare candidates · ${selectedJob?.title || "Selected job"}`}
        onClose={() => setCompareOpen(false)}
      >
        {compareLoading ? (
          <p className="muted-note" role="status">Loading persisted evaluations and evidence…</p>
        ) : compareError ? (
          <div className="form-error" role="alert">{compareError}</div>
        ) : (
          <div className="candidate-comparison">
            <p className="muted-note">
              This view aligns the current saved evidence for this job. It does not recalculate scores or recommend a hiring decision.
            </p>
            <div className="candidate-comparison-grid" style={{ "--comparison-count": compareBundles.length }}>
              <div className="candidate-comparison-label"><strong>Current evaluation</strong></div>
              {compareBundles.map((bundle) => (
                <div className="candidate-comparison-cell" key={bundle.application.id}>
                  <strong>{bundle.candidate?.name || "Candidate"}</strong>
                      <span>Score: {formatScore(bundle.poolRow?.score)}</span>
                      <span>
                        HR decision: {{ advance: "Advance", hold: "Hold", reject: "Reject" }[
                          bundle.poolRow?.decision
                        ] || "Not recorded"}
                      </span>
                </div>
              ))}

              {(() => {
                const requirements = new Map();
                compareBundles.forEach((bundle) => {
                  (bundle.evidence || []).forEach((item) => {
                    const key = item?.requirement_ref?.requirement_key;
                    if (key && !requirements.has(key)) requirements.set(key, evidenceLabel(item));
                  });
                });
                if (requirements.size === 0) {
                  return (
                    <div className="candidate-comparison-empty" role="status" key="no-evidence">
                      No persisted requirement evidence is available for the selected applications.
                    </div>
                  );
                }
                return [...requirements].map(([key, label]) => (
                  <React.Fragment key={key}>
                    <div className="candidate-comparison-label">{label}</div>
                    {compareBundles.map((bundle) => {
                      const item = evidenceForRequirement(bundle, key);
                      const type = item?.evidence_type;
                      const quote = item?.candidate_evidence?.quote;
                      const verifiedQuote = item?.candidate_evidence?.quote_verified === true && typeof quote === "string";
                      return (
                        <div className="candidate-comparison-cell" key={`${bundle.application.id}-${key}`}>
                          <span className={`comparison-evidence comparison-${type || "unavailable"}`}>
                            {type === "matched" ? "Matched" : type === "partial" ? "Partial" : type === "missing" ? "No evidence recorded" : "Not available"}
                          </span>
                          {verifiedQuote && <blockquote dir="auto">“{quote}”</blockquote>}
                        </div>
                      );
                    })}
                  </React.Fragment>
                ));
              })()}
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}
