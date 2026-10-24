import apiClient from "./apiClient";
import { evaluateApplication, createDecision } from "./applicationService";
import { getResume, listCandidateProfiles } from "./resumeService";

// Review-flow service. Uses the backend's single aggregation endpoint
// (Phase 4) instead of composing 7 separate calls:
//   GET  /job-applications/{id}/review-bundle   everything the review screen needs
//   POST /job-applications/{id}/evaluate         creates an evaluation run
//   POST /job-applications/{id}/decisions        records an HR decision
//
// Invariants (master-mission contract):
//   - The backend CandidateEvaluationWorkflow is the ONLY source of evaluation
//     creation; this service never fabricates a score or an evaluation object.
//   - Only the HRDecisionCreate payload { decision, reason } is ever submitted.
//   - Score/group are displayed as returned; never computed client-side.

// One call for the full review screen. The backend's ReviewService returns
// application, candidate, job, evaluations, current evaluation, evidence,
// and pool row — all composed server-side.
export async function getReviewBundle(applicationId) {
  const { data } = await apiClient.get(`/job-applications/${applicationId}/review-bundle`);
  return {
    application: data.application,
    candidate: data.candidate,
    job: data.job,
    evaluations: data.evaluations || [],
    evaluation: data.evaluation,
    evidence: data.evidence || [],
    poolRow: data.pool_row,
  };
}

// Runs a synchronous backend evaluation run and returns the run result
// ({ evaluation_id, workflow_run_id, version_number }); the page refetches the
// evaluation + evidence afterwards.
export async function runEvaluation(applicationId) {
  return evaluateApplication(applicationId);
}

// Records an HR decision through the backend DecisionService API. Only the
// decision vocabulary from src/types/api/decision.js is valid, and only
// { decision, reason } is transmitted.
export async function recordDecision(applicationId, decision, reason, expectedEvaluationId) {
  const payload = {
    decision,
    reason: (reason || "").trim() || undefined,
    expected_evaluation_id: expectedEvaluationId || undefined,
  };
  return createDecision(applicationId, payload);
}

// Full review-workspace load: the review bundle plus the resume metadata and
// the latest current CandidateProfile, both fetched through EXISTING read
// endpoints (GET /resumes/{id}, GET /resumes/{id}/profiles). Either extras
// fetch failure degrades to null — the review screen must never fail because
// resume/profile metadata is missing.
export async function getReviewWorkspace(applicationId) {
  const bundle = await getReviewBundle(applicationId);
  const extras = await loadResumeAndProfile(bundle.application);
  return { ...bundle, ...extras };
}

async function loadResumeAndProfile(application) {
  if (!application?.resume_id) return { resume: null, profile: null };

  let resume = null;
  try {
    resume = await getResume(application.resume_id);
  } catch {
    resume = null;
  }

  let profile = null;
  try {
    const profiles = await listCandidateProfiles(application.resume_id);
    profile =
      (Array.isArray(profiles) && profiles.find((p) => p.is_current)) ||
      (Array.isArray(profiles) && profiles[0]) ||
      null;
  } catch {
    profile = null;
  }
  return { resume, profile };
}