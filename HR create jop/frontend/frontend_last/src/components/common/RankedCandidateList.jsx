import React from "react";
import DataTable from "./DataTable";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import LoadingSpinner from "./LoadingSpinner";
import ScoreBadge from "./ScoreBadge";
import { formatScore, parseScore } from "../../utils/score";

// UI-only presentation scaffold for ranked-candidate lists (Evaluations,
// Talent Pool, … and — with a configuration/adapter — anything similar).
//
// Renders the data-pipeline states (loading / error / empty) plus a
// configurable candidate table through the shared DataTable. It owns NO
// business rules: the owning page/service keeps fetching, transforming,
// filtering, sorting, scoring and submitting decisions. Scores, groups,
// statuses and decisions are displayed exactly as received.
//
// Props:
//   loading / error / onRetry / loadingLabel / errorMessage — pipeline states
//   rows / columns / onRowClick / rowKeys — DataTable contract (columns as
//     [{ key, header, render? }], rows are already-adapted presentation rows)
//   emptyMessage — shown via EmptyState when rows is empty
//   toolbar — React node of parent-owned filter/search controls, rendered in
//     the standard .toolbar bar; values and handlers stay in the parent
//   header — optional node rendered inside the panel above the table (e.g. a
//     panel-title row for pages that keep their search inside the panel)
export default function RankedCandidateList({
  loading = false,
  error = false,
  onRetry,
  loadingLabel = "Loading...",
  errorMessage = "Unable to load the list. Please try again.",
  emptyMessage = "No candidates to show.",
  toolbar,
  header,
  columns,
  rows = [],
  onRowClick,
}) {
  if (loading) return <LoadingSpinner label={loadingLabel} />;
  if (error) return <ErrorState message={errorMessage} onRetry={onRetry} />;

  return (
    <>
      {toolbar && <div className="toolbar">{toolbar}</div>}
      {rows.length === 0 ? (
        header ? (
          <div className="panel table-panel">
            {header}
            <EmptyState message={emptyMessage} />
          </div>
        ) : (
          <EmptyState message={emptyMessage} />
        )
      ) : (
        <DataTable header={header} columns={columns} data={rows} onRowClick={onRowClick} />
      )}
    </>
  );
}

// Candidate identity cell: initials avatar + name + optional subtitle line.
function initialsOf(name) {
  return (name || "")
    .split(" ")
    .map((x) => x[0])
    .join("")
    .slice(0, 2);
}

export function CandidateCell({ name, subtitle }) {
  return (
    <div className="candidate-cell">
      <div className="mini-avatar">{initialsOf(name)}</div>
      <div>
        <strong dir="auto">{name}</strong>
        {subtitle && <div dir="auto">{subtitle}</div>}
      </div>
    </div>
  );
}

// Score display cell. The value is always backend-provided; this never
// computes, rounds, or piles thresholds on top — it only picks the display
// style ("badge" = circular ScoreBadge, "text" = plain score number).
export function ScoreCell({ score, group, variant = "badge" }) {
  if (parseScore(score) === null) {
    return <span className="muted-note">Not scored</span>;
  }
  if (variant === "text") {
    return <strong className="score-text">{formatScore(score, { suffix: "" })}</strong>;
  }
  return <ScoreBadge value={score} group={group} />;
}

// Backend-authoritative group pill. The tone/label maps are display-only and
// may be overridden per page; groups are never calculated here.
const GROUP_TONES = {
  must_review: "green",
  consider: "amber",
  lower_priority: "grey",
};

const GROUP_LABELS = {
  must_review: "Must Review",
  consider: "Consider",
  lower_priority: "Lower Priority",
};

export function GroupPill({ group, tones = GROUP_TONES, labels = GROUP_LABELS }) {
  return (
    <span className={`recommendation recommendation-${tones[group] || "grey"}`}>
      {labels[group] || group || "—"}
    </span>
  );
}

// Extracted-profile skills chips cell.
export function SkillsPreview({ skills = [], max = 3 }) {
  return (
    <div className="skill-preview">
      {skills.length ? (
        skills.slice(0, max).map((s) => <span key={s}>{s}</span>)
      ) : (
        <span className="muted-note">No profile yet</span>
      )}
      {skills.length > max && <span>+{skills.length - max}</span>}
    </div>
  );
}
