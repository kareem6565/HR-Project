import React from "react";
import { CheckCircle2, Clock3, MinusCircle } from "lucide-react";
import ScoreBadge from "./ScoreBadge";

// Reusable score summary: circle badge + supported/partial/no-evidence requirement chips.
// Used on Matching Results rows and reusable anywhere a compact AI score
// summary is needed. All values are passed in from the backend's AI
// evaluation — this component only renders them. When no requirement
// evidence is supplied (e.g. list views whose aggregation endpoint does not
// carry evidence), it renders an honest empty state instead of fabricated
// chips.
//
// In accordance with HERA evidence semantics:
// - Matched: Evidence supporting requirement -> CheckCircle2 + chip good
// - Partial: Evidence partially supporting requirement -> Clock3 + chip chip-partial
// - Missing: No sufficient evidence found in CV text -> MinusCircle + chip chip-neutral
//   (Never styled in red, and never labeled as candidate lacking the skill)
export default function ScoreCard({
  score,
  group,
  matching = [],
  partial = [],
  missing = [],
  compact = false,
}) {
  const hasBlocks = matching.length > 0 || partial.length > 0 || missing.length > 0;
  return (
    <div className={`score-card ${compact ? "score-card-compact" : ""}`}>
      <ScoreBadge value={score} group={group} size={compact ? 40 : 56} />
      <div className="score-card-skills">
        {!hasBlocks ? (
          <span className="muted-note">No requirement evidence in this view</span>
        ) : (
          <>
            {matching.length > 0 && (
              <div className="score-card-skill-row">
                <CheckCircle2 size={14} className="good-icon" aria-hidden="true" />
                <div className="chips">
                  {matching.slice(0, compact ? 3 : matching.length).map((s) => (
                    <span className="chip good" key={s} dir="auto" title={`Supported requirement: ${s}`}>
                      {s}
                    </span>
                  ))}
                  {compact && matching.length > 3 && <span className="chip">+{matching.length - 3}</span>}
                </div>
              </div>
            )}
            {partial.length > 0 && (
              <div className="score-card-skill-row">
                <Clock3 size={14} className="partial-icon" aria-hidden="true" />
                <div className="chips">
                  {partial.slice(0, compact ? 2 : partial.length).map((s) => (
                    <span
                      className="chip chip-partial"
                      key={s}
                      dir="auto"
                      title={`Partial evidence: ${s}`}
                    >
                      {s}
                    </span>
                  ))}
                  {compact && partial.length > 2 && <span className="chip">+{partial.length - 2}</span>}
                </div>
              </div>
            )}
            {missing.length > 0 && (
              <div className="score-card-skill-row">
                <MinusCircle size={14} className="neutral-icon" aria-hidden="true" />
                <div className="chips">
                  {missing.slice(0, compact ? 2 : missing.length).map((s) => (
                    <span
                      className="chip chip-neutral"
                      key={s}
                      dir="auto"
                      title={`No evidence found in CV text: ${s}`}
                    >
                      {s}
                    </span>
                  ))}
                  {compact && missing.length > 2 && (
                    <span className="chip chip-neutral">+{missing.length - 2}</span>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
