// Score values are 0–100 match scores from the backend. Keep parsing strict so
// malformed or out-of-range historical values are shown as unavailable.
const NUMERIC_SCORE = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

export function parseScore(value) {
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && !NUMERIC_SCORE.test(value.trim())) return null;
  if (typeof value === "string" && !value.trim()) return null;
  const score = Number(value);
  return Number.isFinite(score) && score >= 0 && score <= 100 ? score : null;
}

export function formatScore(value, { suffix = "%", maximumFractionDigits = 1 } = {}) {
  const score = parseScore(value);
  if (score === null) return "—";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(score)}${suffix}`;
}
