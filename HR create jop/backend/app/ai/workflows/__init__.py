"""Workflow orchestration for deterministic, single-run AI operations.

Phase 3.4 introduced ``JobProfileExtractionWorkflow`` and Phase 3.5 adds
``CandidateProfileExtractionWorkflow``. Phase 3.6 adds
``CandidateEvaluationWorkflow``, which synchronously evaluates a JobApplication
against an approved/current JobProfile and a current CandidateProfile,
persisting MatchEvidence and a new versioned CandidateEvaluation. Each workflow
orchestrates loading source entities, validating the required deterministic
input, calling the AI provider for structured data, validating that data,
persisting a new versioned artifact, and recording workflow/step/AI traces.
Workflows depend only on the provider-agnostic ``AIProvider`` interface and
never commit; the caller owns the transaction so any failure rolls back safely.
Real provider adapters, LangChain/LangGraph/agents, resume parsing, scoring,
workers, and async execution are intentionally out of scope.
"""

from app.ai.workflows.candidate_evaluation import (
    EVIDENCE_AI_COMPONENT as CANDIDATE_EVALUATION_EVIDENCE_COMPONENT,
)
from app.ai.workflows.candidate_evaluation import (
    EXPLANATION_AI_COMPONENT as CANDIDATE_EVALUATION_EXPLANATION_COMPONENT,
)
from app.ai.workflows.candidate_evaluation import (
    PROMPT_VERSION as CANDIDATE_EVALUATION_PROMPT_VERSION,
)
from app.ai.workflows.candidate_evaluation import (
    STEP_NAME as CANDIDATE_EVALUATION_STEP,
)
from app.ai.workflows.candidate_evaluation import (
    WORKFLOW_TYPE as CANDIDATE_EVALUATION_WORKFLOW_TYPE,
)
from app.ai.workflows.candidate_evaluation import (
    CandidateEvaluationResult,
    CandidateEvaluationWorkflow,
)
from app.ai.workflows.candidate_profile_extraction import (
    AI_COMPONENT_NAME as CANDIDATE_PROFILE_AI_COMPONENT,
)
from app.ai.workflows.candidate_profile_extraction import (
    PROMPT_VERSION as CANDIDATE_PROFILE_PROMPT_VERSION,
)
from app.ai.workflows.candidate_profile_extraction import (
    STEP_NAME as CANDIDATE_PROFILE_STEP,
)
from app.ai.workflows.candidate_profile_extraction import (
    WORKFLOW_TYPE as CANDIDATE_PROFILE_WORKFLOW_TYPE,
)
from app.ai.workflows.candidate_profile_extraction import (
    CandidateProfileExtractionResult,
    CandidateProfileExtractionWorkflow,
)
from app.ai.workflows.hera_assistant import (
    COMPOSE_AI_COMPONENT as HERA_COMPOSE_AI_COMPONENT,
)
from app.ai.workflows.hera_assistant import (
    PLAN_AI_COMPONENT as HERA_PLAN_AI_COMPONENT,
)
from app.ai.workflows.hera_assistant import (
    PROMPT_VERSION as HERA_PROMPT_VERSION,
)
from app.ai.workflows.hera_assistant import (
    STEP_COMPOSE as HERA_STEP_COMPOSE,
)
from app.ai.workflows.hera_assistant import (
    STEP_PLAN as HERA_STEP_PLAN,
)
from app.ai.workflows.hera_assistant import (
    WORKFLOW_TYPE as HERA_WORKFLOW_TYPE,
)
from app.ai.workflows.hera_assistant import (
    HERAAssistantResult,
    HERAAssistantWorkflow,
    HERAToolInvocation,
)
from app.ai.workflows.interview_questions import (
    AI_COMPONENT_NAME as INTERVIEW_QUESTION_AI_COMPONENT,
)
from app.ai.workflows.interview_questions import (
    PROMPT_VERSION as INTERVIEW_QUESTION_PROMPT_VERSION,
)
from app.ai.workflows.interview_questions import (
    STEP_NAME as INTERVIEW_QUESTION_STEP,
)
from app.ai.workflows.interview_questions import (
    WORKFLOW_TYPE as INTERVIEW_QUESTION_WORKFLOW_TYPE,
)
from app.ai.workflows.interview_questions import (
    InterviewQuestionGenerationResult,
    InterviewQuestionGenerationWorkflow,
)
from app.ai.workflows.job_profile_extraction import (
    AI_COMPONENT_NAME,
    PROMPT_VERSION,
    STEP_NAME,
    WORKFLOW_TYPE,
    JobProfileExtractionResult,
    JobProfileExtractionWorkflow,
)

__all__ = [
    "AI_COMPONENT_NAME",
    "PROMPT_VERSION",
    "STEP_NAME",
    "WORKFLOW_TYPE",
    "CANDIDATE_EVALUATION_EVIDENCE_COMPONENT",
    "CANDIDATE_EVALUATION_EXPLANATION_COMPONENT",
    "CANDIDATE_EVALUATION_PROMPT_VERSION",
    "CANDIDATE_EVALUATION_STEP",
    "CANDIDATE_EVALUATION_WORKFLOW_TYPE",
    "CandidateEvaluationResult",
    "CandidateEvaluationWorkflow",
    "CANDIDATE_PROFILE_AI_COMPONENT",
    "CANDIDATE_PROFILE_PROMPT_VERSION",
    "CANDIDATE_PROFILE_STEP",
    "CANDIDATE_PROFILE_WORKFLOW_TYPE",
    "CandidateProfileExtractionResult",
    "CandidateProfileExtractionWorkflow",
    "HERA_COMPOSE_AI_COMPONENT",
    "HERA_PLAN_AI_COMPONENT",
    "HERA_PROMPT_VERSION",
    "HERA_STEP_COMPOSE",
    "HERA_STEP_PLAN",
    "HERA_WORKFLOW_TYPE",
    "HERAAssistantResult",
    "HERAAssistantWorkflow",
    "HERAToolInvocation",
    "JobProfileExtractionResult",
    "JobProfileExtractionWorkflow",
    "INTERVIEW_QUESTION_AI_COMPONENT",
    "INTERVIEW_QUESTION_PROMPT_VERSION",
    "INTERVIEW_QUESTION_STEP",
    "INTERVIEW_QUESTION_WORKFLOW_TYPE",
    "InterviewQuestionGenerationResult",
    "InterviewQuestionGenerationWorkflow",
]
