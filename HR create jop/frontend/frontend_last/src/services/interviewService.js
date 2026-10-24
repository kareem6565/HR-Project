import apiClient from "./apiClient";

// Interview service. Contract: backend/app/api/v1/schemas/interviews.py.
//
// The backend stores statuses/types lowercase; this service maps them to the
// display form the pages render ("Scheduled", "Technical", ...). Feedback is
// snake_case on the wire (`problem_solving` / `submitted_by`) and camelCase
// in the UI. Interviewers are org users — they have no role field, so the
// pages only render a role when one is present.

const STATUS_DISPLAY = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};

const TYPE_DISPLAY = {
  technical: "Technical",
  hr: "HR",
  behavioral: "Behavioral",
};

// "10:00:00" / "10:00" -> "10:00 AM" for display.
function formatTime(value) {
  if (!value) return "";
  const match = String(value).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return value;
  const hours = Number(match[1]);
  const minutes = match[2];
  const suffix = hours >= 12 ? "PM" : "AM";
  const displayHour = hours % 12 || 12;
  return `${displayHour}:${minutes} ${suffix}`;
}

// "10:00 AM" -> "10:00" for storage.
function toBackendTime(value) {
  const match = String(value).match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return value;
  let hours = Number(match[1]) % 12;
  if (match[3].toUpperCase() === "PM") hours += 12;
  return `${String(hours).padStart(2, "0")}:${match[2]}`;
}

function adaptFeedback(feedback) {
  if (!feedback) return null;
  return {
    technical: feedback.technical ?? 0,
    communication: feedback.communication ?? 0,
    problemSolving: feedback.problem_solving ?? 0,
    overall: feedback.overall ?? 0,
    comments: feedback.comments || "",
    submittedBy: feedback.submitted_by || "",
    submittedAt: feedback.submitted_at || "",
  };
}

function adaptInterview(row) {
  const status = STATUS_DISPLAY[row.status] || row.status;
  const type = TYPE_DISPLAY[row.interview_type] || row.interview_type;
  const interviewerName = row.interviewer_name || "";
  return {
    id: row.id,
    candidateId: row.candidate_id,
    candidateName: row.candidate_name || "Unknown",
    candidateEmail: row.candidate_email || "",
    jobId: row.job_id,
    job: row.job_title || "",
    type,
    status,
    date: row.scheduled_date,
    time: formatTime(row.scheduled_time),
    interviewer: interviewerName,
    interviewers: interviewerName
      ? [{ id: row.interviewer_user_id, name: interviewerName, role: "" }]
      : [],
    feedback: adaptFeedback(row.feedback),
    durationMinutes: row.scheduled_duration_minutes || 60,
    questionSetId: row.interview_question_set_id || null,
  };
}

// `status` is the display form (Scheduled / Completed / Cancelled); it is
// sent to the backend lowercase. Omit (or "all") for every interview.
export async function getInterviews(status) {
  const params = {};
  if (status && status !== "all") params.status = status.toLowerCase();
  const { data } = await apiClient.get("/interviews", { params });
  return (data.interviews || []).map(adaptInterview);
}

export async function getInterviewById(id) {
  const { data } = await apiClient.get(`/interviews/${id}`);
  return adaptInterview(data);
}

export async function getInterviewers() {
  const { data } = await apiClient.get("/interviewers");
  return (Array.isArray(data) ? data : []).map((user) => ({
    id: user.id,
    name: user.full_name,
    role: "",
  }));
}

// Books an interview slot for a screened candidate + job. The backend
// resolves (and validates) the JobApplication from candidate_id + job_id and
// hard-blocks overlapping slots for the same interviewer or candidate (409).
// A duration (default 60) and an approved interview question set may be
// attached; the backend validates the set belongs to the candidate's
// application and is approved.
export async function scheduleInterview({
  candidate,
  job,
  interviewer,
  date,
  time,
  durationMinutes = 60,
  questionSetId = null,
}) {
  const { data } = await apiClient.post("/interviews", {
    candidate_id: candidate.id,
    job_id: job?.id,
    interviewer_user_id: interviewer || null,
    interview_type: "technical",
    scheduled_date: date,
    scheduled_time: toBackendTime(time),
    scheduled_duration_minutes: durationMinutes,
    interview_question_set_id: questionSetId || null,
  });
  return adaptInterview(data);
}

// Occupied interview windows for a date (optionally per interviewer), so the
// schedule page can disable conflicting times up front. Windows mirror the
// backend's exclusive-end overlap rule.
export async function getInterviewSlots(scheduledDate, interviewerUserId) {
  const params = {
    scheduled_date: scheduledDate,
  };
  if (interviewerUserId) params.interviewer_user_id = interviewerUserId;
  const { data } = await apiClient.get("/interview-slots", { params });
  return {
    date: data.date,
    total: data.total || 0,
    occupied: (data.occupied || []).map((slot) => ({
      interviewId: slot.interview_id,
      interviewerUserId: slot.interviewer_user_id,
      startMinutes: slot.start_minutes,
      endMinutes: slot.end_minutes,
      startTime: slot.start_time,
      endTime: slot.end_time,
    })),
  };
}

export async function cancelInterview(id) {
  const { data } = await apiClient.patch(`/interviews/${id}`, { status: "cancelled" });
  return adaptInterview(data);
}

// Feedback is entered by the interviewer after the interview happens and
// marks the interview as Completed. The overall rating is a simple average
// of the three sub-scores — presentation logic that stays on the frontend.
export async function submitInterviewFeedback(id, feedback) {
  const { data } = await apiClient.post(`/interviews/${id}/feedback`, {
    technical: feedback.technical,
    communication: feedback.communication,
    problem_solving: feedback.problemSolving,
    overall: feedback.overall,
    comments: feedback.comments || null,
    submitted_by: feedback.submittedBy || null,
  });
  return adaptInterview(data);
}