// LinkedIn candidate sourcing service.
//
// Talks to the sourcing backend: POST /sourcing/searches starts a search
// (202), GET /sourcing/searches/:id polls it until it succeeds or fails.
// The page (pages/sourcing/) depends only on this module.

import apiClient from "./apiClient";

const DEFAULT_POLL_INTERVAL_MS = 2500;
const DEFAULT_POLL_TIMEOUT_MS = 150000;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function normalizeCandidate(candidate) {
  return {
    id: candidate.id,
    name: candidate.full_name || "LinkedIn candidate",
    headline: candidate.headline || "",
    location: candidate.location || "",
    currentTitle: candidate.current_title || "",
    currentCompany: candidate.current_company || "",
    profileUrl: candidate.profile_url || "",
    email: candidate.email || "",
    phone: candidate.phone || "",
    fitScore: candidate.fit_score ?? null,
    status: candidate.status || "suggested",
  };
}

function normalizeSearch(search) {
  return {
    id: search.id,
    jobId: search.job_id,
    queryText: search.query_text,
    status: search.status,
    errorCode: search.error_code || null,
    errorMessage: search.error_message || null,
    candidates: (search.candidates || []).map(normalizeCandidate),
  };
}

export async function startSourcingSearch({ jobId, needs }) {
  const payload = { query_text: needs || "" };
  if (jobId) payload.job_id = jobId;
  const { data } = await apiClient.post("/sourcing/searches", payload);
  return normalizeSearch(data);
}

export async function getOutreachDraft(candidateId) {
  const { data } = await apiClient.post(`/sourcing/candidates/${candidateId}/outreach-draft`);
  return data;
}

export async function personalizeOutreachDraft(candidateId) {
  const { data } = await apiClient.post(
    `/sourcing/candidates/${candidateId}/outreach-draft/personalize`
  );
  return data;
}

export async function enrichSourcingCandidate(candidateId) {
  const { data } = await apiClient.post(`/sourcing/candidates/${candidateId}/enrich`);
  return normalizeCandidate(data);
}

export async function getSourcingSearch(searchId) {
  const { data } = await apiClient.get(`/sourcing/searches/${searchId}`);
  return normalizeSearch(data);
}

/**
 * Start a sourcing search and poll until it finishes.
 *
 * Resolves with { status: "ok", candidates, searchId } when candidates were
 * found, { status: "unavailable", candidates: [] } when sourcing is not
 * enabled on the backend, and { status: "failed", errorMessage, candidates: [] }
 * when the provider could not complete the search.
 */
export async function searchLinkedInCandidates(
  { jobId, needs },
  { pollIntervalMs = DEFAULT_POLL_INTERVAL_MS, pollTimeoutMs = DEFAULT_POLL_TIMEOUT_MS } = {}
) {
  let search;
  try {
    search = await startSourcingSearch({ jobId, needs });
  } catch (err) {
    if (err?.response?.status === 503) {
      return { status: "unavailable", candidates: [] };
    }
    throw new Error(
      err?.response?.data?.detail || "The sourcing search could not be started."
    );
  }

  const deadline = Date.now() + pollTimeoutMs;
  let current = search;
  while (current.status === "queued" || current.status === "running") {
    if (Date.now() >= deadline) {
      return {
        status: "failed",
        errorMessage: "The search is taking longer than expected. Check back shortly.",
        candidates: [],
        searchId: current.id,
      };
    }
    await sleep(pollIntervalMs);
    current = await getSourcingSearch(current.id);
  }

  if (current.status === "succeeded") {
    return { status: "ok", candidates: current.candidates, searchId: current.id };
  }
  return {
    status: "failed",
    errorMessage: current.errorMessage || "The sourcing provider could not complete this search.",
    candidates: [],
    searchId: current.id,
  };
}
