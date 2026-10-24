import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  Trash2,
  Plus,
  Lock,
  CalendarClock,
  MessageSquareText,
} from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import {
  generateQuestionSet,
  listQuestionSets,
  updateQuestionSet,
  approveQuestionSet,
} from "../../services/interviewQuestionSetService";
import { getReviewBundle } from "../../services/reviewService";

const CATEGORIES = ["technical", "behavioral", "situational", "candidate_specific"];

const CATEGORY_LABELS = {
  technical: "Technical",
  behavioral: "Behavioral",
  situational: "Situational",
  candidate_specific: "Candidate-Specific",
};

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

function blankQuestion() {
  return { category: "technical", text: "", topic: "", requirementKey: null };
}

const EVIDENCE_BASIS_LABELS = {
  verified_cv_evidence: "Verified CV evidence",
  verification_question: "Check this with the candidate",
  job_requirement: "Job requirement",
};

function QuestionReviewGuide({ guide }) {
  if (!guide) {
    return (
      <p className="qs-guide-legacy">
        No structured review guidance is available for this saved question.
      </p>
    );
  }

  return (
    <div className="qs-review-guide">
      <span className="qs-guide-basis">
        {EVIDENCE_BASIS_LABELS[guide.evidenceBasis] || "Review guidance"}
      </span>
      <p><strong>Purpose:</strong> {guide.purpose}</p>
      {guide.sourceQuote && (
        <blockquote dir="auto">
          <strong>CV evidence:</strong> “{guide.sourceQuote}”
        </blockquote>
      )}
      <p><strong>Listen for:</strong> {guide.interviewerLooksFor}</p>
      {Array.isArray(guide.evaluationRubric) && guide.evaluationRubric.length > 0 && (
        <div>
          <strong>Consistent rubric</strong>
          <ul>
            {guide.evaluationRubric.map((criterion, index) => (
              <li key={`${index}-${criterion}`}>{criterion}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function QuestionSetBuilder() {
  const { id: applicationId } = useParams();
  const navigate = useNavigate();

  const [context, setContext] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");
  const [approveOpen, setApproveOpen] = useState(false);
  const [approveError, setApproveError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [bundle, sets] = await Promise.all([
        getReviewBundle(applicationId),
        listQuestionSets(applicationId),
      ]);
      setContext(bundle);
      setVersions(sets.questionSets);
      const preferred =
        sets.questionSets.find((s) => s.status === "generated") ||
        sets.questionSets.find((s) => s.isCurrent) ||
        sets.questionSets[0] ||
        null;
      setSelectedId(preferred ? preferred.id : null);
    } catch (err) {
      setLoadError(extractError(err));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => versions.find((v) => v.id === selectedId) || null,
    [versions, selectedId]
  );
  const isEditable = selected?.status === "generated";
  const approvedSet = versions.find((v) => v.status === "approved") || null;

  const selectVersion = (version) => {
    setSelectedId(version.id);
    setNotice("");
    setFailure("");
  };

  // Keep the draft in sync when a generated version becomes the active one.
  useEffect(() => {
    if (selected && selected.status === "generated" && draft === null) {
      setDraft(selected.questions.map((q) => ({ ...q })));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, selected?.status]);

  const dirty = useMemo(() => {
    if (!selected || selected.status !== "generated" || !draft) return false;
    return JSON.stringify(draft) !== JSON.stringify(selected.questions.map((q) => ({ ...q })));
  }, [selected, draft]);

  const patchDraft = (index, patch) => {
    setDraft((prev) => prev.map((q, i) => (i === index ? { ...q, ...patch } : q)));
  };

  const move = (index, direction) => {
    setDraft((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const addQuestion = () => {
    setDraft((prev) => [...prev, blankQuestion()]);
  };

  const removeQuestion = (index) => {
    setDraft((prev) => prev.filter((_, i) => i !== index));
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setNotice("");
    setFailure("");
    try {
      const created = await generateQuestionSet(applicationId);
      setNotice(`Generated ${created.questions.length} questions (v${created.versionNumber}). Review, edit, then approve.`);
      const sets = await listQuestionSets(applicationId);
      setVersions(sets.questionSets);
      setSelectedId(created.id);
      setDraft(created.questions.map((q) => ({ ...q })));
    } catch (err) {
      setFailure(extractError(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!selected || !draft || !draft.filter((q) => q.text.trim()).length) {
      setFailure("Please add at least one question with text before saving.");
      return;
    }
    setSaving(true);
    setNotice("");
    setFailure("");
    try {
      const saved = await updateQuestionSet(selected.id, draft);
      setNotice(`Saved changes to v${saved.versionNumber}. Remember to approve before scheduling.`);
      setVersions((prev) =>
        prev.map((v) => (v.id === saved.id ? saved : v))
      );
      setDraft(saved.questions.map((q) => ({ ...q })));
    } catch (err) {
      setFailure(extractError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    if (!selected) return;
    setApproving(true);
    setApproveError("");
    try {
      const approved = await approveQuestionSet(selected.id);
      setApproveOpen(false);
      setNotice(`Question set v${approved.versionNumber} approved and set as current.`);
      const sets = await listQuestionSets(applicationId);
      setVersions(sets.questionSets);
      setSelectedId(approved.id);
      setDraft(null);
    } catch (err) {
      setApproveError(extractError(err));
    } finally {
      setApproving(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading question sets..." />;
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
  if (!context) {
    return (
      <section>
        <button className="back" onClick={() => navigate("/applications")}>
          <ArrowLeft size={17} /> Back to Applications
        </button>
        <div className="empty">Application not found.</div>
      </section>
    );
  }

  const { candidate, job } = context;

  return (
    <section>
      <button className="back" onClick={() => navigate(`/applications/${applicationId}/review`)}>
        <ArrowLeft size={17} /> Back to {candidate?.name || "Application"}
      </button>

      <div className="section-head">
        <div>
          <p className="eyebrow">INTERVIEW QUESTIONS</p>
          <h2>
            Questions — {candidate?.name || "Candidate"} · {job?.title || "Job"}
          </h2>
        </div>
        <button className="primary" onClick={handleGenerate} disabled={generating}>
          {generating ? (
            <RefreshCw size={16} className="spin" />
          ) : (
            <Sparkles size={16} />
          )}
          {generating ? "Generating..." : "Generate Questions with AI"}
        </button>
      </div>

      {notice && (
        <div className="success-message" style={{ marginBottom: 14 }}>
          <CheckCircle2 size={16} style={{ marginRight: 6, verticalAlign: "-3px" }} />
          {notice}
        </div>
      )}
      {failure && (
        <div className="form-error" style={{ marginBottom: 14 }}>
          <AlertCircle size={14} style={{ marginRight: 6, verticalAlign: "-3px" }} />
          {failure}
        </div>
      )}

      <p className="muted-note" style={{ marginBottom: 14, maxWidth: 720 }}>
        The AI drafts a question set from the approved job requirements and the candidate's profile.
        You can edit, reorder, add or remove questions, then approve the set before attaching it to an
        interview. Approved sets are locked.
      </p>

      {/* ===== Version selector ===== */}
      <div className="filter-tabs" style={{ marginBottom: 16 }}>
        {versions.length === 0 && (
          <span className="muted-note">No question sets yet — generate one to begin.</span>
        )}
        {versions.map((version) => (
          <button
            key={version.id}
            type="button"
            className={`filter-tab ${selectedId === version.id ? "active" : ""}`}
            onClick={() => selectVersion(version)}
          >
            v{version.versionNumber} · {version.statusLabel}
            {version.isCurrent && <span className="tab-count">current</span>}
          </button>
        ))}
      </div>

      {!selected ? (
        <div className="panel">
          <div className="empty">
            Generate a question set with the AI button above. HR can then pick, edit, and approve it.
          </div>
        </div>
      ) : (
        <div className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">SET v{selected.versionNumber}</p>
              <h3>{selected.statusLabel}</h3>
            </div>
            {selected.isCurrent && <span className="chip good">Current approved set</span>}
          </div>

          <div className="muted-note" style={{ fontSize: 12, marginBottom: 14 }}>
            AI model: {selected.generatedBy || "—"} · Created {formatTimestamp(selected.createdAt)}
            {selected.approvedAt
              ? ` · Approved ${formatTimestamp(selected.approvedAt)}`
              : " · Not approved yet"}
          </div>

          {!isEditable && (
            <div className="form-error" style={{ marginBottom: 14 }}>
              <Lock size={14} style={{ marginRight: 6, verticalAlign: "-3px" }} />
              This set is {selected.statusLabel.toLowerCase()} and locked. Generate a new version to
              change the questions.
            </div>
          )}

          {isEditable && draft ? (
            <>
              <div className="question-list" style={{ gap: 10 }}>
                {draft.map((question, index) => (
                  <div className="question-item qs-editor-row" key={index === undefined ? index : `${question.id || "new"}-${index}`}>
                    <div className="qs-editor-controls">
                      <button
                        type="button"
                        className="qs-icon-btn"
                        onClick={() => move(index, -1)}
                        disabled={index === 0}
                        aria-label="Move up"
                      >
                        <ChevronUp size={15} />
                      </button>
                      <button
                        type="button"
                        className="qs-icon-btn"
                        onClick={() => move(index, 1)}
                        disabled={index === draft.length - 1}
                        aria-label="Move down"
                      >
                        <ChevronDown size={15} />
                      </button>
                    </div>
                    <div className="qs-editor-fields">
                      <div className="qs-editor-meta">
                        <select
                          value={question.category}
                          onChange={(e) => patchDraft(index, { category: e.target.value })}
                          aria-label="Category"
                        >
                          {CATEGORIES.map((cat) => (
                            <option key={cat} value={cat}>
                              {CATEGORY_LABELS[cat]}
                            </option>
                          ))}
                        </select>
                        <input
                          value={question.topic ?? ""}
                          onChange={(e) => patchDraft(index, { topic: e.target.value })}
                          placeholder="Topic (optional)"
                          aria-label="Topic"
                        />
                        {question.requirementKey && (
                          <span className="chip">Req {question.requirementKey}</span>
                        )}
                      </div>
                      <textarea
                        value={question.text}
                        onChange={(e) => patchDraft(index, { text: e.target.value })}
                        placeholder="Question text…"
                        rows={2}
                        aria-label="Question text"
                      />
                      <QuestionReviewGuide guide={question.reviewGuide} />
                    </div>
                    <button
                      type="button"
                      className="qs-icon-btn qs-remove"
                      onClick={() => removeQuestion(index)}
                      aria-label="Remove question"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>

              <button type="button" className="btn-secondary" onClick={addQuestion} style={{ marginTop: 12 }}>
                <Plus size={15} /> Add Question
              </button>

              <div className="modal-actions" style={{ marginTop: 20, justifyContent: "flex-end" }}>
                <button className="primary" onClick={handleSave} disabled={saving || !dirty}>
                  {saving ? "Saving..." : "Save Changes"}
                </button>
                <button className="btn btn-danger" onClick={() => setApproveOpen(true)}>
                  <CheckCircle2 size={16} /> Approve Set
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="question-list">
                {selected.questions.map((q, index) => (
                  <div className="question-item qs-readonly-item" key={q.id || index}>
                    <div className="qs-readonly-question">
                      <span className="chip">{q.categoryLabel}</span>
                      <span style={{ flex: 1 }}>{q.text}</span>
                    </div>
                    <QuestionReviewGuide guide={q.reviewGuide} />
                  </div>
                ))}
              </div>

              {selected.status !== "approved" && approvedSet && (
                <p className="muted-note" style={{ marginTop: 12 }}>
                  An approved set (v{approvedSet.versionNumber}) already exists. Approving a new version
                  supersedes the old one.
                </p>
              )}

              {approvedSet && approvedSet.id === selected.id && (
                <div className="selected-appointment" style={{ marginTop: 16 }}>
                  <CalendarClock size={20} />
                  <div>
                    <span>Ready for scheduling</span>
                    <strong>
                      Attach this question set to an interview so the interviewer uses it.
                    </strong>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ marginLeft: "auto" }}
                    onClick={() =>
                      navigate(`/interviews/schedule?applicationId=${applicationId}&questionSetId=${selected.id}`)
                    }
                  >
                    <MessageSquareText size={16} /> Schedule with this set
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ===== Approve confirm modal ===== */}
      <Modal open={approveOpen} title="Approve question set?" onClose={() => setApproveOpen(false)}>
        <p style={{ marginBottom: 12 }}>
          Approving v{selected?.versionNumber} locks the questions and makes it the current approved set
          for this application. It can no longer be edited; only newer generated versions can change it.
          {approvedSet && approvedSet.id !== selected?.id
            ? ` The previous approved set (v${approvedSet.versionNumber}) becomes superseded.`
            : ""}
        </p>
        {approveError && (
          <div className="form-error" style={{ marginBottom: 12 }}>
            <AlertCircle size={14} style={{ marginRight: 6 }} />
            {approveError}
          </div>
        )}
        <div className="modal-actions">
          <button className="btn-secondary" onClick={() => setApproveOpen(false)} disabled={approving}>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={handleApprove} disabled={approving}>
            {approving ? "Approving..." : "Confirm Approval"}
          </button>
        </div>
      </Modal>
    </section>
  );
}
