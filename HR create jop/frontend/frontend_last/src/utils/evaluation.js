// Presentation-only mapping from an AI score to a recommendation label.
// The score itself always comes from the backend's AI evaluation — this
// just decides how to phrase/color it consistently across pages.
export function getRecommendation(score) {
  if (score >= 85) return { label: "Recommend Interview", tone: "green" };
  if (score >= 70) return { label: "Consider for Interview", tone: "amber" };
  return { label: "Not Recommended", tone: "red" };
}
