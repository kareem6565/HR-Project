import apiClient from "./apiClient";
import { listCandidateProfiles, listCandidateResumes } from "./resumeService";
import { parseScore } from "../utils/score";

// Candidate service. Contract: src/types/api/candidate.js.
//
// The list is backed by the org-wide roster (GET /candidates) and enriched
// client-side from each candidate's latest current Candidate Profile where
// one exists. A job-scoped pool variant (GET /jobs/{id}/candidates, the only
// source of per-job scores) is kept for the talent pool. Single-candidate
// reads hit GET /candidates/{id}.

// Maps a JobCandidateSummary (pool row) onto the candidate display model.
// score comes back as a STRING ("85.000") — the client keeps its numeric
// number but never computes groups (the backend assigns `group` itself).
function mapPoolRowToCandidate(row) {
  const rawScore = parseScore(row.score);
  const score = rawScore;
  return {
    id: row.candidate_id,
    name: row.full_name || "Unknown",
    email: row.email || "",
    phone: row.phone || "",
    score,
    status: row.status || "active",
    decision: row.decision || "",
    group: row.group || "",
    title: "",
    experience: "",
    matching: [],
    missing: [],
    strengths: [],
    reason: "",
    projects: [],
    education: "",
    links: {},
    cv: "",
  };
}

function adaptFromBackend(c) {
  if (!c) return null;
  return {
    id: c.id,
    name: c.full_name,
    email: c.email || "",
    phone: c.phone || "",
    status: c.status,
    title: "",
    skills: [],
    score: null, // no org-wide score; per-job scores come from the pool
    matching: [],
    missing: [],
    strengths: [],
    reason: "",
    projects: [],
    education: "",
    experience: "",
    summary: "",
    lastInteraction: "",
    appliedAt: c.created_at,
  };
}

// Fold a CandidateProfile's profile_data into the display model. Only fields
// the extraction schema produces (skills, experience, summary) are mapped;
// everything else keeps its "not provided" default.
function applyProfile(row, profile) {
  if (!profile) return row;
  const d = profile.profile_data || {};
  const skills = Array.isArray(d.skills) ? d.skills : [];
  const experience = Array.isArray(d.experience) ? d.experience : [];
  return {
    ...row,
    summary: typeof d.summary === "string" ? d.summary : row.summary,
    // Keep CV-extracted contact values separate from recruiter-maintained
    // candidate fields. A null candidate value can mean HR intentionally
    // cleared it, so extracted values must never overwrite the canonical row.
    profileEmail: typeof d.email === "string" ? d.email : "",
    profilePhone: typeof d.phone === "string" ? d.phone : "",
    skills,
    matching: skills,
    experience: experience.length ? `${experience.length} positions` : row.experience,
    education: typeof d.education === "string" ? d.education : row.education,
  };
}

// Find a candidate's latest current Candidate Profile (newest resume wins).
async function latestProfileFor(candidateId) {
  const resumes = await listCandidateResumes(candidateId);
  if (!resumes.length) return null;
  const ordered = resumes.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  for (const resume of ordered) {
    const profiles = await listCandidateProfiles(resume.id);
    const current =
      profiles.find((p) => p.is_current) ||
      profiles.find((p) => p.status === "current");
    if (current) return current;
  }
  return null;
}

// `params` become the org-wide query: status, search. Passing `jobId` instead
// selects the job-scoped CandidatePoolQuery (status, search, group, decision,
// min_score, max_score).
export async function getCandidates(params = {}) {
  if (params.jobId) {
    const query = {};
    if (params.status) query.status = params.status;
    if (params.decision) query.decision = params.decision;
    if (params.group) query.group = params.group;
    if (params.search) query.search = params.search;
    if (params.min_score !== undefined) query.min_score = params.min_score;
    if (params.max_score !== undefined) query.max_score = params.max_score;
    const { data } = await apiClient.get(`/jobs/${params.jobId}/candidates`, { params: query });
    return (Array.isArray(data) ? data : []).map(mapPoolRowToCandidate);
  }

  const query = {};
  if (params.search) query.search = params.search;
  if (params.status) query.status = params.status;
  const { data } = await apiClient.get("/candidates", { params: query });
  const rows = (Array.isArray(data) ? data : []).map(adaptFromBackend);
  return Promise.all(
    rows.map(async (row) => {
      try {
        return applyProfile(row, await latestProfileFor(row.id));
      } catch {
        return row;
      }
    })
  );
}

export async function getCandidateById(id) {
  const { data } = await apiClient.get(`/candidates/${id}`);
  return applyProfile(adaptFromBackend(data), await latestProfileFor(id));
}

export async function updateCandidate(id, { email, phone } = {}) {
  const body = {};
  if (email !== undefined) body.email = email;
  if (phone !== undefined) body.phone = phone;
  const { data } = await apiClient.patch(`/candidates/${id}`, body);
  return adaptFromBackend(data);
}

export async function archiveCandidate(id) {
  const { data } = await apiClient.post(`/candidates/${id}/archive`);
  return adaptFromBackend(data);
}

// Runs the backend's full CV-screening workflow for a job + uploaded PDFs:
// candidate + resume upload + candidate profile extraction + job application
// + evaluation for every uploaded CV.
export async function screenCandidates({ jobId, files }) {
  if (!jobId) {
    throw new Error("A job must be selected before screening can start.");
  }
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }
  const { data } = await apiClient.post(`/jobs/${jobId}/screen`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
  });
  return data;
}

export {
  createScreeningBatch,
  getScreeningBatch,
  retryBatchItem,
} from "./screeningBatchService";
