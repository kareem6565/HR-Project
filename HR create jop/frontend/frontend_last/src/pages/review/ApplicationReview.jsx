import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock3,
  RefreshCw,
  FileText,
  User,
  ShieldCheck,
  MapPin,
  Mail,
  Phone,
  Briefcase,
  GraduationCap,
  Link2,
  Globe,
  Download,
  Languages,
  MessageSquareText,
  Copy,
} from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import EmptyState from "../../components/common/EmptyState";
import Badge from "../../components/common/Badge";
import Modal from "../../components/common/Modal";
import EvaluationSummary from "../../components/evaluation/EvaluationSummary";
import EvidenceTable from "../../components/evaluation/EvidenceTable";
import LimitationsNote from "../../components/evaluation/LimitationsNote";
import DecisionBar from "../../components/review/DecisionBar";
import PipelineActions from "../../components/common/PipelineActions";
import { HRDecisionValue } from "../../types/api";
import { getReviewWorkspace, runEvaluation, recordDecision } from "../../services/reviewService";
import { downloadResume } from "../../services/resumeService";
import { formatScore, parseScore } from "../../utils/score";
import { BAND_CONFIG } from "../../components/common/ScoreBadge";
import { getApplicationStatusGroup } from "../../utils/applicationStatus";
import { createCandidateInterviewInvitation } from "../../services/interviewService";

const DECISION_LABELS = {
  [HRDecisionValue.ADVANCE]: "Advance",
  [HRDecisionValue.HOLD]: "Hold",
  [HRDecisionValue.REJECT]: "Reject",
};

const DECISION_TONE = {
  [HRDecisionValue.ADVANCE]: "green",
  [HRDecisionValue.HOLD]: "amber",
  [HRDecisionValue.REJECT]: "red",
};

const DECISION_ICON = {
  [HRDecisionValue.ADVANCE]: CheckCircle2,
  [HRDecisionValue.HOLD]: Clock3,
  [HRDecisionValue.REJECT]: XCircle,
};

const EVALUATION_STATUS_TONE = {
  completed: "green",
  running: "blue",
  queued: "blue",
  failed: "red",
  superseded: "grey",
};

function normalizeStatus(status) {
  return String(status || "")
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function extractError(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return "The operation failed. Please try again.";
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return null;
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatProfileItem(item) {
  if (typeof item === "string") return item;
  if (!item || typeof item !== "object") return String(item || "");
  const parts = [
    item.title || item.role || item.position || item.degree || item.name,
    item.company || item.organization || item.institution || item.school || item.issuer,
    item.duration || item.period || item.year || item.date,
    item.description || item.summary,
  ].filter(Boolean);
  if (parts.length > 0) return parts.join(" — ");
  return (
    Object.values(item)
      .filter((v) => typeof v === "string" || typeof v === "number")
      .join(" · ") || "—"
  );
}

const PROFILE_SECTION_HEADINGS = new Set([
  "summary",
  "professional summary",
  "profile",
  "professional profile",
  "experience",
  "professional experience",
  "employment",
  "work history",
  "education",
  "academic background",
  "certification",
  "certifications",
  "license",
  "licenses",
  "skills",
  "languages",
  "projects",
  "publications",
  "references",
  "awards",
  "volunteer",
  "volunteer experience",
]);

export function filterCertificationHeadings(entries) {
  return (Array.isArray(entries) ? entries : []).filter(
    (entry) =>
      typeof entry !== "string" ||
      !PROFILE_SECTION_HEADINGS.has(entry.trim().replace(/:$/, "").replace(/\s+/g, " ").toLowerCase()),
  );
}

export default function ApplicationReview() {
  const { id: applicationId } = useParams();
  const navigate = useNavigate();
  const routerLocation = useLocation();

  const [bundle, setBundle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [evaluating, setEvaluating] = useState(false);
  const [evalError, setEvalError] = useState(null);

  const [decisionModal, setDecisionModal] = useState({ open: false, decision: null });
  const [decisionReason, setDecisionReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [decisionError, setDecisionError] = useState(null);
  const [isConflictError, setIsConflictError] = useState(false);

  const [successMsg, setSuccessMsg] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [cvError, setCvError] = useState("");
  const [interviewInviteBusy, setInterviewInviteBusy] = useState(false);
  const [interviewInviteUrl, setInterviewInviteUrl] = useState("");
  const [interviewInviteMessage, setInterviewInviteMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getReviewWorkspace(applicationId);
      setBundle(data);
    } catch (err) {
      setLoadError(extractError(err));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSpinner label="Loading review workspace…" />;
  if (loadError) {
    return (
      <section>
        <button className="back" onClick={() => navigate("/applications")}>
          <ArrowLeft size={17} /> Back to Applications
        </button>
        <ErrorState message={loadError} onRetry={load} />
      </section>
    );
  }
  if (!bundle) {
    return (
      <section>
        <button className="back" onClick={() => navigate("/applications")}>
          <ArrowLeft size={17} /> Back to Applications
        </button>
        <div className="empty">Application not found.</div>
      </section>
    );
  }

  const { application, candidate, job, evaluation, evidence, poolRow, resume, profile } = bundle;

  const hasEvaluation = !!evaluation;
  const score = parseScore(evaluation?.score);
  const group = poolRow?.group;
  const applicationStatusGroup = getApplicationStatusGroup(application.status);
  const currentDecision = poolRow?.decision;
  const DecisionIcon = currentDecision ? DECISION_ICON[currentDecision] || Clock3 : Clock3;
  const signalsCount = (evidence || []).filter((e) => {
    const key = e?.requirement_ref?.requirement_key;
    const cat = key ? evaluation?.score_breakdown?.[key]?.category : e?.requirement_ref?.category;
    const isMustHave = cat === "must_have" || cat === "Must-Have";
    return e?.evidence_type === "missing" && isMustHave;
  }).length;

  const profileData = profile?.profile_data || {};
  const skills = Array.isArray(profileData.skills) ? profileData.skills : Array.isArray(candidate?.skills) ? candidate.skills : [];
  const experience = Array.isArray(profileData.experience) ? profileData.experience : [];
  const education = Array.isArray(profileData.education) ? profileData.education : [];
  const languages = Array.isArray(profileData.languages) ? profileData.languages : [];
  const certifications = filterCertificationHeadings(profileData.certifications);
  const location = profileData.location || profileData.city || candidate?.location || null;
  const summary = profileData.summary || candidate?.summary || null;
  const contact = {
    email: profileData.email || candidate?.email || null,
    phone: profileData.phone || candidate?.phone || null,
  };
  const withScheme = (value) =>
    value && !/^https?:\/\//i.test(value) ? `https://${value}` : value;

  const profileLinks = [
    { label: "LinkedIn", url: profileData.linkedin_url, icon: Link2 },
    { label: "GitHub", url: profileData.github_url, icon: Link2 },
    { label: "Portfolio", url: profileData.portfolio_url, icon: Globe },
  ]
    .filter((link) => link.url)
    .map((link) => ({ ...link, url: withScheme(link.url) }));

  const handleDownloadCv = async () => {
    if (!resume?.id) return;
    setDownloading(true);
    setCvError("");
    try {
      const { blob, filename } = await downloadResume(resume.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setCvError(extractError(err));
    } finally {
      setDownloading(false);
    }
  };

  const handleEvaluate = async () => {
    setEvaluating(true);
    setEvalError(null);
    setSuccessMsg("");
    try {
      const result = await runEvaluation(applicationId);
      setSuccessMsg(`Evaluation v${result.version_number} completed.`);
      await load();
    } catch (err) {
      setEvalError(extractError(err));
    } finally {
      setEvaluating(false);
    }
  };

  const openDecision = (decision) => {
    setDecisionModal({ open: true, decision });
    setDecisionReason("");
    setDecisionError(null);
    setIsConflictError(false);
  };

  const handleDecision = async (andNext = false) => {
    if (saving || !decisionModal.decision) return;
    setSaving(true);
    setDecisionError(null);
    setIsConflictError(false);
    try {
      if (evaluation?.id) {
        await recordDecision(applicationId, decisionModal.decision, decisionReason, evaluation.id);
      } else {
        await recordDecision(applicationId, decisionModal.decision, decisionReason);
      }
      setSuccessMsg(`${DECISION_LABELS[decisionModal.decision]} recorded for ${candidate?.name || "this candidate"}.`);
      setDecisionModal({ open: false, decision: null });

      if (andNext) {
        const candidateIds = Array.isArray(routerLocation.state?.candidateIds) ? routerLocation.state.candidateIds : [];
        const currentIdx = candidateIds.indexOf(applicationId);
        if (currentIdx !== -1 && currentIdx + 1 < candidateIds.length) {
          const nextAppId = candidateIds[currentIdx + 1];
          navigate(`/applications/${nextAppId}/review`, { state: routerLocation.state });
          return;
        }
        // Fallback to selected job's results page or general matching
        const targetJobId = routerLocation.state?.jobId || bundle?.job?.id;
        if (targetJobId) {
          navigate(`/matching?jobId=${targetJobId}`);
        } else {
          navigate("/matching");
        }
      } else {
        await load();
      }
    } catch (err) {
      const isConflict =
        err?.response?.status === 409 ||
        String(err?.message || "").includes("409") ||
        String(err?.response?.data?.detail || "").toLowerCase().includes("stale") ||
        String(err?.response?.data?.detail || "").toLowerCase().includes("superseded");

      setIsConflictError(isConflict);
      if (isConflict) {
        setDecisionError(
          "Evaluation Conflict (409): The evaluation was updated or superseded while this page was open. To protect recruitment decision integrity, your decision was not saved. Please reload the latest evaluation before deciding."
        );
      } else {
        setDecisionError(extractError(err));
      }
    } finally {
      setSaving(false);
    }
  };

  const createInterviewInvite = async () => {
    setInterviewInviteBusy(true);
    setInterviewInviteMessage("");
    setInterviewInviteUrl("");
    try {
      const invitation = await createCandidateInterviewInvitation(applicationId);
      setInterviewInviteUrl(`${window.location.origin}/interview/schedule#${invitation.token}`);
      setInterviewInviteMessage("Link created. Share it with the candidate; it expires in 7 days and can schedule one interview.");
    } catch (err) {
      setInterviewInviteMessage(extractError(err));
    } finally {
      setInterviewInviteBusy(false);
    }
  };

  const copyInterviewInvite = async () => {
    try {
      await navigator.clipboard.writeText(interviewInviteUrl);
      setInterviewInviteMessage("Interview link copied.");
    } catch {
      setInterviewInviteMessage("Copy is unavailable here. Select and copy the link below.");
    }
  };

  return (
    <section>
      <div className="review-workspace-top">
        <button type="button" className="back" onClick={() => navigate("/applications")}>
          <ArrowLeft size={17} aria-hidden="true" /> Back to Applications
        </button>
        <a className="btn btn-secondary btn-small" href="#hr-decision">
          Go to HR decision <ArrowDown size={14} aria-hidden="true" />
        </a>
      </div>

      {/* ===== Global Notification Banners ===== */}
      {successMsg && (
        <div className="success-message" style={{ marginBottom: 14 }}>
          <CheckCircle2 size={16} style={{ marginRight: 6, verticalAlign: "-3px" }} />
          {successMsg}
        </div>
      )}
      {evalError && (
        <div className="form-error" style={{ marginBottom: 14 }}>
          <AlertCircle size={14} style={{ marginRight: 6 }} />
          {evalError}
        </div>
      )}

      <div className="review-summary-shell">
      <header className="review-workspace-heading" aria-labelledby="review-candidate-name">
        <div className="review-workspace-identity">
          <div className="big-avatar" aria-hidden="true">
            {(candidate?.name || "C")
              .split(" ")
              .map((part) => part[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div>
            <p className="eyebrow">APPLICATION REVIEW</p>
            <h1 id="review-candidate-name" dir="auto">{candidate?.name || "Candidate"}</h1>
            <p className="review-role-line">
              Applied for <strong dir="auto">{job?.title || "Role not available"}</strong>
            </p>
          </div>
        </div>
        <span className="review-human-authority">Final hiring decisions remain with HR.</span>
      </header>

      {/* ===== Status Strip Summary ===== */}
      <div className="status-strip review-status-strip" role="group" aria-label="Application review summary">
        <span className="status-item">
          <span>
            {applicationStatusGroup?.id === "processing"
              ? "Processing status"
              : applicationStatusGroup?.id === "decision"
                ? "Decision-mirrored application state"
                : applicationStatusGroup?.id === "other"
                  ? "Other application status"
                  : "Application status"}
          </span>
          <strong><Badge status={application.status} /></strong>
        </span>
        <span className="status-item">
          <span>AI Evaluation Status</span>
          <strong>{hasEvaluation ? `v${evaluation.version_number} · ${normalizeStatus(evaluation.status)}` : "Not run yet"}</strong>
        </span>
        <span className="status-item">
          <span>AI Match Score (0–100)</span>
          <strong>{hasEvaluation ? formatScore(score) : "Not available"}</strong>
        </span>
        <span className="status-item">
          <span>AI Review Category</span>
          <strong>
            <span className="application-ai-category">{BAND_CONFIG[group]?.label || "Not available"}</span>
          </strong>
        </span>
        <span className="status-item">
          <span>Human HR Decision</span>
          <strong>
            {currentDecision ? (
              <span className={`badge badge-${DECISION_TONE[currentDecision] || "grey"}`}>
                <DecisionIcon size={13} aria-hidden="true" />
                {DECISION_LABELS[currentDecision] || normalizeStatus(currentDecision)}
              </span>
            ) : "No decision recorded"}
          </strong>
        </span>
        <span className="status-item">
          <span>Review Signals</span>
          <strong>{hasEvaluation ? signalsCount : "—"}</strong>
        </span>
      </div>

      <div className="review-quick-actions">
        <div className="review-quick-actions-copy">
          <strong>Human decision</strong>
          <span>Review the evidence, then choose an action. You will confirm before it is recorded.</span>
        </div>
        <PipelineActions
          currentStatus={currentDecision}
          onDecision={openDecision}
          disabled={saving}
        />
      </div>
      </div>

      {currentDecision === HRDecisionValue.ADVANCE && (
        <section className="panel interview-invite-panel" aria-labelledby="interview-invite-title">
          <div>
            <p className="eyebrow">CANDIDATE SELF-SCHEDULING</p>
            <h3 id="interview-invite-title">Let the candidate choose a time</h3>
            <p>Publish interviewer availability first. The candidate link opens only the scheduling page and expires after 7 days.</p>
          </div>
          <div className="interview-invite-actions">
            <button type="button" className="primary" onClick={createInterviewInvite} disabled={interviewInviteBusy}>
              {interviewInviteBusy ? "Creating link…" : "Create scheduling link"}
            </button>
            <a href="/interviews/availability">Manage availability</a>
          </div>
          {interviewInviteUrl && (
            <div className="interview-invite-link-row">
              <label htmlFor="candidate-interview-link">Share this link with the candidate</label>
              <div><input id="candidate-interview-link" readOnly value={interviewInviteUrl} /><button type="button" className="btn-secondary" onClick={copyInterviewInvite}><Copy size={15} aria-hidden="true" /> Copy link</button></div>
              <small>Creating another link invalidates the previous unused link. The candidate can book once. To reschedule, cancel the existing interview first, then issue a new link.</small>
            </div>
          )}
          {interviewInviteMessage && <p className="interview-invite-message" role="status">{interviewInviteMessage}</p>}
        </section>
      )}

      {/* =======================================================
          1. CANDIDATE PROFILE (AI Assisted)
          ======================================================= */}
      <div className="panel review-block">
        <div className="review-block-title">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <User size={18} />
            <h3>Candidate Profile</h3>
          </div>
          <span className="flag flag-ai">
            <Sparkles size={12} /> AI Assisted Profile
          </span>
        </div>

        {summary && <p className="muted-note" dir="auto" style={{ margin: "0 0 16px" }}>{summary}</p>}

        <div className="review-stack" style={{ marginBottom: 16 }}>
          <div className="info">
            <span><Mail size={13} style={{ display: "inline", verticalAlign: "-2px", marginRight: 4 }} /> Contact · Email</span>
            <strong>{contact.email || "—"}</strong>
          </div>
          <div className="info">
            <span><Phone size={13} style={{ display: "inline", verticalAlign: "-2px", marginRight: 4 }} /> Contact · Phone</span>
            <strong>{contact.phone || "—"}</strong>
          </div>
          {location && (
            <div className="info">
              <span><MapPin size={13} style={{ display: "inline", verticalAlign: "-2px", marginRight: 4 }} /> Location</span>
              <strong dir="auto">{location}</strong>
            </div>
          )}
        </div>

        <div style={{ marginTop: 16 }}>
          <h4><Briefcase size={15} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} /> Experience</h4>
          {experience.length ? (
            <ul className="strengths-list" style={{ marginBottom: 12 }}>
              {experience.map((item, i) => (
                <li key={i} dir="auto">{formatProfileItem(item)}</li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No experience entries in the extracted candidate profile." />
          )}
        </div>

        {(profileLinks.length > 0 || education.length > 0 || languages.length > 0 || certifications.length > 0) && (
          <details className="review-profile-more">
            <summary>Additional profile details</summary>
            <div className="review-profile-more-content">
              {profileLinks.length > 0 && (
                <div>
                  <h4>Links</h4>
                  <div className="review-profile-links">
                    {profileLinks.map((link) => {
                      const LinkIcon = link.icon;
                      return (
                        <a
                          key={link.label}
                          href={link.url}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-secondary btn-small"
                        >
                          <LinkIcon size={14} aria-hidden="true" /> {link.label}
                        </a>
                      );
                    })}
                  </div>
                </div>
              )}

              {education.length > 0 && (
                <div>
                  <h4><GraduationCap size={15} aria-hidden="true" /> Education</h4>
                  <ul className="strengths-list">
                    {education.map((item, i) => (
                      <li key={i} dir="auto">{formatProfileItem(item)}</li>
                    ))}
                  </ul>
                </div>
              )}

              {languages.length > 0 && (
                <div>
                  <h4><Languages size={15} aria-hidden="true" /> Languages</h4>
                  <div className="chips">
                    {languages.map((lang) => (
                      <span className="chip" key={lang}>{lang}</span>
                    ))}
                  </div>
                </div>
              )}

              {certifications.length > 0 && (
                <div>
                  <h4><ShieldCheck size={15} aria-hidden="true" /> Certifications</h4>
                  <ul className="strengths-list">
                    {certifications.map((cert, i) => (
                      <li key={i} dir="auto">{formatProfileItem(cert)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>
        )}

        <div style={{ marginTop: 16 }}>
          <h4>Skills</h4>
          {skills.length ? (
            <div className="chips" style={{ marginBottom: 12 }}>
              {skills.map((s) => (
                <span className="chip good" key={s}>
                  {s}
                </span>
              ))}
            </div>
          ) : (
            <EmptyState message="No skills found in candidate profile." />
          )}
        </div>

        <div style={{ marginTop: 16 }}>
          <h4>Resume Document</h4>
          <div className="resume-meta" style={{ padding: 12, borderRadius: 8, background: "var(--bg-muted, #f8fafc)", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <FileText size={24} style={{ color: "var(--primary-color, #2563eb)" }} />
            <div style={{ flex: 1, minWidth: 180 }}>
              <strong>{resume?.original_filename || "Resume on file"}</strong>
              {(resume?.content_type || formatBytes(resume?.file_size_bytes)) && (
                <div className="muted-note" style={{ fontSize: 13, marginTop: 2 }}>
                  {[resume?.content_type, formatBytes(resume?.file_size_bytes)].filter(Boolean).join(" · ")}
                </div>
              )}
            </div>
            {resume?.id && (
              <button type="button" className="btn btn-secondary btn-small" onClick={handleDownloadCv} disabled={downloading}>
                <Download size={14} /> {downloading ? "Downloading…" : "Download CV"}
              </button>
            )}
          </div>
          {cvError && (
            <div className="form-error" style={{ marginTop: 8 }}>
              <AlertCircle size={14} style={{ marginRight: 6, verticalAlign: "-2px" }} />
              {cvError}
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          2. APPLICATION / JOB CONTEXT (Human Review)
          ======================================================= */}
      <div className="panel review-block">
        <div className="review-block-title">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Briefcase size={18} />
            <h3>Application / Job Context</h3>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="flag flag-human">
              <User size={12} /> Human Review
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={() => navigate(`/applications/${applicationId}/questions`)}
            >
              <MessageSquareText size={14} /> Interview Questions
            </button>
          </div>
        </div>
        <div className="detail-grid review-2col">
          <div>
            <div className="info">
              <span>Candidate</span>
              <strong>{candidate?.name || "—"}</strong>
            </div>
            <div className="info">
              <span>Job Title</span>
              <strong>{job?.title || "—"}</strong>
            </div>
            {job?.department && (
              <div className="info">
                <span>Department</span>
                <strong>{job.department}</strong>
              </div>
            )}
          </div>
          <div>
            <div className="info">
              <span>Application ID</span>
              <strong className="mono">{application.id}</strong>
            </div>
            <div className="info">
              <span>Application Status</span>
              <div>
                <Badge status={application.status} />
              </div>
            </div>
            <div className="info">
              <span>Applied On</span>
              <strong>{formatTimestamp(application.created_at)}</strong>
            </div>
          </div>
        </div>

      </div>

      {/* =======================================================
          3. AI EVALUATION (AI Generated)
          ======================================================= */}
      <div className="panel review-block ai-box">
        <div className="review-block-title">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} />
            <h3>AI Evaluation</h3>
          </div>
          <span className="flag flag-ai">
            <Sparkles size={12} /> AI Generated
          </span>
        </div>

        {!hasEvaluation ? (
          <EmptyState
            icon={Sparkles}
            message="Evaluation not run yet. Running the AI evaluation analyzes the candidate profile against job requirements to produce a score, explanation, breakdown, and evidence."
            action={
              <button type="button" className="primary" onClick={handleEvaluate} disabled={evaluating}>
                {evaluating ? (
                  <>
                    <RefreshCw size={16} className="spin" /> Evaluating…
                  </>
                ) : (
                  <>
                    <Sparkles size={16} /> Evaluate Candidate
                  </>
                )}
              </button>
            }
          />
        ) : (
          <>
            <EvaluationSummary
              evaluation={evaluation}
              group={group}
              onReevaluate={handleEvaluate}
              evaluating={evaluating}
            />

            <div className="evaluation-evidence-section" style={{ marginTop: 24 }}>
              <h4 style={{ margin: "0 0 12px" }}>Requirement Match Evidence</h4>
              <LimitationsNote />
              <EvidenceTable evidence={evidence} breakdown={evaluation.score_breakdown} />
            </div>
          </>
        )}
      </div>

      {/* =======================================================
          8. HR DECISION (Human Decision)
          ======================================================= */}
      <DecisionBar
        currentDecision={currentDecision}
        decisionCreatedAt={poolRow?.decision_created_at}
        onSelectDecision={openDecision}
        disabled={saving}
        showActions={false}
      />

      {/* ===== Decision Confirmation Modal ===== */}
      <Modal
        open={decisionModal.open}
        title={`Confirm HR Decision: ${DECISION_LABELS[decisionModal.decision] || "Decision"}`}
        onClose={() => {
          if (!saving) setDecisionModal({ open: false, decision: null });
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleDecision(false);
          }}
        >
          <p style={{ marginBottom: 12 }}>
            {decisionModal.decision === HRDecisionValue.ADVANCE &&
              `Advancing ${candidate?.name || "this candidate"} moves them forward in the recruitment pipeline.`}
            {decisionModal.decision === HRDecisionValue.HOLD &&
              `Putting ${candidate?.name || "this candidate"} on hold keeps their application active while pausing immediate action.`}
            {decisionModal.decision === HRDecisionValue.REJECT &&
              `Rejecting ${candidate?.name || "this candidate"} records them as not moving forward for this position.`}
          </p>

          <label htmlFor="decision-reason-input" style={{ display: "block", marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 500, display: "block", marginBottom: 4 }}>
              Reason for decision (optional audit note):
            </span>
            <textarea
              id="decision-reason-input"
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
              placeholder="Enter reason for audit record (optional)…"
              rows={3}
              disabled={saving}
              style={{ width: "100%", padding: 8, borderRadius: 6, border: "1px solid var(--border-color, #cbd5e1)" }}
            />
          </label>

          {decisionError && (
            <div className="form-error" role="alert" style={{ marginBottom: 12 }}>
              <AlertCircle size={14} style={{ marginRight: 6, flexShrink: 0 }} aria-hidden="true" />
              <div>
                <span>{decisionError}</span>
                {isConflictError && (
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      onClick={async () => {
                        setDecisionModal({ open: false, decision: null });
                        await load();
                      }}
                    >
                      <RefreshCw size={12} style={{ marginRight: 6 }} aria-hidden="true" /> Reload Latest Evaluation
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="modal-actions" style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                if (!saving) setDecisionModal({ open: false, decision: null });
              }}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="button"
              className={decisionModal.decision === HRDecisionValue.REJECT ? "btn btn-danger" : "btn btn-primary"}
              onClick={() => handleDecision(false)}
              disabled={saving || isConflictError}
            >
              {saving ? "Saving…" : `Confirm ${DECISION_LABELS[decisionModal.decision]}`}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleDecision(true)}
              disabled={saving || isConflictError}
              title="Save decision and proceed to next candidate"
            >
              <span>{saving ? "Saving…" : "Save & Next Candidate"}</span>
              <ArrowRight size={14} style={{ marginLeft: 6 }} aria-hidden="true" />
            </button>
          </div>
        </form>
      </Modal>
    </section>
  );
}
