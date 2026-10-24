// Authoritative route-to-title map for HERA (UI-03).
// Every registered route in App.jsx maps to an accurate, descriptive page title.

export const ROUTE_TITLE_RULES = [
  // Specific sub-routes first
  { pattern: /^\/jobs\/new$/, title: "Create Job" },
  { pattern: /^\/jobs\/[^/]+\/edit$/, title: "Edit Job" },
  { pattern: /^\/jobs\/[^/]+$/, title: "Job Details" },
  { pattern: /^\/jobs$/, title: "Jobs" },

  { pattern: /^\/candidates\/screen$/, title: "Screen Candidates" },
  { pattern: /^\/candidates\/[^/]+$/, title: "Candidate Details" },
  { pattern: /^\/candidates$/, title: "Candidates" },

  // Legacy route redirects to the application-level review queue.
  { pattern: /^\/evaluations$/, title: "Applications" },

  { pattern: /^\/applications\/[^/]+\/review$/, title: "Application Review" },
  { pattern: /^\/applications\/[^/]+\/questions$/, title: "Question Set Builder" },
  { pattern: /^\/applications$/, title: "Applications" },

  { pattern: /^\/talent-pool$/, title: "Talent Pool" },
  { pattern: /^\/matching-results$/, title: "Matching Results" },
  { pattern: /^\/analytics$/, title: "Analytics" },
  { pattern: /^\/settings$/, title: "AI Settings" },

  { pattern: /^\/interviews\/schedule$/, title: "Schedule Interview" },
  { pattern: /^\/interviews\/[^/]+\/feedback$/, title: "Interview Feedback" },
  { pattern: /^\/interviews$/, title: "Interviews" },

  { pattern: /^\/interview-questions$/, title: "Interview Questions" },
  { pattern: /^\/ai-activity$/, title: "AI Activity" },
  { pattern: /^\/dashboard$/, title: "Dashboard" },
];

export function getTitleForPath(pathname = "/") {
  const cleanPath = pathname.split("?")[0].split("#")[0];
  const matched = ROUTE_TITLE_RULES.find((rule) => rule.pattern.test(cleanPath));
  return matched ? matched.title : "Overview";
}
