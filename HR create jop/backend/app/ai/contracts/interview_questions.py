"""Structured AI output for interview question set generation.

Represents the AI-proposed set of interview questions for a candidate against a
job. Only question material is included: it must NOT contain a score, a hire /
reject / advance recommendation, or any HR decision field. The HR professional
remains the final decision maker and curator of the question set.

A question may optionally target a specific job requirement via
``requirement_key``; callers validate that any supplied ``requirement_key``
exists in the exact key set given to the producer, mirroring the match-evidence
contract boundary (schema v1.2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.contracts.match_evidence import is_requirement_key
from app.ai.contracts.schema import INTERVIEW_QUESTION_SCHEMA_VERSION, SchemaVersion

QuestionCategory = Literal["technical", "behavioral", "situational", "candidate_specific"]
QuestionEvidenceBasis = Literal[
    "verified_cv_evidence",
    "verification_question",
    "job_requirement",
]


class InterviewQuestionReviewGuide(BaseModel):
    """Consistent interviewer guidance for a question, grounded in its source."""

    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=1, max_length=1000)
    evidence_basis: QuestionEvidenceBasis
    source_quote: str | None = Field(default=None, max_length=2000)
    interviewer_looks_for: str = Field(min_length=1, max_length=1000)
    evaluation_rubric: list[str] = Field(min_length=2, max_length=5)

    @model_validator(mode="after")
    def _validate_source_quote(self) -> InterviewQuestionReviewGuide:
        if self.evidence_basis == "verified_cv_evidence" and not self.source_quote:
            raise ValueError("Verified CV evidence requires a source_quote.")
        if self.evidence_basis != "verified_cv_evidence" and self.source_quote is not None:
            raise ValueError("Only verified CV evidence may include a source_quote.")
        if any(not item.strip() for item in self.evaluation_rubric):
            raise ValueError("Evaluation rubric criteria must not be empty.")
        return self


class InterviewQuestionOutput(BaseModel):
    """A single AI-proposed interview question (contract schema v1.2)."""

    model_config = ConfigDict(extra="forbid")

    category: QuestionCategory
    text: str = Field(min_length=1)
    topic: str | None = Field(default=None, max_length=250)
    requirement_key: str | None = None
    review_guide: InterviewQuestionReviewGuide

    @model_validator(mode="after")
    def _validate_requirement_key(self) -> InterviewQuestionOutput:
        if self.requirement_key is not None and not is_requirement_key(self.requirement_key):
            raise ValueError("requirement_key must match the system requirement key pattern.")
        return self


class InterviewQuestionSetOutput(BaseModel):
    """An AI-proposed set of interview questions (contract schema v1.2).

    ``questions`` is a flat, pre-ordered list; position is implied by list order.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = INTERVIEW_QUESTION_SCHEMA_VERSION
    questions: list[InterviewQuestionOutput] = Field(min_length=1)


def validate_interview_question_set(
    data: dict, *, allowed_keys: set[str], resume_text: str | None = None
) -> InterviewQuestionSetOutput:
    """Validate raw AI data into an InterviewQuestionSetOutput bound to allowed keys.

    In addition to Pydantic shape validation, every ``requirement_key`` returned
    by the producer must exist in ``allowed_keys`` — the exact requirement-key set
    supplied to the producer. Raises the shared application ``ValidationError`` on
    failure.
    """
    from app.ai.contracts.validation import _validate_contract
    from app.services.errors import ValidationError

    try:
        output = _validate_contract(InterviewQuestionSetOutput, data)
    except ValidationError as error:
        raise ValidationError(f"Invalid AI output contract: {error}") from error
    for question in output.questions:
        if question.requirement_key is not None and question.requirement_key not in allowed_keys:
            raise ValidationError(
                f"Interview question requirement_key {question.requirement_key!r} was not "
                "among the requirement keys supplied to the AI."
            )
        guide = question.review_guide
        if guide.evidence_basis == "verified_cv_evidence" and (
            not resume_text or not guide.source_quote or guide.source_quote not in resume_text
        ):
            raise ValidationError(
                "Interview question source_quote was not found verbatim in the extracted CV."
            )
    return output
