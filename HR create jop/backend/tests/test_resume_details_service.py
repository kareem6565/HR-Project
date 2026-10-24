"""Unit tests for the deterministic resume-derived screening details."""

from __future__ import annotations

import pytest

from app.ai.contracts import (
    CandidateProfileExtractionOutput,
    MatchEvidenceListOutput,
    validate_evaluation_explanation,
)
from app.services.resume_details_service import (
    build_skills,
    derive_evidence_payload,
    derive_explanation_payload,
    derive_profile_payload,
    derive_screening_payloads,
    extract_certifications,
    extract_education,
    extract_email,
    extract_github_url,
    extract_languages,
    extract_linkedin_url,
    extract_location,
    extract_phone,
    extract_portfolio_url,
)

RICH_RESUME = """
Ada Lovelace
London, United Kingdom
ada.lovelace@example.com
+44 20 7946 0958
linkedin.com/in/ada-lovelace
github.com/adalovelace
portfolio: ada.dev/engineering

EXPERIENCE
Data Analyst, 2018 - 2021
Senior Data Engineer, 2021 - present

EDUCATION
BSc Computer Science
MSc Data Science

CERTIFICATIONS
AWS Certified Solutions Architect
Professional Scrum Master I

SKILLS
Python, TypeScript, React, Postgres, Docker, Kubernetes, Machine Learning

Languages: English (native), French (conversational)
"""

REQUIREMENTS = [
    {
        "text": "Strong Python programming skills over several years",
        "category": "must_have",
        "dimension": "skill",
    },
    {
        "text": "Cloud infrastructure experience with AWS",
        "category": "must_have",
        "dimension": "skill",
    },
    {
        "text": "Experience with German legal compliance",
        "category": "important",
        "dimension": "skill",
    },
]


class TestContactExtraction:
    def test_email(self) -> None:
        assert extract_email(RICH_RESUME) == "ada.lovelace@example.com"

    def test_phone_keeps_country_code(self) -> None:
        assert extract_phone(RICH_RESUME) == "+44 20 7946 0958"

    def test_phone_rejects_year_range(self) -> None:
        assert extract_phone("Joined 2018 - 2021, still active") is None

    def test_linkedin_url_adds_scheme(self) -> None:
        assert extract_linkedin_url(RICH_RESUME) == "https://linkedin.com/in/ada-lovelace"

    def test_github_url(self) -> None:
        assert extract_github_url(RICH_RESUME) == "https://github.com/adalovelace"

    def test_portfolio_url(self) -> None:
        assert extract_portfolio_url(RICH_RESUME) == "https://ada.dev/engineering"

    def test_location(self) -> None:
        assert extract_location(RICH_RESUME) == "London, United Kingdom"


class TestStructuredExtraction:
    def test_skills_are_found(self) -> None:
        skills = build_skills(RICH_RESUME)
        assert "python" in skills
        assert "machine learning" in skills
        assert "kubernetes" in skills

    def test_languages(self) -> None:
        assert extract_languages(RICH_RESUME) == ["English", "French"]

    def test_education_skips_scrum_master(self) -> None:
        education = extract_education(RICH_RESUME)
        assert "BSc Computer Science" in education
        assert "MSc Data Science" in education
        assert not any("Scrum Master" in item for item in education)

    def test_education_skips_ms_office(self) -> None:
        assert extract_education("MS Office power user for reporting") == []

    def test_certifications(self) -> None:
        certifications = extract_certifications(RICH_RESUME)
        assert any("Solutions Architect" in item for item in certifications)
        assert "Professional Scrum Master I" in certifications

    def test_certification_headings_and_neighboring_sections_are_not_credentials(self) -> None:
        resume = """
        PROFESSIONAL SUMMARY
        Experienced product manager
        PROFESSIONAL EXPERIENCE
        Senior Product Manager, 2018 - 2022
        CERTIFICATIONS
        AWS Certified Solutions Architect
        EDUCATION
        Professional Certificate in Product Design
        """
        assert extract_certifications(resume) == ["AWS Certified Solutions Architect"]

    def test_empty_certification_section_stays_empty(self) -> None:
        assert extract_certifications("CERTIFICATIONS\n\nPROFESSIONAL EXPERIENCE\nEngineer") == []

    def test_certification_keyword_without_explicit_section_is_supported(self) -> None:
        assert extract_certifications("Licensed Clinical Social Worker") == [
            "Licensed Clinical Social Worker"
        ]


class TestContractPayloads:
    def test_profile_payload_valid_and_grounded(self) -> None:
        payload = derive_profile_payload(full_name="Ada Lovelace", resume_text=RICH_RESUME)
        contract = CandidateProfileExtractionOutput.model_validate(payload)
        assert contract.email == "ada.lovelace@example.com"
        assert contract.phone == "+44 20 7946 0958"
        assert contract.linkedin_url == "https://linkedin.com/in/ada-lovelace"
        assert "python" in contract.skills
        assert len(contract.education) >= 2
        assert contract.experience  # employment lines present

    def test_profile_payload_without_text_is_empty_not_fabricated(self) -> None:
        payload = derive_profile_payload(full_name="Ada", resume_text=None)
        contract = CandidateProfileExtractionOutput.model_validate(payload)
        assert contract.skills == []
        assert contract.experience == []
        assert contract.email is None
        assert contract.phone is None
        assert contract.location is None

    def test_evidence_payload_covers_every_requirement(self) -> None:
        from app.ai.contracts import normalize_job_profile_requirements

        payload = derive_evidence_payload(resume_text=RICH_RESUME, requirements=REQUIREMENTS)
        contract = MatchEvidenceListOutput.model_validate(payload)
        keys = {item.requirement_ref["requirement_key"] for item in contract.evidence_items}
        expected = {req.key for req in normalize_job_profile_requirements(REQUIREMENTS)}
        assert keys == expected
        by_type = {item.evidence_type for item in contract.evidence_items}
        assert "matched" in by_type
        assert "partial" in by_type

    def test_evidence_aws_requirement_matches(self) -> None:
        payload = derive_evidence_payload(resume_text=RICH_RESUME, requirements=REQUIREMENTS)
        items = payload["evidence_items"]
        aws = next(item for item in items if item["evidence_type"] == "matched")
        assert aws["strength"] == "strong"
        assert "aws" in aws["candidate_evidence"]["matched_terms"]

    def test_evidence_missing_requirement_is_empty_grounded(self) -> None:
        payload = derive_evidence_payload(
            resume_text=RICH_RESUME,
            requirements=[
                {
                    "text": "Expertise in actuarial risk modeling",
                    "category": "must_have",
                    "dimension": "skill",
                }
            ],
        )
        items = payload["evidence_items"]
        assert len(items) == 1 and items[0]["evidence_type"] == "missing"
        assert items[0]["candidate_evidence"]["evidence_text"] == ""
        assert items[0]["strength"] == "none"

    def test_evidence_empty_requirements(self) -> None:
        payload = derive_evidence_payload(resume_text=RICH_RESUME, requirements=[])
        assert payload["evidence_items"] == []

    def test_explanation_payload_is_valid_and_tallies(self) -> None:
        evidence = derive_evidence_payload(resume_text=RICH_RESUME, requirements=REQUIREMENTS)
        payload = derive_explanation_payload(
            job_title="Senior Data Engineer",
            requirements=REQUIREMENTS,
            evidence_payload=evidence,
        )
        contract = validate_evaluation_explanation(payload)
        assert "Senior Data Engineer" in contract.summary
        assert len(contract.points) == len(REQUIREMENTS)
        assert any("Strong match" in point for point in contract.points)

    def test_screening_payloads_together(self) -> None:
        profile, evidence, explanation = derive_screening_payloads(
            full_name="Ada Lovelace",
            job_title="Senior Data Engineer",
            resume_text=RICH_RESUME,
            requirements=REQUIREMENTS,
        )
        assert profile["email"] == "ada.lovelace@example.com"
        assert evidence["evidence_items"]
        assert explanation["summary"]

    def test_screening_payloads_accept_job_requirement_instances(self) -> None:
        from app.ai.contracts.job_profile import JobRequirement

        requirements = [JobRequirement.model_validate(item) for item in REQUIREMENTS]
        profile, evidence, _ = derive_screening_payloads(
            full_name="Ada Lovelace",
            job_title="Senior Data Engineer",
            resume_text=RICH_RESUME,
            requirements=requirements,
        )
        assert profile["email"]
        assert len(evidence["evidence_items"]) == len(requirements)

    def test_empty_resume_text_yields_zero_score_material(self) -> None:
        profile, evidence, explanation = derive_screening_payloads(
            full_name="Ada",
            job_title="Analyst",
            resume_text=None,
            requirements=REQUIREMENTS,
        )
        assert not profile["skills"]
        assert all(item["evidence_type"] == "missing" for item in evidence["evidence_items"])
        assert "0 matched, 0 partial, 3 missing" in explanation["summary"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Call +1 (415) 555-0132 today", "+1 (415) 555-0132"),
        ("Mobile 971 50 123 4567", "971 50 123 4567"),
    ],
)
def test_phone_formats(text: str, expected: str) -> None:
    assert extract_phone(text) == expected
