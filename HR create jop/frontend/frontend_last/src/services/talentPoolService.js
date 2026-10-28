import apiClient from "./apiClient";
import { parseScore } from "../utils/score";

// Talent-pool service. Contract: src/types/api/candidate.js (TalentPoolRowResponse).
// Pool rows come from the org-wide aggregation endpoint:
//   GET /talent-pool   hold/advanced applications by default; rejected only
//                      with include_rejected=true. Evidence remains tied to
//                      the evaluation referenced by the prior HR decision.
// Field names match the backend exactly (snake_case); the page maps them to its
// display model. score is a STRING from the backend (e.g. "85.000") or null.

export async function getTalentPool({ includeRejected = false } = {}) {
  const { data } = await apiClient.get("/talent-pool", {
    params: includeRejected ? { include_rejected: true } : {},
  });
  return (Array.isArray(data) ? data : []).map(mapBackendRow);
}

export async function createTalentPoolConsentLink(candidateId) {
  const { data } = await apiClient.post(`/candidates/${candidateId}/talent-pool-consent-link`);
  return {
    url: `${window.location.origin}/talent-pool/consent#${data.token}`,
    expiresAt: data.expires_at,
  };
}

export async function previewTalentPoolConsent(token) {
  const { data } = await apiClient.post("/candidate-portal/talent-pool-consent/preview", { token });
  return data;
}

export async function respondToTalentPoolConsent(token, decision) {
  const { data } = await apiClient.post("/candidate-portal/talent-pool-consent/respond", {
    token,
    decision,
    self_attested: true,
  });
  return data;
}

export async function withdrawTalentPoolConsent(candidateId) {
  const { data } = await apiClient.post(
    `/candidates/${candidateId}/talent-pool-consent/withdraw`,
    { candidate_requested: true },
  );
  return data.withdrawn;
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
    consentExpiresAt: row.consent_expires_at || null,
    evidence: Array.isArray(row.evidence) ? row.evidence : [],
    skills: Array.isArray(row.skills) ? row.skills.filter((skill) => typeof skill === "string") : [],
  };
}
