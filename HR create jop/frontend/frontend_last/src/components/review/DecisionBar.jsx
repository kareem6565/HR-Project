import React from "react";
import { CheckCircle2, Clock3, XCircle, ShieldCheck, User, Info } from "lucide-react";
import PipelineActions from "../common/PipelineActions";
import { HRDecisionValue } from "../../types/api";

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

/**
 * DecisionBar — Dedicated decision panel and action bar for human recruitment decisions.
 * Displays the current recorded status, labelled actions for Advance, Hold, Reject,
 * and clear server audit trail disclosures.
 */
export default function DecisionBar({
  currentDecision,
  decisionCreatedAt,
  onSelectDecision,
  disabled = false,
  showActions = true,
  className = "",
}) {
  const DecisionIcon = currentDecision ? DECISION_ICON[currentDecision] || Clock3 : null;

  return (
    <div
      id="hr-decision"
      className={`panel review-block review-decision ${className}`.trim()}
      role="region"
      aria-label="HR Hiring Decision"
      tabIndex={-1}
    >
      {/* Title & Human Flag */}
      <div className="review-block-title">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ShieldCheck size={18} aria-hidden="true" />
          <h3 style={{ margin: 0 }}>Human Hiring Decision</h3>
        </div>
        <span className="flag flag-human">
          <User size={12} aria-hidden="true" /> Human Controlled
        </span>
      </div>

      <p className="muted-note" style={{ marginBottom: 14 }}>
        The AI evaluation provides automated screening insights. Final recruitment decisions are made strictly by human HR professionals.
      </p>

      {/* Current Status Bar */}
      <div className="decision-status-container" style={{ marginBottom: 16 }}>
        {currentDecision ? (
          <div className="decision-current-state">
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
              <span className="muted-note" style={{ fontSize: 13, fontWeight: 500 }}>
                Current Decision:
              </span>
              <span
                className={`badge badge-${DECISION_TONE[currentDecision] || "grey"}`}
                data-testid="current-decision-badge"
              >
                {DecisionIcon && <DecisionIcon size={13} aria-hidden="true" />}
                <span>{DECISION_LABELS[currentDecision] || normalizeStatus(currentDecision)}</span>
              </span>
              {decisionCreatedAt && (
                <span className="muted-note" style={{ fontSize: 12 }}>
                  (Recorded on {formatTimestamp(decisionCreatedAt)})
                </span>
              )}
            </div>
            <p className="muted-note" style={{ fontSize: 12, margin: 0 }}>
              {showActions
                ? "An HR decision is currently recorded. Selecting an action below will record a new append-only entry."
                : "An HR decision is currently recorded. Selecting an action in the review summary will record a new append-only entry."}
            </p>
          </div>
        ) : (
          <div className="decision-current-state">
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
              <span className="muted-note" style={{ fontSize: 13, fontWeight: 500 }}>
                Current Decision:
              </span>
              <span className="badge badge-grey" data-testid="current-decision-badge">
                No Decision Recorded
              </span>
            </div>
            <p className="muted-note" style={{ fontSize: 12, margin: 0 }}>
              {showActions
                ? "No HR decision recorded yet. Review the available evidence, then select an action to record your decision."
                : "No HR decision recorded yet. Decision actions are available in the review summary above."}
            </p>
          </div>
        )}
      </div>

      {/* Decision Buttons with Visible Labels */}
      {showActions && (
        <div className="decision-actions-row" style={{ marginBottom: 16 }}>
          <PipelineActions
            currentStatus={currentDecision}
            onDecision={onSelectDecision}
            disabled={disabled}
          />
        </div>
      )}

      {/* Immutable Server Audit Trail Note */}
      <div
        className="flow-note"
        style={{
          padding: 10,
          borderRadius: 6,
          background: "var(--bg-muted, #f8fafc)",
          fontSize: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <Info
            size={15}
            style={{ flexShrink: 0, marginTop: 1, color: "var(--hera-teal, #1b3a3a)" }}
            aria-hidden="true"
          />
          <div className="muted-note" style={{ margin: 0, lineHeight: 1.4 }}>
            <strong>Decision Integrity:</strong> Every decision is recorded immutably in the database audit log with user and evaluation version metadata. Full multi-event historical decision logs require an administrative audit endpoint.
          </div>
        </div>
      </div>
    </div>
  );
}
