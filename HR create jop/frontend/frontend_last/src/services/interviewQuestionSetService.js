import apiClient from "./apiClient";

// Interview Question Sets service. Contract:
// backend/app/api/v1/schemas/interview_question_sets.py.
//
// Question sets are job-application scoped and follow an HR-in-the-loop
// lifecycle: the AI generates (generateQuestionSet), HR edits/reorders
// (updateQuestionSet), and HR approves (approveQuestionSet) before a set can
// be attached to an interview. Categories are lowercase on the wire and mapped
// to display form here.

const STATUS_DISPLAY = {
  generated: "Generated",
  approved: "Approved",
  superseded: "Superseded",
};

const CATEGORY_DISPLAY = {
  technical: "Technical",
  behavioral: "Behavioral",
  situational: "Situational",
  candidate_specific: "Candidate-Specific",
};

function mapCategory(category) {
  return CATEGORY_DISPLAY[category] || category;
}

function mapReviewGuide(guide) {
  if (!guide || typeof guide !== "object") return null;
  return {
    purpose: guide.purpose || "",
    evidenceBasis: guide.evidence_basis || "",
    sourceQuote: guide.source_quote || null,
    interviewerLooksFor: guide.interviewer_looks_for || "",
    evaluationRubric: Array.isArray(guide.evaluation_rubric)
      ? guide.evaluation_rubric
      : [],
  };
}

function reviewGuidePayload(guide) {
  if (!guide) return null;
  return {
    purpose: guide.purpose,
    evidence_basis: guide.evidenceBasis,
    source_quote: guide.sourceQuote || null,
    interviewer_looks_for: guide.interviewerLooksFor,
    evaluation_rubric: guide.evaluationRubric,
  };
}

function mapQuestion(question) {
  return {
    id: question.id ?? null,
    category: question.category,
    categoryLabel: mapCategory(question.category),
    text: question.text || "",
    topic: question.topic || "",
    requirementKey: question.requirement_key || null,
    reviewGuide: mapReviewGuide(question.review_guide),
  };
}

function mapSet(questionSet) {
  return {
    id: questionSet.id,
    jobApplicationId: questionSet.job_application_id,
    versionNumber: questionSet.version_number,
    status: questionSet.status,
    statusLabel: STATUS_DISPLAY[questionSet.status] || questionSet.status,
    generatedBy: questionSet.generated_by || "",
    approvedByUserId: questionSet.approved_by_user_id || null,
    approvedAt: questionSet.approved_at || null,
    isCurrent: !!questionSet.is_current,
    provenance: questionSet.provenance || null,
    createdAt: questionSet.created_at,
    questions: (questionSet.questions || []).map(mapQuestion),
  };
}

// Runs the real-AI generation workflow for an application. Returns the newly
// created (draft) set.
export async function generateQuestionSet(applicationId) {
  const { data } = await apiClient.post(
    `/job-applications/${applicationId}/question-sets/generate`
  );
  return mapSet(data);
}

// Returns all question-set versions for an application (newest first) plus
// the id of the current (approved) set.
export async function listQuestionSets(applicationId) {
  const { data } = await apiClient.get(`/job-applications/${applicationId}/question-sets`);
  return {
    total: data.total || 0,
    currentId: data.current_id || null,
    questionSets: (data.question_sets || []).map(mapSet),
  };
}

// Lists one candidate's job applications (org-scoped, newest first). Used by
// application-aware entry points so the job application is explicit before any
// question preparation starts — the system never guesses a "latest" app.
export async function findCandidateApplications(candidateId) {
  const { data } = await apiClient.get("/job-applications", {
    params: { candidate_id: candidateId },
  });
  return (data || []).map((row) => ({
    id: row.id,
    jobId: row.job_id,
    jobTitle: row.job_title,
    status: row.status,
    createdAt: row.created_at,
  }));
}

function questionPayload(questions) {
  return questions.map((question) => ({
    category: question.category,
    text: question.text,
    topic: question.topic || null,
    requirement_key: question.requirementKey || null,
    review_guide: reviewGuidePayload(question.reviewGuide),
  }));
}

// Creates an HR-curated draft ("generated", generated_by="hr") question set for
// an application. Only called when no editable draft exists yet — saving on top
// of an approved set must never touch the approved set, so the page then
// creates a fresh draft and lets HR approve explicitly in the builder.
export async function createQuestionSet(applicationId, questions) {
  const payload = { questions: questionPayload(questions) };
  const { data } = await apiClient.post(
    `/job-applications/${applicationId}/question-sets`,
    payload
  );
  return mapSet(data);
}

// Persists HR's selection from the prep workspace for a known application:
// updates the existing generated draft in place (same set id, order preserved)
// or creates a new draft when none exists.
export async function saveSelectedQuestions(applicationId, questions) {
  const { questionSets } = await listQuestionSets(applicationId);
  const draft = questionSets.find((set) => set.status === "generated");
  if (draft) return updateQuestionSet(draft.id, questions);
  return createQuestionSet(applicationId, questions);
}

export async function getQuestionSet(questionSetId) {
  const { data } = await apiClient.get(`/interview-question-sets/${questionSetId}`);
  return mapSet(data);
}

// Persists HR's select / edit / reorder / add / remove of the questions on a
// non-approved set.
export async function updateQuestionSet(questionSetId, questions) {
  const payload = {
    questions: questions.map((question) => ({
      category: question.category,
      text: question.text,
      topic: question.topic || null,
      requirement_key: question.requirementKey || null,
      review_guide: reviewGuidePayload(question.reviewGuide),
    })),
  };
  const { data } = await apiClient.put(`/interview-question-sets/${questionSetId}`, payload);
  return mapSet(data);
}

// Approves the set; it becomes the current approved set for the application
// and can be attached to scheduled interviews.
export async function approveQuestionSet(questionSetId) {
  const { data } = await apiClient.post(`/interview-question-sets/${questionSetId}/approve`);
  return mapSet(data);
}
