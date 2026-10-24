import React from "react";
import { Info } from "lucide-react";

/**
 * LimitationsNote — Stable limitation disclosure component for HERA evaluations.
 *
 * Reminds reviewers that AI scoring is based solely on extracted text from the CV,
 * and that lack of evidence in the CV does not prove lack of candidate capability.
 */
export default function LimitationsNote({ className = "", style = {} }) {
  return (
    <div
      role="note"
      aria-label="Evaluation limitations disclosure"
      className={`limitations-note ${className}`.trim()}
      style={style}
    >
      <Info size={16} className="limitations-note-icon" aria-hidden="true" />
      <div className="limitations-note-content">
        <strong className="limitations-note-title">Evaluation Note:</strong>{" "}
        <span>
          The evaluation reflects the text extracted from the CV and absence of evidence does not prove absence of the skill.
        </span>
      </div>
    </div>
  );
}
