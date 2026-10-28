import axios from "axios";

const apiBase = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

// Candidate-link requests deliberately omit the shared authenticated apiClient.
// The bearer capability is sent only in JSON, never in the URL or headers.
async function post(path, payload) {
  const { data } = await axios.post(`${apiBase}${path}`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  return data;
}

export function getCandidateInterviewPreview(token) {
  return post("/candidate-portal/interview/preview", { token });
}

export function getCandidateInterviewMonth(token, month) {
  return post("/candidate-portal/interview/slots", { token, month });
}

export function bookCandidateInterview({ token, availabilityId, scheduledTime }) {
  return post("/candidate-portal/interview/book", {
    token,
    availability_id: availabilityId,
    scheduled_time: scheduledTime,
  });
}
