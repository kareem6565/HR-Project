"""Structured AI output contracts.

Phase 3.2: provider-agnostic, validated data contracts describing what an LLM or
deterministic extractor is expected to produce. Each contract is a plain
Pydantic model (no database behavior, no SQLAlchemy, no HR final decision
fields) validated by helpers that raise the shared application ValidationError.
"""

from app.ai.contracts.candidate_profile import CandidateProfileExtractionOutput
from app.ai.contracts.evaluation import EvaluationExplanationOutput
from app.ai.contracts.hera import (
    MAX_REPLY_LINKS,
    MAX_TOOL_CALLS,
    HERALink,
    HERAPlanOutput,
    HERAReplyOutput,
    HERAToolCall,
    validate_hera_plan,
    validate_hera_reply,
)
from app.ai.contracts.interview_questions import (
    InterviewQuestionOutput,
    InterviewQuestionReviewGuide,
    InterviewQuestionSetOutput,
    validate_interview_question_set,
)
from app.ai.contracts.job_draft import JobDraftSuggestionOutput
from app.ai.contracts.job_profile import (
    REQUIREMENT_CATEGORIES,
    REQUIREMENT_DIMENSIONS,
    JobProfileExtractionOutput,
    JobRequirement,
    requirement_key,
)
from app.ai.contracts.match_evidence import (
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    MatchEvidenceListOutput,
    MatchEvidenceOutput,
    is_requirement_key,
)
from app.ai.contracts.schema import (
    AI_CONTRACT_SCHEMA_VERSION,
    INTERVIEW_QUESTION_SCHEMA_VERSION,
    JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
)
from app.ai.contracts.validation import (
    normalize_job_profile_requirements,
    validate_candidate_profile_extraction,
    validate_evaluation_explanation,
    validate_job_draft_suggestion,
    validate_job_profile_extraction,
    validate_match_evidence,
    validate_match_evidence_list,
)

__all__ = [
    "AI_CONTRACT_SCHEMA_VERSION",
    "CandidateProfileExtractionOutput",
    "EVIDENCE_CONTRACT_SCHEMA_VERSION",
    "EvaluationExplanationOutput",
    "HERALink",
    "HERAPlanOutput",
    "HERAReplyOutput",
    "HERAToolCall",
    "InterviewQuestionOutput",
    "InterviewQuestionReviewGuide",
    "InterviewQuestionSetOutput",
    "INTERVIEW_QUESTION_SCHEMA_VERSION",
    "JOB_PROFILE_EXTRACTION_SCHEMA_VERSION",
    "JobDraftSuggestionOutput",
    "JobProfileExtractionOutput",
    "JobRequirement",
    "MAX_REPLY_LINKS",
    "MAX_TOOL_CALLS",
    "MatchEvidenceListOutput",
    "MatchEvidenceOutput",
    "REQUIREMENT_CATEGORIES",
    "REQUIREMENT_DIMENSIONS",
    "SUPPORTED_SCHEMA_VERSIONS",
    "is_requirement_key",
    "normalize_job_profile_requirements",
    "requirement_key",
    "validate_candidate_profile_extraction",
    "validate_evaluation_explanation",
    "validate_hera_plan",
    "validate_hera_reply",
    "validate_interview_question_set",
    "validate_job_draft_suggestion",
    "validate_job_profile_extraction",
    "validate_match_evidence",
    "validate_match_evidence_list",
]
