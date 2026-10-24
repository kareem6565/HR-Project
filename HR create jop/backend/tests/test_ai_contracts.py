"""Unit tests for the Phase 3.2 structured AI output contracts and validators.

Phase 4.1 extends the job profile contract to schema v1.1 structured job
requirements with system-generated keys, while keeping the v1.0 flat
requirement shape readable.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.ai.contracts import (
    EVIDENCE_CONTRACT_SCHEMA_VERSION,
    JOB_PROFILE_EXTRACTION_SCHEMA_VERSION,
    REQUIREMENT_CATEGORIES,
    REQUIREMENT_DIMENSIONS,
    CandidateProfileExtractionOutput,
    EvaluationExplanationOutput,
    JobProfileExtractionOutput,
    JobRequirement,
    MatchEvidenceListOutput,
    MatchEvidenceOutput,
    is_requirement_key,
    normalize_job_profile_requirements,
    requirement_key,
    validate_candidate_profile_extraction,
    validate_evaluation_explanation,
    validate_job_profile_extraction,
    validate_match_evidence_list,
    validate_interview_question_set,
)
from app.services.errors import ApplicationError, ValidationError


def _valid_interview_question_set(quote: str | None = None) -> dict:
    return {
        "schema_version": "1.2",
        "questions": [
            {
                "category": "technical",
                "text": "How did you use PostgreSQL?",
                "topic": "PostgreSQL",
                "requirement_key": requirement_key("PostgreSQL", "must_have"),
                "review_guide": {
                    "purpose": "Understand the candidate's practical PostgreSQL experience.",
                    "evidence_basis": "verified_cv_evidence" if quote else "job_requirement",
                    "source_quote": quote,
                    "interviewer_looks_for": "A concrete example and validation approach.",
                    "evaluation_rubric": ["Clear explanation", "Relevant example"],
                },
            }
        ],
    }


def test_interview_question_contract_requires_exact_quote_for_cv_claim() -> None:
    exact_quote = "Built PostgreSQL services handling 2M records."
    result = validate_interview_question_set(
        _valid_interview_question_set(exact_quote),
        allowed_keys={requirement_key("PostgreSQL", "must_have")},
        resume_text=f"Experience: {exact_quote}",
    )
    assert result.questions[0].review_guide.source_quote == exact_quote

    with pytest.raises(ValidationError, match="not found verbatim"):
        validate_interview_question_set(
            _valid_interview_question_set("Used PostgreSQL at scale."),
            allowed_keys={requirement_key("PostgreSQL", "must_have")},
            resume_text=f"Experience: {exact_quote}",
        )

    with pytest.raises(ValidationError):
        validate_interview_question_set(
            _valid_interview_question_set(exact_quote),
            allowed_keys={requirement_key("PostgreSQL", "must_have")},
            resume_text=None,
        )


def _valid_requirement() -> dict:
    return {"text": "Python", "category": "must_have", "dimension": "skill"}


def _valid_job_profile() -> dict:
    return {
        "title": "Backend Engineer",
        "requirements": [
            {"text": "Python", "category": "must_have", "dimension": "skill"},
            {"text": "PostgreSQL", "category": "important", "dimension": "skill"},
        ],
    }


def _valid_candidate_profile() -> dict:
    return {"full_name": "Ada Lovelace", "skills": ["Python", "SQL"]}


def _valid_match_evidence() -> dict:
    return {
        "evidence_type": "matched",
        "requirement_ref": {"requirement_key": requirement_key("Python", "must_have")},
        "candidate_evidence": {"text": "3 years Python"},
        "strength": "strong",
    }


def _valid_evidence_list() -> dict:
    return {
        "evidence_items": [
            {
                "evidence_type": "matched",
                "requirement_ref": {"requirement_key": requirement_key("Python", "must_have")},
                "candidate_evidence": {"text": "3 years Python"},
                "strength": "strong",
            },
            {
                "evidence_type": "missing",
                "requirement_ref": {"requirement_key": requirement_key("SQL", "must_have")},
            },
        ]
    }


def _valid_eval_explanation() -> dict:
    return {"summary": "Strong match on required skills."}


# --------------------------------------------------------------------------- #
# Valid contract construction
# --------------------------------------------------------------------------- #


def test_valid_job_profile_extraction_output() -> None:
    output = JobProfileExtractionOutput.model_validate(_valid_job_profile())
    assert output.title == "Backend Engineer"
    assert output.schema_version == JOB_PROFILE_EXTRACTION_SCHEMA_VERSION
    first, second = output.requirements
    assert isinstance(first, JobRequirement)
    assert first.text == "Python"
    assert first.category == "must_have"
    assert first.dimension == "skill"
    assert first.key == requirement_key("Python", "must_have")
    assert second.key == requirement_key("PostgreSQL", "important")


def test_valid_candidate_profile_extraction_output() -> None:
    output = CandidateProfileExtractionOutput.model_validate(_valid_candidate_profile())
    assert output.full_name == "Ada Lovelace"
    assert output.skills == ["Python", "SQL"]


def test_valid_match_evidence_output() -> None:
    output = MatchEvidenceOutput.model_validate(_valid_match_evidence())
    assert output.evidence_type == "matched"
    assert output.requirement_ref == {"requirement_key": requirement_key("Python", "must_have")}


def test_evidence_list_contract_defaults_to_v1_2() -> None:
    assert EVIDENCE_CONTRACT_SCHEMA_VERSION == "1.2"
    output = MatchEvidenceListOutput.model_validate(_valid_evidence_list())
    assert output.schema_version == "1.2"
    assert [item.evidence_type for item in output.evidence_items] == ["matched", "missing"]
    assert [item.requirement_ref["requirement_key"] for item in output.evidence_items] == [
        requirement_key("Python", "must_have"),
        requirement_key("SQL", "must_have"),
    ]
    assert any(item.strength is not None for item in output.evidence_items)


def test_is_requirement_key_matches_system_generated_pattern() -> None:
    assert is_requirement_key(requirement_key("Python", "must_have"))
    assert not is_requirement_key("req-not-a-hex-key")
    assert not is_requirement_key("req-abc")
    assert not is_requirement_key("req-0000000000000000000000")
    assert not is_requirement_key(123)
    assert not is_requirement_key(None)


@pytest.mark.parametrize(
    "requirement_ref",
    [
        {"requirement": "Python"},
        {"requirement_key": "not-a-valid-key"},
        {"requirement_key": "req-zzzzzzzzzzzzzzzz"},
        {"requirement_key": ""},
        {},
    ],
)
def test_evidence_requirement_ref_must_carry_valid_key(requirement_ref) -> None:
    with pytest.raises(PydanticValidationError):
        MatchEvidenceOutput.model_validate(
            {"evidence_type": "matched", "requirement_ref": requirement_ref}
        )


def test_evidence_requires_requirement_ref_in_v1_2() -> None:
    with pytest.raises(PydanticValidationError):
        MatchEvidenceListOutput.model_validate({"evidence_items": [{"evidence_type": "matched"}]})


def test_duplicate_evidence_requirement_keys_rejected() -> None:
    payload = {
        "evidence_items": [
            {
                "evidence_type": "matched",
                "requirement_ref": {"requirement_key": requirement_key("Python", "must_have")},
            },
            {
                "evidence_type": "partial",
                "requirement_ref": {"requirement_key": requirement_key("Python", "must_have")},
            },
        ]
    }
    with pytest.raises(PydanticValidationError, match="[Dd]uplicate"):
        MatchEvidenceListOutput.model_validate(payload)


def test_evidence_list_rejects_key_not_supplied_to_the_ai() -> None:
    with pytest.raises(ValidationError, match="not among the requirement keys"):
        validate_match_evidence_list(
            _valid_evidence_list(),
            allowed_keys={requirement_key("Python", "must_have")},
        )


def test_evidence_list_accepts_all_supplied_keys() -> None:
    allowed_keys = {
        requirement_key("Python", "must_have"),
        requirement_key("SQL", "must_have"),
    }
    output = validate_match_evidence_list(_valid_evidence_list(), allowed_keys=allowed_keys)
    returned_keys = {item.requirement_ref["requirement_key"] for item in output.evidence_items}
    assert returned_keys == allowed_keys


def test_valid_evaluation_explanation_output() -> None:
    output = EvaluationExplanationOutput.model_validate(_valid_eval_explanation())
    assert output.summary == "Strong match on required skills."


def test_requirement_category_and_dimension_enums_are_locked() -> None:
    assert REQUIREMENT_CATEGORIES == ("must_have", "important", "nice_to_have")
    assert REQUIREMENT_DIMENSIONS == ("skill", "experience", "education", "responsibility")


# --------------------------------------------------------------------------- #
# Requirement keys
# --------------------------------------------------------------------------- #


def test_requirement_key_is_deterministic_and_category_scoped() -> None:
    assert requirement_key("Python", "must_have") == requirement_key("  Python  ", "must_have")
    assert requirement_key("Python", "must_have") != requirement_key("Python", "important")
    assert requirement_key("Python", "must_have") != requirement_key("Python", "nice_to_have")


def test_flat_v1_requirements_normalized_with_defaults() -> None:
    output = JobProfileExtractionOutput.model_validate(
        {"title": "Engineer", "requirements": ["Python", "PostgreSQL"]}
    )
    assert [item.text for item in output.requirements] == ["Python", "PostgreSQL"]
    assert [item.category for item in output.requirements] == ["important", "important"]
    assert [item.dimension for item in output.requirements] == ["skill", "skill"]
    assert [item.key for item in output.requirements] == [
        requirement_key("Python", "important"),
        requirement_key("PostgreSQL", "important"),
    ]


def test_flat_requirement_text_is_whitespace_normalized() -> None:
    output = JobProfileExtractionOutput.model_validate(
        {"title": "Engineer", "requirements": ["  Python  \t SQL "]}
    )
    assert output.requirements[0].text == "Python SQL"


@pytest.mark.parametrize(
    "requirement",
    [
        {"key": "req-tampered", "text": "Python", "category": "must_have", "dimension": "skill"},
        {"text": "Python", "category": "must_have", "dimension": "skill", "key": ""},
    ],
)
def test_llm_supplied_requirement_key_is_never_trusted(requirement) -> None:
    output = JobProfileExtractionOutput.model_validate(
        {"title": "Engineer", "requirements": [requirement]}
    )
    assert output.requirements[0].key == requirement_key("Python", "must_have")


# --------------------------------------------------------------------------- #
# Job requirement validation failures
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "requirements",
    [
        ["Python", {"text": "SQL", "category": "must_have", "dimension": "skill"}],
        [{"text": "SQL", "category": "must_have", "dimension": "skill"}, "Python"],
    ],
)
def test_mixed_requirement_shapes_rejected(requirements) -> None:
    with pytest.raises(PydanticValidationError, match="mix"):
        JobProfileExtractionOutput.model_validate({"title": "X", "requirements": requirements})


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": "critical"},
        {"dimension": "location"},
    ],
)
def test_invalid_requirement_category_or_dimension_rejected(overrides) -> None:
    payload = {**_valid_requirement(), **overrides}
    with pytest.raises(PydanticValidationError):
        JobProfileExtractionOutput.model_validate({"title": "X", "requirements": [payload]})


@pytest.mark.parametrize("text", ["", "   ", "\t  \n"])
def test_blank_requirement_text_rejected(text) -> None:
    payload = {**_valid_requirement(), "text": text}
    with pytest.raises(PydanticValidationError):
        JobProfileExtractionOutput.model_validate({"title": "X", "requirements": [payload]})


def test_requirement_extra_field_rejected() -> None:
    payload = {**_valid_requirement(), "score": 9}
    with pytest.raises(PydanticValidationError):
        JobProfileExtractionOutput.model_validate({"title": "X", "requirements": [payload]})


@pytest.mark.parametrize(
    "first,second",
    [
        (
            {"text": "Python", "category": "must_have", "dimension": "skill"},
            {"text": "Python", "category": "must_have", "dimension": "skill"},
        ),
        (
            {"text": "Python", "category": "must_have", "dimension": "skill"},
            {"text": "  Python ", "category": "must_have", "dimension": "education"},
        ),
    ],
)
def test_duplicate_requirement_keys_rejected(first, second) -> None:
    with pytest.raises(PydanticValidationError, match="[Dd]uplicate"):
        JobProfileExtractionOutput.model_validate({"title": "X", "requirements": [first, second]})


def test_same_text_in_different_categories_allowed() -> None:
    output = JobProfileExtractionOutput.model_validate(
        {
            "title": "X",
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
                {"text": "Python", "category": "nice_to_have", "dimension": "skill"},
            ],
        }
    )
    assert {item.category for item in output.requirements} == {"must_have", "nice_to_have"}
    assert len({item.key for item in output.requirements}) == 2


def test_legacy_v1_schema_version_still_accepted() -> None:
    output = JobProfileExtractionOutput.model_validate(
        {"title": "X", "schema_version": "1.0", "requirements": ["Python"]}
    )
    assert output.schema_version == "1.0"
    assert output.requirements[0].key == requirement_key("Python", "important")


# --------------------------------------------------------------------------- #
# Missing required fields
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "contract_type,data",
    [
        (JobProfileExtractionOutput, {"summary": "no title"}),
        (CandidateProfileExtractionOutput, {"skills": []}),
        (MatchEvidenceOutput, {"strength": "strong"}),
        (MatchEvidenceListOutput, {}),
        (EvaluationExplanationOutput, {"points": []}),
    ],
)
def test_missing_required_field_rejected(contract_type, data) -> None:
    with pytest.raises(PydanticValidationError):
        contract_type.model_validate(data)


# --------------------------------------------------------------------------- #
# Wrong field types
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "contract_type,data",
    [
        (JobProfileExtractionOutput, {"title": 123}),
        (JobProfileExtractionOutput, {"title": "x", "requirements": [42]}),
        (CandidateProfileExtractionOutput, {"full_name": 123}),
        (CandidateProfileExtractionOutput, {"full_name": "x", "skills": [1]}),
        (MatchEvidenceOutput, {"evidence_type": "upgraded", "strength": 5}),
        (EvaluationExplanationOutput, {"summary": 123}),
        (EvaluationExplanationOutput, {"summary": "x", "points": [1]}),
    ],
)
def test_wrong_field_type_rejected(contract_type, data) -> None:
    with pytest.raises(PydanticValidationError):
        contract_type.model_validate(data)


# --------------------------------------------------------------------------- #
# Invalid contract values (domain-level)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "contract_type,data",
    [
        (JobProfileExtractionOutput, {"title": ""}),
        (CandidateProfileExtractionOutput, {"full_name": ""}),
        (MatchEvidenceOutput, {"evidence_type": "other"}),
        (EvaluationExplanationOutput, {"summary": ""}),
    ],
)
def test_invalid_contract_rejected(contract_type, data) -> None:
    with pytest.raises(PydanticValidationError):
        contract_type.model_validate(data)


# --------------------------------------------------------------------------- #
# Optional fields / default behavior
# --------------------------------------------------------------------------- #


def test_optional_fields_default_when_omitted() -> None:
    job = JobProfileExtractionOutput.model_validate({"title": "Engineer"})
    assert job.summary is None
    assert job.requirements == []

    candidate = CandidateProfileExtractionOutput.model_validate({"full_name": "Ada"})
    assert candidate.summary is None
    assert candidate.skills == []
    assert candidate.experience == []

    evidence = MatchEvidenceOutput.model_validate(
        {
            "evidence_type": "missing",
            "requirement_ref": {"requirement_key": requirement_key("SQL", "must_have")},
        }
    )
    assert evidence.candidate_evidence is None
    assert evidence.strength is None
    assert evidence.provenance is None

    explanation = EvaluationExplanationOutput.model_validate({"summary": "ok"})
    assert explanation.points == []


def test_list_defaults_are_not_mutated_across_instances() -> None:
    first = JobProfileExtractionOutput.model_validate({"title": "Engineer"})
    first.requirements.append("Extra")
    second = JobProfileExtractionOutput.model_validate({"title": "Engineer"})
    assert second.requirements == []

    skill_first = CandidateProfileExtractionOutput.model_validate({"full_name": "Ada"})
    skill_first.skills.append("Python")
    skill_second = CandidateProfileExtractionOutput.model_validate({"full_name": "Ada"})
    assert skill_second.skills == []


def test_extra_fields_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        JobProfileExtractionOutput.model_validate({"title": "X", "score": 90})


# --------------------------------------------------------------------------- #
# schema_version validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "contract_type,data",
    [
        (JobProfileExtractionOutput, {"title": "X", "schema_version": "0.9"}),
        (CandidateProfileExtractionOutput, {"full_name": "A", "schema_version": "0.9"}),
        (MatchEvidenceOutput, {"evidence_type": "matched", "schema_version": "0.9"}),
        (EvaluationExplanationOutput, {"summary": "x", "schema_version": "0.9"}),
        (JobProfileExtractionOutput, {"title": "X", "schema_version": "not-a-version"}),
        (JobProfileExtractionOutput, {"title": "X", "schema_version": ""}),
        (JobProfileExtractionOutput, {"title": "X", "schema_version": 5}),
    ],
)
def test_invalid_schema_version_rejected(contract_type, data) -> None:
    with pytest.raises(PydanticValidationError):
        contract_type.model_validate(data)


@pytest.mark.parametrize("version", ["1.0", "1.1", "1.2"])
def test_supported_schema_version_accepted(version) -> None:
    output = JobProfileExtractionOutput.model_validate({"title": "X", "schema_version": version})
    assert output.schema_version == version


@pytest.mark.parametrize(
    "version",
    [
        "1.1",
        "v1.1",
        "V1.1",
        " v1.1 ",
        "1.2",
        "v1.2",
        "V1.2",
        " v1.2 ",
        "1.0",
        "v1.0",
    ],
)
def test_schema_version_normalized_to_canonical(version) -> None:
    expected = version.strip().lstrip("vV") or "1.1"
    output = JobProfileExtractionOutput.model_validate({"title": "X", "schema_version": version})
    assert output.schema_version == expected


@pytest.mark.parametrize("version", ["1.2", "v1.2", "V1.2", " v1.2 "])
def test_evidence_schema_version_normalized_to_canonical(version) -> None:
    output = MatchEvidenceOutput.model_validate(
        {**_valid_match_evidence(), "schema_version": version}
    )
    assert output.schema_version == "1.2"

    list_output = MatchEvidenceListOutput.model_validate(
        {**_valid_evidence_list(), "schema_version": version}
    )
    assert list_output.schema_version == "1.2"


# --------------------------------------------------------------------------- #
# Read-path normalization helper
# --------------------------------------------------------------------------- #


def test_normalize_legacy_missing_or_empty_requirements() -> None:
    assert normalize_job_profile_requirements(None) == []
    assert normalize_job_profile_requirements([]) == []


def test_normalize_flat_requirements_applies_read_defaults() -> None:
    normalized = normalize_job_profile_requirements(["Python", "Machine Learning"])
    assert len(normalized) == 2
    assert normalized[0].text == "Python"
    assert normalized[0].category == "important"
    assert normalized[0].dimension == "skill"
    assert normalized[0].key == requirement_key("Python", "important")


def test_normalize_structured_requirements_recomputes_system_key() -> None:
    normalized = normalize_job_profile_requirements(
        [
            {
                "key": "req-tampered",
                "text": "Python",
                "category": "must_have",
                "dimension": "skill",
            }
        ]
    )
    assert normalized[0].key == requirement_key("Python", "must_have")


def test_normalize_invalid_requirements_raise_application_error() -> None:
    with pytest.raises(ValidationError, match="must be a list"):
        normalize_job_profile_requirements("Python")
    with pytest.raises(ValidationError, match="mix"):
        normalize_job_profile_requirements(
            ["Python", {"text": "SQL", "category": "must_have", "dimension": "skill"}]
        )
    with pytest.raises(ValidationError, match="unsupported"):
        normalize_job_profile_requirements([42])
    with pytest.raises(ValidationError, match="[Dd]uplicate"):
        normalize_job_profile_requirements(
            [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
                {"text": "Python", "category": "must_have", "dimension": "education"},
            ]
        )
    with pytest.raises(ValidationError, match="Invalid persisted"):
        normalize_job_profile_requirements([{"text": "Python", "category": "invalid"}])


# --------------------------------------------------------------------------- #
# Validation helpers (raise the Phase 3.1 application ValidationError)
# --------------------------------------------------------------------------- #


def test_validators_return_validated_contracts() -> None:
    job = validate_job_profile_extraction(_valid_job_profile())
    assert isinstance(job, JobProfileExtractionOutput)

    candidate = validate_candidate_profile_extraction(_valid_candidate_profile())
    assert isinstance(candidate, CandidateProfileExtractionOutput)

    allowed_keys = {
        requirement_key("Python", "must_have"),
        requirement_key("SQL", "must_have"),
    }
    evidence_list = validate_match_evidence_list(_valid_evidence_list(), allowed_keys=allowed_keys)
    assert isinstance(evidence_list, MatchEvidenceListOutput)
    returned_keys = {
        item.requirement_ref["requirement_key"] for item in evidence_list.evidence_items
    }
    assert returned_keys == allowed_keys

    explanation = validate_evaluation_explanation(_valid_eval_explanation())
    assert isinstance(explanation, EvaluationExplanationOutput)


@pytest.mark.parametrize(
    "validator,data",
    [
        (validate_job_profile_extraction, {"summary": "missing title"}),
        (validate_candidate_profile_extraction, {"skills": []}),
        (
            validate_match_evidence_list,
            {
                "evidence_items": [
                    {
                        "evidence_type": "matched",
                        "requirement_ref": {"requirement_key": "bad-key"},
                    }
                ]
            },
        ),
        (validate_evaluation_explanation, {"points": []}),
        (validate_job_profile_extraction, {"title": "X", "schema_version": "0.9"}),
        (
            validate_job_profile_extraction,
            {
                "title": "X",
                "requirements": [
                    {"text": "Python", "category": "must_have", "dimension": "skill"},
                    {"text": "Python", "category": "must_have", "dimension": "skill"},
                ],
            },
        ),
    ],
)
def test_validators_raise_application_validation_error(validator, data) -> None:
    with pytest.raises(ValidationError) as excinfo:
        if validator is validate_match_evidence_list:
            validator(data, **{"allowed_keys": set()})
        else:
            validator(data)
    assert isinstance(excinfo.value, ApplicationError)
    assert not isinstance(excinfo.value, PydanticValidationError)


def test_validator_validation_error_is_not_a_raw_pydantic_error() -> None:
    try:
        validate_job_profile_extraction({"summary": "missing title"})
    except ValidationError:
        pass
    else:
        raise AssertionError("expected ApplicationError to be raised")
