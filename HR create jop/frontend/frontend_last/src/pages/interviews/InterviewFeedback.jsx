import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import { getInterviewById, submitInterviewFeedback } from "../../services/interviewService";

const RATING_FIELDS = [
  { key: "technical", label: "Technical Skills" },
  { key: "communication", label: "Communication" },
  { key: "problemSolving", label: "Problem Solving" },
];

function RatingInput({ label, value, onChange }) {
  return (
    <label>
      {label}
      <div className="rating-row">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className={`rating-dot ${n <= value ? "filled" : ""}`}
            onClick={() => onChange(n)}
            aria-label={`${label}: ${n} out of 5`}
          >
            {n}
          </button>
        ))}
        <span className="rating-value">{value ? `${value}/5` : "Not rated"}</span>
      </div>
    </label>
  );
}

export default function InterviewFeedback() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [interview, setInterview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [ratings, setRatings] = useState({ technical: 0, communication: 0, problemSolving: 0 });
  const [comments, setComments] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    getInterviewById(id)
      .then((data) => {
        setInterview(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const overall = useMemo(() => {
    const { technical, communication, problemSolving } = ratings;
    if (!technical || !communication || !problemSolving) return 0;
    return Math.round(((technical + communication + problemSolving) / 3) * 10) / 10;
  }, [ratings]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setFormError("");
    if (!ratings.technical || !ratings.communication || !ratings.problemSolving) {
      setFormError("Please rate all three categories before submitting.");
      return;
    }
    setSubmitting(true);
    await submitInterviewFeedback(id, {
      ...ratings,
      overall,
      comments,
    });
    setSubmitting(false);
    setSubmitted(true);
  };

  if (loading) return <LoadingSpinner label="Loading interview..." />;
  if (error) return <ErrorState message="Unable to load this interview. Please try again." onRetry={load} />;
  if (!interview) {
    return (
      <section>
        <button className="back" onClick={() => navigate("/interviews")}>
          <ArrowLeft size={17} /> Back to Interviews
        </button>
        <div className="empty">Interview not found.</div>
      </section>
    );
  }

  const existingFeedback = interview.feedback;
  const showReadOnly = existingFeedback && !submitted;

  return (
    <section>
      <button className="back" onClick={() => navigate("/interviews")}>
        <ArrowLeft size={17} /> Back to Interviews
      </button>

      <div className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">INTERVIEW FEEDBACK</p>
            <h3>
              {interview.candidateName} — {interview.job}
            </h3>
          </div>
        </div>
        <p className="muted-note">
          {interview.date} at {interview.time} · Interviewer: {interview.interviewer}
        </p>

        {submitted ? (
          <div className="success-message" style={{ marginTop: 16 }}>
            <CheckCircle2 size={16} style={{ marginRight: 6, verticalAlign: "-3px" }} />
            Feedback submitted. This interview is now marked as Completed.
          </div>
        ) : showReadOnly ? (
          <div className="feedback-readonly">
            {RATING_FIELDS.map((f) => (
              <div className="feedback-readonly-row" key={f.key}>
                <span>{f.label}</span>
                <strong>{existingFeedback[f.key]}/5</strong>
              </div>
            ))}
            <div className="feedback-readonly-row">
              <span>Overall Rating</span>
              <strong>{existingFeedback.overall}/5</strong>
            </div>
            <h4>Comments</h4>
            <p className="ai-explanation">{existingFeedback.comments || "No comments left."}</p>
          </div>
        ) : (
          <form onSubmit={onSubmit} style={{ marginTop: 20 }}>
            {RATING_FIELDS.map((f) => (
              <RatingInput
                key={f.key}
                label={f.label}
                value={ratings[f.key]}
                onChange={(n) => setRatings({ ...ratings, [f.key]: n })}
              />
            ))}

            <div className="overall-score-row" style={{ marginTop: 10 }}>
              <span>Overall Rating</span>
              <strong>{overall ? `${overall}/5` : "—"}</strong>
            </div>

            <label>
              Comments
              <textarea
                rows="4"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="e.g. Strong backend fundamentals."
              />
            </label>

            {formError && <div className="form-error">{formError}</div>}

            <button className="primary wide" type="submit" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Feedback"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}