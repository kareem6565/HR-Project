import React, { useState, useMemo } from "react";
import { AlertCircle, ChevronDown, ChevronRight, CheckCircle2, HelpCircle } from "lucide-react";
import EmptyState from "../common/EmptyState";

function normalizeStatus(status) {
  return String(status || "")
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Checks if a string is a technical hash or internal ID like "req-0000000000000001",
 * "req-1234567890", a UUID, or purely hexadecimal characters.
 */
function isTechnicalHash(val) {
  if (!val || typeof val !== "string") return false;
  const trimmed = val.trim();
  if (/^req[-_]?[0-9a-fA-F-]{4,}$/i.test(trimmed)) return true;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed)) return true;
  if (/^[0-9a-f]{16,}$/i.test(trimmed)) return true;
  return false;
}

/**
 * Resolves a human-readable requirement name without exposing internal hashes or keys.
 */
function resolveRequirementName(reqRef, breakdownItem, fallbackIndex) {
  // 1. Direct textual fields from requirement_ref
  const candidates = [
    reqRef?.text,
    reqRef?.skill,
    reqRef?.requirement,
    reqRef?.title,
    reqRef?.name,
    breakdownItem?.text,
    breakdownItem?.label,
    breakdownItem?.skill,
    breakdownItem?.requirement,
  ];

  for (const c of candidates) {
    if (c && typeof c === "string" && !isTechnicalHash(c)) {
      return c.trim();
    }
  }

  // 2. Check if requirement_key has a human readable format (e.g. "must_have:Python" or "skills:Docker")
  const rawKey = reqRef?.requirement_key || breakdownItem?.requirement_key;
  if (rawKey && typeof rawKey === "string" && !isTechnicalHash(rawKey)) {
    if (rawKey.includes(":")) {
      const parts = rawKey.split(":");
      const part = parts[parts.length - 1].trim();
      if (part && !isTechnicalHash(part)) {
        return part.replace(/_/g, " ");
      }
    }
    // Clean underscores/dashes for human display
    const cleaned = rawKey.replace(/[_-]/g, " ").trim();
    if (cleaned && !isTechnicalHash(cleaned)) {
      return cleaned;
    }
  }

  // 3. Fallback: Human-friendly numbered label rather than internal technical hash
  return `Requirement #${fallbackIndex}`;
}

/**
 * Extracts and normalizes requirement category.
 */
function resolveCategory(reqRef, breakdownItem) {
  const raw = breakdownItem?.category || reqRef?.category || reqRef?.section;
  if (!raw) return "General";
  const s = String(raw).toLowerCase().replace(/[-_\s]+/g, "");
  if (s === "musthave") return "Must-Have";
  if (s === "important") return "Important";
  if (s === "nicetohave") return "Nice-to-Have";
  return normalizeStatus(raw);
}

/**
 * Normalizes candidate evidence into clean display properties without JSON.stringify.
 */
function resolveCandidateEvidence(candidateEvidence, breakdownItem) {
  if (!candidateEvidence && breakdownItem?.evidence_value) {
    if (typeof breakdownItem.evidence_value === "string") {
      return {
        mainText: breakdownItem.evidence_value,
        quote: null,
        terms: [],
        explanation: null,
        uncertainty: null,
        verificationStatus: null,
        sourceSection: null,
      };
    }
  }

  if (!candidateEvidence) {
    return {
      mainText: null,
      quote: null,
      terms: [],
      explanation: null,
      uncertainty: null,
      verificationStatus: null,
      sourceSection: null,
    };
  }

  if (typeof candidateEvidence === "string") {
    return {
      mainText: candidateEvidence,
      quote: candidateEvidence,
      terms: [],
      explanation: null,
      uncertainty: null,
      verificationStatus: null,
      sourceSection: null,
    };
  }

  if (Array.isArray(candidateEvidence)) {
    const terms = candidateEvidence.filter((t) => typeof t === "string");
    return {
      mainText: terms.join(" · "),
      quote: null,
      terms,
      explanation: null,
      uncertainty: null,
      verificationStatus: null,
      sourceSection: null,
    };
  }

  if (typeof candidateEvidence === "object") {
    const quote =
      candidateEvidence.quote ||
      candidateEvidence.evidence_text ||
      candidateEvidence.text ||
      null;
    const explanation = candidateEvidence.explanation || null;
    const terms = Array.isArray(candidateEvidence.matched_terms)
      ? candidateEvidence.matched_terms.filter((t) => typeof t === "string")
      : [];
    const uncertainty = candidateEvidence.uncertainty || null;
    const verificationStatus = candidateEvidence.verification_status || null;
    const sourceSection =
      candidateEvidence.source_section ||
      candidateEvidence.source ||
      candidateEvidence.resume_section ||
      null;

    let mainText = quote || explanation;
    if (!mainText && terms.length > 0) {
      mainText = `Matched terms: ${terms.join(", ")}`;
    }
    if (!mainText) {
      // Format simple key-value pairs cleanly without raw JSON
      const pairs = Object.entries(candidateEvidence)
        .filter(
          ([k, v]) =>
            v !== null &&
            v !== undefined &&
            v !== "" &&
            typeof v !== "object" &&
            !["verification_status", "uncertainty"].includes(k)
        )
        .map(([k, v]) => `${normalizeStatus(k)}: ${v}`);
      mainText = pairs.join(" · ") || null;
    }

    return {
      mainText,
      quote,
      terms,
      explanation,
      uncertainty,
      verificationStatus,
      sourceSection,
    };
  }

  return {
    mainText: String(candidateEvidence),
    quote: null,
    terms: [],
    explanation: null,
    uncertainty: null,
    verificationStatus: null,
    sourceSection: null,
  };
}

/**
 * Formats contribution and strength information if present in the response.
 */
function resolveContribution(item, breakdownItem) {
  const contrib = breakdownItem?.contribution;
  const strength = item?.strength;

  let contribStr = null;
  if (contrib !== undefined && contrib !== null && contrib !== "") {
    contribStr =
      typeof contrib === "number"
        ? `${contrib > 0 ? "+" : ""}${contrib}%`
        : String(contrib);
  }

  if (contribStr && strength) {
    return `${normalizeStatus(strength)} (${contribStr})`;
  }
  if (contribStr) {
    return contribStr;
  }
  if (strength) {
    return normalizeStatus(strength);
  }
  return "—";
}

export default function EvidenceTable({
  evidence = [],
  breakdown = null,
  className = "",
}) {
  const [expandedRows, setExpandedRows] = useState({});

  const toggleRow = (rowId) => {
    setExpandedRows((prev) => ({
      ...prev,
      [rowId]: !prev[rowId],
    }));
  };

  // Build unified rows by merging evidence items and score_breakdown
  const { rows, summaryCounts, signalsCount } = useMemo(() => {
    const rawEvidence = Array.isArray(evidence) ? evidence : [];
    const breakdownMap =
      breakdown && typeof breakdown === "object"
        ? Array.isArray(breakdown)
          ? breakdown.reduce((acc, item) => {
              if (item?.requirement_key) acc[item.requirement_key] = item;
              return acc;
            }, {})
          : breakdown
        : {};

    const unified = [];
    const processedKeys = new Set();
    let index = 1;

    // 1. Process items from evidence array
    for (const item of rawEvidence) {
      const key = item?.requirement_ref?.requirement_key || item?.id || `evidence-${index}`;
      processedKeys.add(key);

      const bdItem = breakdownMap[key] || null;
      const name = resolveRequirementName(item?.requirement_ref, bdItem, index);
      const category = resolveCategory(item?.requirement_ref, bdItem);
      const evidenceType = item?.evidence_type || bdItem?.evidence_type || "missing";
      const candidateData = resolveCandidateEvidence(item?.candidate_evidence, bdItem);
      const contribution = resolveContribution(item, bdItem);

      // Determine inline review signals
      const signals = [];
      if (evidenceType === "missing" && category === "Must-Have") {
        signals.push("No evidence found for must-have requirement");
      } else if (candidateData.verificationStatus === "fabricated_quote") {
        signals.push("Quote not found in candidate CV text");
      } else if (candidateData.verificationStatus === "unverified_quote") {
        signals.push("Unverified quote");
      }

      const hasDetails = Boolean(
        candidateData.sourceSection ||
          candidateData.uncertainty ||
          candidateData.verificationStatus ||
          (candidateData.quote && candidateData.explanation) ||
          (candidateData.terms && candidateData.terms.length > 0)
      );

      unified.push({
        id: item?.id || key || `row-${index}`,
        name,
        category,
        evidenceType,
        candidateData,
        contribution,
        signals,
        hasDetails,
      });

      index += 1;
    }

    // 2. Process any remaining requirements from breakdown that were not in evidence
    for (const [key, bdItem] of Object.entries(breakdownMap)) {
      if (processedKeys.has(key)) continue;

      const name = resolveRequirementName(null, bdItem, index);
      const category = resolveCategory(null, bdItem);
      const evidenceType = bdItem?.evidence_type || "missing";
      const candidateData = resolveCandidateEvidence(null, bdItem);
      const contribution = resolveContribution(null, bdItem);

      const signals = [];
      if (evidenceType === "missing" && category === "Must-Have") {
        signals.push("No evidence found for must-have requirement");
      }

      unified.push({
        id: bdItem?.requirement_key || key || `row-${index}`,
        name,
        category,
        evidenceType,
        candidateData,
        contribution,
        signals,
        hasDetails: false,
      });

      index += 1;
    }

    // Summary counts
    const counts = { matched: 0, partial: 0, missing: 0 };
    let sigCount = 0;
    for (const r of unified) {
      if (counts[r.evidenceType] !== undefined) {
        counts[r.evidenceType] += 1;
      }
      sigCount += r.signals.length;
    }

    return {
      rows: unified,
      summaryCounts: counts,
      signalsCount: sigCount,
    };
  }, [evidence, breakdown]);

  if (!rows.length) {
    return (
      <EmptyState message="No requirement evidence was attached to this evaluation." />
    );
  }

  return (
    <div className={`evidence-table-container ${className}`.trim()}>
      {/* 1. Summary Chips Bar */}
      <div className="evidence-summary-bar">
        {summaryCounts.matched > 0 && (
          <span className="chip good">
            {summaryCounts.matched} supported
          </span>
        )}
        {summaryCounts.partial > 0 && (
          <span className="chip chip-partial">
            {summaryCounts.partial} partial
          </span>
        )}
        {summaryCounts.missing > 0 && (
          <span className="chip chip-neutral">
            {summaryCounts.missing} no evidence found
          </span>
        )}
        {signalsCount > 0 && (
          <span className="chip chip-partial" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <AlertCircle size={13} aria-hidden="true" />
            <span>
              {signalsCount} review signal{signalsCount > 1 ? "s" : ""}
            </span>
          </span>
        )}
      </div>

      {/* 2. Unified Primary Requirements / Evidence Table */}
      <div className="panel table-panel" style={{ padding: 0, overflow: "hidden" }}>
        <div className="table-wrap">
          <table className="evidence-table" aria-label="Candidate Requirement Match Evidence">
            <thead>
              <tr>
                <th scope="col" style={{ width: "26%" }}>Requirement</th>
                <th scope="col" style={{ width: "16%" }}>Status</th>
                <th scope="col" style={{ width: "36%" }}>Candidate Evidence</th>
                <th scope="col" style={{ width: "12%" }}>Contribution</th>
                <th scope="col" style={{ width: "10%" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isExpanded = Boolean(expandedRows[row.id]);
                const { candidateData } = row;

                return (
                  <React.Fragment key={row.id}>
                    <tr className={isExpanded ? "evidence-row-expanded" : ""}>
                      {/* Requirement Column */}
                      <td className="evidence-req-cell">
                        <span className="evidence-req-name" dir="auto">{row.name}</span>
                        <span className="evidence-req-category">{row.category}</span>
                        {row.signals.length > 0 && (
                          <div style={{ marginTop: 6 }}>
                            {row.signals.map((sig, i) => (
                              <span key={i} className="evidence-signal-badge">
                                <AlertCircle size={11} aria-hidden="true" />
                                <span>{sig}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Status Column */}
                      <td>
                        {row.evidenceType === "matched" && (
                          <span className="chip good">Supported</span>
                        )}
                        {row.evidenceType === "partial" && (
                          <span className="chip chip-partial">Partial</span>
                        )}
                        {row.evidenceType === "missing" && (
                          <span className="chip chip-neutral">No evidence found</span>
                        )}
                      </td>

                      {/* Candidate Evidence Column */}
                      <td>
                        {candidateData.quote ? (
                          <blockquote className="evidence-quote-box" dir="auto">
                            "{candidateData.quote}"
                          </blockquote>
                        ) : candidateData.mainText ? (
                          <div className="evidence-text-content" dir="auto">
                            {candidateData.mainText}
                          </div>
                        ) : (
                          <span className="muted-note">No evidence found in CV text</span>
                        )}

                        {candidateData.terms && candidateData.terms.length > 0 && (
                          <div style={{ marginTop: 4 }}>
                            {candidateData.terms.map((term, i) => (
                              <span key={i} className="evidence-term-chip">
                                {term}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Contribution Column */}
                      <td className="muted-note">{row.contribution}</td>

                      {/* Details Toggle Column */}
                      <td>
                        {row.hasDetails ? (
                          <button
                            type="button"
                            className="evidence-expand-btn"
                            onClick={() => toggleRow(row.id)}
                            aria-expanded={isExpanded}
                            aria-label={`${isExpanded ? "Hide" : "Show"} details for ${row.name}`}
                          >
                            {isExpanded ? (
                              <>
                                <ChevronDown size={14} aria-hidden="true" />
                                <span>Hide</span>
                              </>
                            ) : (
                              <>
                                <ChevronRight size={14} aria-hidden="true" />
                                <span>Details</span>
                              </>
                            )}
                          </button>
                        ) : (
                          <span className="muted-note">—</span>
                        )}
                      </td>
                    </tr>

                    {/* Expandable Supporting Context Details */}
                    {isExpanded && row.hasDetails && (
                      <tr className="evidence-details-row">
                        <td colSpan={5} style={{ background: "#fcfdfd", padding: "10px 18px 14px" }}>
                          <div className="evidence-details-drawer">
                            {candidateData.sourceSection && (
                              <div>
                                <strong>Resume Section:</strong>{" "}
                                <span>{normalizeStatus(candidateData.sourceSection)}</span>
                              </div>
                            )}

                            {candidateData.verificationStatus && (
                              <div>
                                <strong>Verification Status:</strong>{" "}
                                <span>{normalizeStatus(candidateData.verificationStatus)}</span>
                              </div>
                            )}

                            {candidateData.uncertainty && (
                              <div>
                                <strong>Uncertainty Note:</strong>{" "}
                                <span dir="auto">{candidateData.uncertainty}</span>
                              </div>
                            )}

                            {candidateData.explanation && candidateData.quote && (
                              <div>
                                <strong>Matching Analysis:</strong>{" "}
                                <span dir="auto">{candidateData.explanation}</span>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
