import React from "react";
import { CheckCircle2, Clock3, XCircle } from "lucide-react";

// UI-only shared pipeline-decision buttons (Advance / Hold / Reject) (UI-01 accessible).
//
// Renders the actions and calls `onDecision(decision)` with the decision
// vocabulary ("advance" | "hold" | "reject"). It performs no API calls and
// holds no business logic: the owning page/service is responsible for
// submitting the decision. `currentStatus` opts a button into the "active"
// visual state (decision vocabulary, e.g. "advance").
const ACTIONS = [
  { decision: "advance", label: "Advance", icon: CheckCircle2, className: "btn-shortlist" },
  { decision: "hold", label: "Hold", icon: Clock3, className: "btn-hold" },
  { decision: "reject", label: "Reject", icon: XCircle, className: "btn-reject" },
];

export default function PipelineActions({ currentStatus, onDecision, size = "normal", disabled }) {
  const small = size === "small";
  return (
    <div className="pipeline-actions" role="group" aria-label="Pipeline decisions">
      {ACTIONS.map(({ decision, label, icon: Icon, className }) => (
        <button
          key={decision}
          type="button"
          className={`btn ${className} ${small ? "btn-small" : ""} ${currentStatus === decision ? "active" : ""}`}
          onClick={() => onDecision(decision)}
          disabled={disabled}
          title={label}
          aria-label={label}
          aria-pressed={currentStatus === decision}
        >
          <Icon size={small ? 13 : 15} aria-hidden="true" /> {!small && label}
        </button>
      ))}
    </div>
  );
}