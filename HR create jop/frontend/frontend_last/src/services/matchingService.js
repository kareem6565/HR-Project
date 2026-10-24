import apiClient from "./apiClient";
import { parseScore } from "../utils/score";

// Matching-results service backed entirely by the real backend.
//
// Candidate ranking is composed from the org-wide application aggregation
// endpoint (GET /job-applications), which returns every application - not
// just hold/advanced like the talent pool - together with the candidate
// name, job title, status, the persisted current evaluation score, the
// backend-assigned grouping band, and a compact summary of the requirement
// evidence (matched / partial / missing) for the current evaluation. This
// lets Ranking show the full pipeline sorted by AI score for any job.
//
// The backend assigns `score`/`group` and classifies every evidence item;
// this service never computes or fabricates any of them. It only normalizes
// the score string to a number for display/sorting.

export async function getRanking() {
  const { data } = await apiClient.get("/job-applications");
  const rows = Array.isArray(data) ? data : [];
  const mapEvidence = (evidence) =>
    (Array.isArray(evidence) ? evidence : []).map((item) => ({
      requirementKey: item.requirement_key || "",
      evidenceType: item.evidence_type || "",
      text: item.text || item.requirement_key || "",
    }));
  return rows.map((row) => {
    const rawScore = parseScore(row.score);
    const score = rawScore;
    return {
      id: row.id,
      applicationId: row.id,
      candidateId: row.candidate_id,
      candidateName: row.candidate_name || "Unknown",
      jobId: row.job_id,
      jobTitle: row.job_title || "—",
      status: row.status || "",
      score,
      reviewed: score !== null,
      group: row.group || "",
      evidence: mapEvidence(row.evidence),
    };
  });
}

export async function recordPipelineDecision(applicationId, decision, reason = null) {
  const payload = { decision };
  if (reason) {
    payload.reason = reason;
  }
  const { data } = await apiClient.post(`/job-applications/${applicationId}/decisions`, payload);
  return data;
}
