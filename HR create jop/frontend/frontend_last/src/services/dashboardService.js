import apiClient from "./apiClient";
import { getApplications } from "./applicationService";

// Dashboard service — every number is computed from the real backend data the
// app already fetches (jobs + applications). There are no dash- specific
// backend endpoints.

async function loadData() {
  const [apps, jobsRes] = await Promise.all([getApplications(), apiClient.get("/jobs")]);
  return {
    apps,
    jobs: Array.isArray(jobsRes.data) ? jobsRes.data : [],
  };
}

export async function getDashboardStats() {
  const { apps, jobs } = await loadData();
  const advanced = apps.filter((a) => a.status === "advanced").length;
  return {
    candidatesWithApplications: new Set(apps.map((a) => a.candidateId).filter(Boolean)).size,
    activeJobs: jobs.filter((j) => j.status === "active").length,
    applications: apps.length,
    shortlisted:
      apps.filter((a) => a.status === "advanced" || a.status === "ready_for_review").length,
    // The deepest forward state the backend tracks is `advanced` (no hired).
    advancedApplications: advanced,
  };
}

export async function getApplicationsByJob() {
  const { apps } = await loadData();
  const byJob = {};
  for (const a of apps) byJob[a.job] = (byJob[a.job] || 0) + 1;
  return Object.entries(byJob).map(([job, applications]) => ({ job, applications }));
}

export async function getCandidateStatusBreakdown() {
  const { apps } = await loadData();
  const counts = {};
  for (const a of apps) counts[a.status] = (counts[a.status] || 0) + 1;
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
}

// The funnel is derived from the application status vocabulary. Stages are
// cumulative through the backend's pipeline.
export async function getHiringFunnel() {
  const { apps } = await loadData();
  const sums = {
    "Applied": 0,
    "Analysis": 0,
    "Ready for Review": 0,
    "Hold": 0,
    "Advanced": 0,
    "Rejected": 0,
  };
  for (const a of apps) {
    if (a.status === "created") sums["Applied"] += 1;
    else if (["analysis_pending", "analyzing", "analysis_failed"].includes(a.status)) sums["Analysis"] += 1;
    else if (a.status === "ready_for_review") sums["Ready for Review"] += 1;
    else if (a.status === "hold") sums["Hold"] += 1;
    else if (a.status === "advanced") sums["Advanced"] += 1;
    else if (a.status === "rejected") sums["Rejected"] += 1;
  }
  return Object.entries(sums).map(([stage, count]) => ({ stage, count }));
}
