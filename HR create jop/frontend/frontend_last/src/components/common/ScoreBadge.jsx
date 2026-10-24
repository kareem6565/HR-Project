import React from "react";
import { formatScore, parseScore } from "../../utils/score";

// Authoritative grouping bands from backend (Phase 4.5 candidate_pool_service.py):
// >=70: must_review -> "green" ("Must Review")
// >=40: consider    -> "amber" ("Consider")
// <40 or unscored: lower_priority -> "grey" ("Lower Priority")
//
// Never use arbitrary frontend traffic-light thresholds (such as 85/70) that
// contradict backend groups.
// Semantic color rules:
// - Green: Must Review / High confidence
// - Amber: Consider / Moderate confidence
// - Grey: Lower Priority / No score / No evidence found (NOT RED)
// - Red is strictly reserved for human Reject decisions or application errors.

export const BAND_CONFIG = {
  must_review: {
    tone: "green",
    label: "Must Review",
  },
  consider: {
    tone: "amber",
    label: "Consider",
  },
  lower_priority: {
    tone: "grey",
    label: "Lower Priority",
  },
};

export function groupForScore(score) {
  const num = parseScore(score);
  if (num === null) return "lower_priority";
  if (num >= 70) return "must_review";
  if (num >= 40) return "consider";
  return "lower_priority";
}

export function toneForScore(score, group) {
  const g = group || groupForScore(score);
  return BAND_CONFIG[g]?.tone || "grey";
}

export function labelForScore(score, group) {
  const g = group || groupForScore(score);
  return BAND_CONFIG[g]?.label || "Lower Priority";
}

export default function ScoreBadge({ value, group, size = 40, showLabel = false }) {
  const displayValue = formatScore(value, { suffix: "" });
  const effectiveGroup = parseScore(value) === null ? "lower_priority" : group || groupForScore(value);
  const tone = BAND_CONFIG[effectiveGroup]?.tone || "grey";
  const label = BAND_CONFIG[effectiveGroup]?.label || "Lower Priority";

  const badgeNode = (
    <div
      className={`score-badge score-badge-${tone}`}
      style={{ width: size, height: size, fontSize: size * 0.34 }}
      aria-label={`Score: ${displayValue}, Band: ${label}`}
      title={`Score: ${displayValue} (${label})`}
    >
      {displayValue}
    </div>
  );

  if (!showLabel) return badgeNode;

  return (
    <div className="score-with-band" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      {badgeNode}
      <span className={`recommendation recommendation-${tone}`}>{label}</span>
    </div>
  );
}
