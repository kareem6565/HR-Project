import apiClient from "./apiClient";

// AI Activity service. Contract: backend/app/api/v1/schemas/ai_activity.py.
//
// This page is workflow observability, not an AI agent — it just displays
// execution traces the backend's AI evaluation pipeline already recorded.
// The backend returns a snake_case read model; this service maps it to the
// page shape (durations/timestamps formatted, statuses normalized) so the
// UI never sees raw trace plumbing.

function formatDuration(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTimestamp(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const date = d.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${date} · ${time}`;
}

function normalizeStatus(status) {
  if (status === "completed") return "success";
  if (status === "failed") return "error";
  return status || "running";
}

function adaptRun(run) {
  return {
    id: run.id,
    runId: run.run_id,
    title: run.title || run.workflow_type || "Workflow Run",
    candidateName: run.candidate_name || "",
    job: run.job_title || "",
    provider: run.provider || "unknown",
    model: run.model || "unknown",
    timestamp: formatTimestamp(run.timestamp),
    totalDuration: formatDuration(run.total_duration_ms),
    status: normalizeStatus(run.status),
    schema: run.schema_version || "—",
    prompt: run.prompt || "—",
    steps: (run.steps || []).map((step) => ({
      name: step.name,
      status: normalizeStatus(step.status),
      duration: formatDuration(step.duration_ms),
    })),
  };
}

export async function getAIActivityRuns() {
  const { data } = await apiClient.get("/ai-activity/runs");
  return (Array.isArray(data) ? data : []).map(adaptRun);
}

export async function getAIActivityStats() {
  const { data } = await apiClient.get("/ai-activity/stats");
  return {
    totalRuns24h: data.total_runs_24h,
    successful: data.successful,
    failed: data.failed,
    avgLatency:
      data.avg_latency_ms == null ? "—" : formatDuration(data.avg_latency_ms),
  };
}

export async function retryRun(id) {
  const { data } = await apiClient.post(`/ai-activity/runs/${id}/retry`);
  return data;
}