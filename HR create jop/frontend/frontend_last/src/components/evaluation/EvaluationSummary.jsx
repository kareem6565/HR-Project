import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import ScoreBadge, { BAND_CONFIG, groupForScore } from "../common/ScoreBadge";
import { formatScore, parseScore } from "../../utils/score";

function normalizeStatus(status) {
  return String(status || "")
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

function formatReadablePoint(point) {
  if (typeof point === "string") return point;
  if (!point || typeof point !== "object") return String(point || "");
  const text =
    point.text ||
    point.point ||
    point.summary ||
    point.title ||
    point.description ||
    point.label;
  if (text && typeof text === "string") return text;
  // If object of key-values, join values cleanly without raw JSON braces
  const readable = Object.values(point)
    .filter((v) => typeof v === "string" || typeof v === "number")
    .join(" — ");
  return readable || "Evaluation note";
}

const EVALUATION_STATUS_TONE = {
  completed: "good",
  running: "chip-amber",
  queued: "chip-neutral",
  failed: "bad",
  superseded: "chip-neutral",
};

/**
 * EvaluationSummary — Compact hero card presenting the authoritative score,
 * grouping band, evaluation versioning, and explainable summary points.
 */
export default function EvaluationSummary({
  evaluation,
  group,
  onReevaluate,
  evaluating = false,
  className = "",
}) {
  if (!evaluation) {
    return null;
  }

  const numScore = parseScore(evaluation.score);
  const hasNumericScore = numScore !== null;

  const effectiveGroup = group || (hasNumericScore ? groupForScore(numScore) : "lower_priority");
  const band = BAND_CONFIG[effectiveGroup] || BAND_CONFIG.lower_priority;
  const statusTone = EVALUATION_STATUS_TONE[evaluation.status] || "chip-neutral";

  const explanation = evaluation.explanation;
  const points = Array.isArray(explanation?.points) ? explanation.points : [];

  return (
    <div className={`panel evaluation-summary-card ${className}`.trim()}>
      {/* 1. Versioning & Status Metadata Strip */}
      <div className="evaluation-meta-strip">
        <span className={`chip ${statusTone}`}>
          {normalizeStatus(evaluation.status)}
        </span>
        {evaluation.version_number && (
          <span className="chip">Version {evaluation.version_number}</span>
        )}
        {evaluation.scoring_version && (
          <span className="chip">Scoring {evaluation.scoring_version}</span>
        )}
        {evaluation.created_at && (
          <span className="chip">Run {formatTimestamp(evaluation.created_at)}</span>
        )}

        {onReevaluate && (
          <button
            type="button"
            className="btn btn-secondary reevaluate-btn"
            onClick={onReevaluate}
            disabled={evaluating}
            aria-label="Re-run evaluation for this application"
          >
            {evaluating ? (
              <RefreshCw size={13} className="spin" aria-hidden="true" />
            ) : (
              <RefreshCw size={13} aria-hidden="true" />
            )}
            <span>{evaluating ? "Evaluating…" : "Re-evaluate"}</span>
          </button>
        )}
      </div>

      {/* 2. Non-completed Status Alert */}
      {evaluation.status && evaluation.status !== "completed" && (
        <div className="form-error" role="alert">
          <AlertCircle size={14} aria-hidden="true" />
          <span>
            This evaluation did not complete normally (status: {normalizeStatus(evaluation.status)}).
          </span>
        </div>
      )}

      {/* 3. Authoritative Score Hero */}
      <div className="score-hero">
        {hasNumericScore ? (
          <>
            <ScoreBadge value={numScore} group={effectiveGroup} size={56} />
            <div>
              <strong className="score-hero-value">
                {formatScore(numScore)} Match Score{" "}
                <span className="muted-note">({band.label})</span>
              </strong>
              <span className="score-hero-desc">
                Authoritative overall match score computed from requirement evidence.
              </span>
            </div>
          </>
        ) : (
          <div className="score-hero-unscored">
            <span className="score-dash" aria-hidden="true">—</span>
            <div>
              <strong className="score-hero-value">No Score Recorded</strong>
              <span className="score-hero-desc">
                The backend recorded this evaluation without a numerical score.
              </span>
            </div>
          </div>
        )}
      </div>

      {hasNumericScore && (
        <div
          className="score-track"
          role="progressbar"
          aria-valuenow={numScore}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Candidate match score progress"
        >
          <i style={{ width: `${Math.min(100, Math.max(0, numScore))}%` }} />
        </div>
      )}

      {/* 4. Explainable AI Summary ("Why this score?") */}
      <div className="evaluation-explanation">
        <h4 className="evaluation-section-title">Why this score?</h4>
        {explanation ? (
          <>
            {typeof explanation.summary === "string" && explanation.summary && (
              <p className="ai-explanation" style={{ marginBottom: points.length ? 10 : 0 }}>
                {explanation.summary}
              </p>
            )}
            {points.length > 0 && (
              <ul className="strengths-list">
                {points.map((point, i) => {
                  const pointText = formatReadablePoint(point);
                  return pointText ? <li key={i}>{pointText}</li> : null;
                })}
              </ul>
            )}
          </>
        ) : (
          <p className="muted-note">
            The evaluation did not include an explanation for this score.
          </p>
        )}
      </div>
    </div>
  );
}
