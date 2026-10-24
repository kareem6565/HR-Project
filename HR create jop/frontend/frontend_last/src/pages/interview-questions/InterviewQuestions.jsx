import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckSquare, Square, ArrowLeft } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import { getCandidateById } from "../../services/candidateService";
import { getInterviewQuestions } from "../../services/interviewQuestionService";
import {
  saveSelectedQuestions,
  listQuestionSets,
} from "../../services/interviewQuestionSetService";
import { getReviewBundle } from "../../services/reviewService";

const CATEGORY_WIRE = {
  Technical: "technical",
  Behavioral: "behavioral",
  Situational: "situational",
  "Candidate-Specific": "candidate_specific",
};

function extractError(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return "Could not save the selected questions. Please try again.";
}

// Application-scoped question preparation ("Interview Prep"). Reached from a
// candidate's profile with an explicit applicationId (the application is
// always chosen first — the system never guesses). Selecting questions and
// saving persists them as an HR draft ("generated") directly on that
// application; approving happens later in the canonical Question Set Builder
// (/applications/{applicationId}/questions). A legacy candidateId-only link
// still browses the banks but cannot save without an application.
export default function InterviewQuestions() {
  const [params] = useSearchParams();
  const applicationId = params.get("applicationId");
  const candidateId = params.get("candidateId");
  const navigate = useNavigate();

  const [candidate, setCandidate] = useState(null);
  const [job, setJob] = useState(null);
  const [categories, setCategories] = useState([]);
  const [questionBank, setQuestionBank] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState("Technical");
  const [selected, setSelected] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveNotice, setSaveNotice] = useState("");
  const [hasApprovedSet, setHasApprovedSet] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);

    const questionsForCandidate = (id) => getInterviewQuestions(id);

    if (applicationId) {
      getReviewBundle(applicationId)
        .then((bundle) =>
          Promise.all([
            bundle,
            questionsForCandidate(bundle.candidate.id),
            listQuestionSets(applicationId),
          ])
        )
        .then(([bundle, questions, sets]) => {
          if (!active) return;
          setCategories(questions.categories || []);
          setQuestionBank(questions.questions || {});
          setCandidate(bundle.candidate);
          setJob(bundle.job);
          setHasApprovedSet(sets.questionSets.some((set) => set.status === "approved"));
          setLoading(false);
        })
        .catch(() => {
          if (!active) return;
          setError(true);
          setLoading(false);
        });
      return () => {
        active = false;
      };
    }

    if (candidateId) {
      Promise.all([
        questionsForCandidate(candidateId),
        getCandidateById(candidateId),
      ])
        .then(([questions, cand]) => {
          if (!active) return;
          setCategories(questions.categories || []);
          setQuestionBank(questions.questions || {});
          setCandidate(cand);
          setLoading(false);
        })
        .catch(() => {
          if (!active) return;
          setError(true);
          setLoading(false);
        });
      return () => {
        active = false;
      };
    }

    questionsForCandidate(null)
      .then((questions) => {
        if (!active) return;
        setCategories(questions.categories || []);
        setQuestionBank(questions.questions || {});
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setError(true);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [applicationId, candidateId]);

  const questionById = useMemo(() => {
    const lookup = {};
    Object.entries(questionBank).forEach(([category, questions]) => {
      (questions || []).forEach((question) => {
        lookup[question.id] = {
          category: CATEGORY_WIRE[category] || "technical",
          text: question.text,
        };
      });
    });
    return lookup;
  }, [questionBank]);

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!applicationId || !selected.size) return;
    setSaving(true);
    setSaveError("");
    setSaveNotice("");
    const questions = [...selected].map((id) => {
      const question = questionById[id];
      return {
        category: question?.category || "technical",
        text: question?.text || "",
        topic: "",
        requirementKey: null,
      };
    });
    try {
      const saved = await saveSelectedQuestions(applicationId, questions);
      setSaveNotice(
        hasApprovedSet
          ? `Saved as a new draft (v${saved.versionNumber}, ${saved.questions.length} questions). The approved set was left untouched — approve the new draft explicitly in the Question Set Builder.`
          : `Saved draft v${saved.versionNumber} (${saved.questions.length} questions). Review and approve it in the Question Set Builder.`
      );
      setHasApprovedSet(
        saved.status === "approved" || hasApprovedSet
      );
    } catch (err) {
      setSaveError(extractError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading interview questions..." />;
  if (error) return <ErrorState message="Unable to load interview questions. Please try again." />;

  const activeQuestions = questionBank[tab] || [];

  return (
    <section>
      {candidate && (
        <button className="back" onClick={() => navigate(`/candidates/${candidate.id}`)}>
          <ArrowLeft size={17} /> Back to {candidate.name}
        </button>
      )}

      <div className="section-head">
        <div>
          <p className="eyebrow">INTERVIEW PREP</p>
          <h2>
            Interview Questions{candidate ? ` — ${candidate.name}` : ""}
            {applicationId && job?.title ? ` · ${job.title}` : ""}
          </h2>
        </div>
        <span className="count">{selected.size} selected</span>
      </div>

      <div className="filter-tabs">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`filter-tab ${tab === cat ? "active" : ""}`}
            onClick={() => setTab(cat)}
          >
            {cat}
            {cat === "Candidate-Specific" && questionBank[cat]?.length > 0 && (
              <span className="tab-count">{questionBank[cat].length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="panel">
        {tab === "Candidate-Specific" && !candidate && (
          <p className="muted-note">
            Open this page from a candidate's profile to generate questions tailored to their
            resume and skill gaps.
          </p>
        )}

        {!activeQuestions.length && candidate ? (
          <p className="muted-note">No candidate-specific questions could be generated.</p>
        ) : (
          <div className="question-list">
            {activeQuestions.map((q) => {
              const isSelected = selected.has(q.id);
              return (
                <label className={`question-item ${isSelected ? "selected" : ""}`} key={q.id}>
                  {isSelected ? (
                    <CheckSquare size={18} className="good-icon" />
                  ) : (
                    <Square size={18} className="muted-note" />
                  )}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggle(q.id)}
                    style={{ display: "none" }}
                  />
                  <span>{q.text}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {!applicationId && (
        <p className="muted-note">
          This is a browse-only preview. Open it from a candidate's profile to pick the job
          application and save your selection as an HR draft.
        </p>
      )}

      <button
        className="primary wide"
        disabled={!selected.size || !applicationId || saving}
        onClick={handleSave}
      >
        {saving ? "Saving..." : `Save Selected Questions (${selected.size})`}
      </button>

      {saveNotice && (
        <div className="form-success">
          {saveNotice}
          <div className="modal-actions" style={{ marginTop: 8 }}>
            <button
              className="primary"
              onClick={() => navigate(`/applications/${applicationId}/questions`)}
            >
              Open Question Set Builder
            </button>
          </div>
        </div>
      )}
      {saveError && <div className="form-error">{saveError}</div>}
    </section>
  );
}