import apiClient from "./apiClient";
import { parseScore } from "../utils/score";

// Talent-pool service. Contract: src/types/api/candidate.js (TalentPoolRowResponse).
// Pool rows come from the org-wide aggregation endpoint:
//   GET /talent-pool   hold/advanced applications (status in {hold, advanced}),
//                      ranked by current evaluation score, decision left-joined.
// Field names match the backend exactly (snake_case); the page maps them to its
// display model. score is a STRING from the backend (e.g. "85.000") or null.

export async function getTalentPool() {
  const { data } = await apiClient.get("/talent-pool");
  return (Array.isArray(data) ? data : []).map(mapBackendRow);
}

function mapBackendRow(row) {
  const rawScore = parseScore(row.score);
  return {
    id: row.application_id,
    applicationId: row.application_id,
    candidateId: row.candidate_id,
    jobId: row.job_id,
    name: row.full_name || "Unknown",
    email: row.email || "",
    phone: row.phone || "",
    jobTitle: row.job_title || "—",
    group: row.group || "",
    score: rawScore,
    status: row.status || "",
    decision: row.decision || "",
    decisionCreatedAt: row.decision_created_at || null,
    skills: Array.isArray(row.skills) ? row.skills.filter((skill) => typeof skill === "string") : [],
  };
}
