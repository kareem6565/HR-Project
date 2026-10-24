import apiClient from "./apiClient";

// Real-job service. Contract: src/types/api/job.js.
//
// The backend job model stores structured fields directly (department,
// location, job_type, experience, requirements/required_skills JSONB lists),
// plus status and a raw_description summary that the AI job-profile pipeline
// consumes.

function buildRawDescription(job) {
  const description = stripDerivedSuffix(job.description, job.requirements, job.requiredSkills);
  const parts = [
    description,
    ...(job.requirements || []).map((r) => `- ${r}`),
    ...(job.requiredSkills || []).map((s) => `Skills: ${s}`),
  ].filter(Boolean);
  return parts.length ? parts.join("\n") : job.title || "";
}

// raw_description is a derived composition (see buildRawDescription). The edit
// form preloads that composed value as `description`, so before recomposing we
// strip the exact derived suffix; otherwise an unchanged save grows the stored
// description every time (requirement/skill lines duplicate on each save).
function stripDerivedSuffix(raw, requirements, requiredSkills) {
  if (!raw) return raw || "";
  const derived = [
    ...(requirements || []).map((r) => `- ${r}`),
    ...(requiredSkills || []).map((s) => `Skills: ${s}`),
  ].join("\n");
  if (!derived) return raw;
  if (raw === derived) return "";
  const suffix = `\n${derived}`;
  return raw.endsWith(suffix) ? raw.slice(0, raw.length - suffix.length) : raw;
}

// Full payload for POST /jobs.
function toBackendCreate(job) {
  return {
    title: job.title,
    raw_description: buildRawDescription(job),
    status: job.status || "draft",
    department: job.department,
    location: job.location,
    job_type: job.type,
    experience: job.experience,
    requirements: job.requirements || [],
    required_skills: job.requiredSkills || [],
  };
}

// Partial payload for PATCH /jobs/{id}: only the keys the caller actually
// changed, so a status-only update never wipes the other fields.
function toBackendUpdate(updates) {
  const body = {};
  if (updates.title !== undefined) body.title = updates.title;
  if (updates.status !== undefined) body.status = updates.status;
  if (updates.department !== undefined) body.department = updates.department;
  if (updates.location !== undefined) body.location = updates.location;
  if (updates.type !== undefined) body.job_type = updates.type;
  if (updates.experience !== undefined) body.experience = updates.experience;
  if (updates.requirements !== undefined) body.requirements = updates.requirements;
  if (updates.requiredSkills !== undefined) body.required_skills = updates.requiredSkills;
  if (
    updates.description !== undefined ||
    updates.requirements !== undefined ||
    updates.requiredSkills !== undefined
  ) {
    body.raw_description = buildRawDescription(updates);
  }
  return body;
}

function adaptFromBackend(job) {
  if (!job) return null;
  return {
    id: job.id,
    title: job.title,
    status: job.status,
    description: job.raw_description || "",
    department: job.department || "",
    location: job.location || "",
    type: job.job_type || "Full-time",
    experience: job.experience || "",
    requirements: job.requirements || [],
    requiredSkills: job.required_skills || [],
    createdAt: job.created_at,
    applicants: job._applicantCount ?? 0,
  };
}

// The backend JobResponse has no applicant count, but the UI surfaces one.
// Derive it from the job-scoped application list (GET /jobs/{id}/applications).
async function withApplicantCount(job) {
  if (!job) return job;
  try {
    const { data } = await apiClient.get(`/jobs/${job.id}/applications`);
    return { ...job, _applicantCount: Array.isArray(data) ? data.length : 0 };
  } catch {
    return { ...job, _applicantCount: 0 };
  }
}

export async function getJobs() {
  const { data } = await apiClient.get("/jobs");
  const rows = Array.isArray(data) ? data : [];
  const withCounts = await Promise.all(rows.map(withApplicantCount));
  return withCounts.map(adaptFromBackend);
}

export async function getJobById(id) {
  const { data } = await apiClient.get(`/jobs/${id}`);
  const counted = await withApplicantCount(data);
  return adaptFromBackend(counted);
}

export async function createJob(job) {
  const { data } = await apiClient.post("/jobs", toBackendCreate(job));
  return adaptFromBackend(data);
}

// Advisory HERA auto-fill for the JobForm. The endpoint only ever receives the
// raw description and returns suggested field values; it never persists, never
// scores or rates, and exposes no confidence fields.
export async function suggestJobDraft(rawDescription) {
  const { data } = await apiClient.post("/jobs/ai/suggest-form", {
    raw_description: rawDescription,
  });
  return {
    title: data?.title || "",
    department: data?.department || "",
    location: data?.location || "",
    type: data?.job_type || "",
    experience: data?.experience || "",
    requirements: data?.requirements || [],
    requiredSkills: data?.required_skills || [],
  };
}

export async function updateJob(id, updates) {
  const { data } = await apiClient.patch(`/jobs/${id}`, toBackendUpdate(updates));
  return adaptFromBackend(data);
}

export async function deleteJob(id) {
  await apiClient.delete(`/jobs/${id}`);
  return { success: true };
}