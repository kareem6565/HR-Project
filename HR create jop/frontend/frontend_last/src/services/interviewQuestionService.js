import apiClient from "./apiClient";

// Interview Questions service. Contract:
// backend/app/api/v1/schemas/interview_questions.py.
//
// The backend holds the curated question banks and, when a candidate_id is
// provided, generates Candidate-Specific questions from the candidate's real
// profile skills (matching) and missing requirement evidence (gaps).

export async function getInterviewQuestions(candidateId) {
  const params = {};
  if (candidateId) params.candidate_id = candidateId;
  const { data } = await apiClient.get("/interview-questions", { params });
  return data;
}