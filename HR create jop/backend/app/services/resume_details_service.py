"""Deterministic resume-derived details for screening (MVP enrichment).

Rule-based, reproducible extraction that runs directly on the uploaded CV text.
It emits the same validated contract payloads the Soal provider produces, so
screening always returns a real score, per-requirement evidence, an explanation,
and contact/skill details derived from the *actual* resume — never fabricated or
placeholder values.

All helpers are pure and deterministic: the same resume text always yields the
same payloads, which keeps them unit-testable and safe to call from the
workflow routes. Nothing here calls an external provider and nothing here makes
a decision; the HR decision is always recorded separately through the review
endpoints.
"""

from __future__ import annotations

import re
from typing import Any

from app.ai.contracts import (
    MatchEvidenceListOutput,
    normalize_job_profile_requirements,
    validate_candidate_profile_extraction,
    validate_evaluation_explanation,
    validate_match_evidence_list,
)
from app.services.evidence_verification_service import EvidenceVerificationService
from app.services.text_normalization import (
    ARABIC_STOPWORDS,
    extract_verbatim_quote,
    has_term_match,
    normalize_for_matching,
    tokenize_words,
)

# ---------------------------------------------------------------------------
# Contact / link / structured detail extraction
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,17}\d")

_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|profile)/[\w-]+")
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w-]+")
_PORTFOLIO_RE = re.compile(r"(?:https?://)?(?:www\.)?[\w-]+\.(?:(?:dev|io|me|site|pro))/[\w./-]*")

_DEGREE_RE = re.compile(
    r"\b(?:BSc|B\.Sc|BA|B\.A|MBA|MSc|M\.Sc|MS|M\.S|MA|M\.A|PhD|Ph\.D|MD|BEng|MEng|"
    r"BS|GED|HND|Diploma|Bachelor|Master|Doctorate|Doctor)\b[^.\n]{0,80}",
    re.IGNORECASE,
)

# A degree keyword is only treated as a degree marker when it follows a line
# boundary (empty previous token) or a connector like "of"/"in" — otherwise
# "Scrum Master" or "Product Master" would be misread as an education entry.
_DEGREE_CONNECTORS: frozenset[str] = frozenset({"", "in", "of", "honors", "honours", "with"})

# Abbreviated degrees are ambiguous ("MS Office", "BA team"), so they must be
# followed by an academic field-of-study word within a short window.
_ABBR_DEGREES: frozenset[str] = frozenset({"BS", "MS", "MA", "BA", "MD", "BE", "ME"})
_ABBR_DEGREE_FIELDS = re.compile(
    r"\b(?:Science|Engineering|Arts|Administration|Business|Computer|Data|Management|"
    r"Mathematics|Statistics|Analytics|Finance|Economics|Information|Human|Law|Design|"
    r"Marketing|Education|Studies|Architecture|Commerce|Civil|Mechanical|Electrical|"
    r"Chemistry|Physics|Biology|Nursing|Social|Psychology|Cybersecurity|Leadership)\b",
    re.IGNORECASE,
)

_CERT_RE = re.compile(
    r"\b(?:certified|certification|certificate|licensed|professional)\b[^.\n]{0,100}",
    re.IGNORECASE,
)

_RESUME_SECTION_RE = re.compile(
    r"^(?:professional\s+)?(?:summary|profile|experience|employment|work\s+history|"
    r"education|academic\s+background|certifications?(?:\s+(?:and|&)\s+licenses?)?|"
    r"licenses?(?:\s+(?:and|&)\s+certifications?)?|skills|languages|"
    r"projects|publications|references|awards|volunteer(?:\s+experience)?)\s*:?$",
    re.IGNORECASE,
)
_CERT_SECTION_RE = re.compile(
    r"^(?:certifications?(?:\s+(?:and|&)\s+licenses?)?|"
    r"licenses?(?:\s+(?:and|&)\s+certifications?)?)\s*:?$",
    re.I,
)

_YEAR_RANGE_RE = re.compile(
    r"\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|now)\b",
    re.IGNORECASE,
)

_KNOWN_COUNTRIES: frozenset[str] = frozenset(
    {
        "algeria",
        "australia",
        "austria",
        "bahrain",
        "belgium",
        "brazil",
        "britain",
        "canada",
        "china",
        "denmark",
        "egypt",
        "finland",
        "france",
        "germany",
        "greece",
        "ireland",
        "india",
        "iraq",
        "israel",
        "italy",
        "japan",
        "jordan",
        "kuwait",
        "lebanon",
        "libya",
        "morocco",
        "netherlands",
        "norway",
        "oman",
        "pakistan",
        "palestine",
        "poland",
        "portugal",
        "qatar",
        "romania",
        "saudi arabia",
        "singapore",
        "spain",
        "sudan",
        "sweden",
        "switzerland",
        "syria",
        "tunisia",
        "turkey",
        "uae",
        "ukraine",
        "united arab emirates",
        "united kingdom",
        "united states",
        "usa",
        "yemen",
    }
)

# Iterated in declaration order so language extraction output stays stable.
_KNOWN_LANGUAGES: tuple[str, ...] = (
    "english",
    "arabic",
    "french",
    "german",
    "spanish",
    "italian",
    "portuguese",
    "russian",
    "chinese",
    "mandarin",
    "japanese",
    "korean",
    "dutch",
    "hindi",
    "urdu",
    "turkish",
    "greek",
    "hebrew",
    "polish",
    "persian",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
)

# Skill dictionary, roughly most-relevant-first. Multi-word entries are matched
# as literal phrases; single words are matched on word boundaries.
_SKILLS: tuple[str, ...] = (
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "large language models",
    "nlp",
    "natural language processing",
    "computer vision",
    "data engineering",
    "data science",
    "data analysis",
    "statistical modeling",
    "python",
    "go",
    "golang",
    "java",
    "typescript",
    "javascript",
    "react",
    "next.js",
    "vue",
    "angular",
    "node.js",
    "nodejs",
    "express",
    "django",
    "flask",
    "fastapi",
    "spring",
    "spring boot",
    "c#",
    ".net",
    "ruby",
    "php",
    "sql",
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "kafka",
    "rabbitmq",
    "docker",
    "kubernetes",
    "k8s",
    "terraform",
    "aws",
    "azure",
    "gcp",
    "google cloud",
    "git",
    "github",
    "ci/cd",
    "jenkins",
    "graphql",
    "rest api",
    "microservices",
    "system design",
    "cloud architecture",
    "linux",
    "bash",
    "bash scripting",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "keras",
    "hugging face",
    "langchain",
    "power bi",
    "tableau",
    "excel",
    "google analytics",
    "seo",
    "salesforce",
    "sap",
    "erp",
    "project management",
    "agile",
    "scrum",
    "kanban",
    "jira",
    "product management",
    "product strategy",
    "roadmap",
    "ux",
    "ui design",
    "figma",
    "adobe xd",
    "prototyping",
    "usability testing",
    "leadership",
    "team leadership",
    "stakeholder management",
    "communication",
    "presentation skills",
    "cross-functional collaboration",
    "mentoring",
    "problem solving",
    "analytical skills",
    "critical thinking",
    "risk management",
    "budget management",
    "negotiation",
    "b2b",
    "b2c",
    "sales strategy",
    "customer relationship management",
    "content strategy",
    "digital marketing",
    "hr",
    "recruitment",
    "talent acquisition",
    "onboarding",
    "compliance",
    "security",
    "cybersecurity",
    "network security",
    "iso 27001",
    "gdpr",
    "qa",
    "automation testing",
    "unit testing",
    "pytest",
    "jest",
    "ci",
)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "have",
        "has",
        "had",
        "this",
        "that",
        "your",
        "you",
        "our",
        "will",
        "would",
        "should",
        "can",
        "could",
        "all",
        "any",
        "are",
        "was",
        "were",
        "been",
        "not",
        "but",
        "also",
        "into",
        "over",
        "under",
        "above",
        "below",
        "during",
        "within",
        "about",
        "after",
        "before",
        "between",
        "through",
        "each",
        "every",
        "their",
        "there",
        "they",
        "them",
        "which",
        "where",
        "while",
        "who",
        "whom",
        "its",
        "itself",
        "etc",
        "ie",
        "eg",
        "via",
        "per",
        "across",
        "along",
        "upon",
        "such",
        "than",
        "then",
        "these",
        "those",
        "some",
        "more",
        "most",
        "other",
        "how",
        "when",
        "what",
        "why",
    }
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*")


def _normalize(text: str | None) -> str:
    return (text or "").lower()


def _has_phrase(norm: str, phrase: str) -> bool:
    if " " in phrase or "/" in phrase or "+" in phrase or "#" in phrase:
        return phrase in norm
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", norm) is not None


def extract_email(text: str | None) -> str | None:
    """Return the first plausible e-mail address found in the resume text."""
    norm = _normalize(text)
    match = _EMAIL_RE.search(norm)
    return match.group(0) if match else None


def extract_phone(text: str | None) -> str | None:
    """Return the first plausible phone number, filtering date/year false hits."""
    norm = _normalize(text)
    for match in _PHONE_RE.finditer(norm):
        candidate = match.group(0).strip()
        digits = "".join(char for char in candidate if char.isdigit())
        if not 7 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"\d{4}\s*[-–]\s*\d{4}", candidate):
            continue  # a year range like 2018 - 2021
        return candidate
    return None


def extract_linkedin_url(text: str | None) -> str | None:
    match = _LINKEDIN_RE.search(_normalize(text))
    if not match:
        return None
    return _ensure_scheme(match.group(0))


def extract_github_url(text: str | None) -> str | None:
    match = _GITHUB_RE.search(_normalize(text))
    if not match:
        return None
    return _ensure_scheme(match.group(0))


def extract_portfolio_url(text: str | None) -> str | None:
    """Best-effort portfolio URL. Prefers dev/me/site hosts outside the big link sites."""
    norm = _normalize(text)
    for match in _PORTFOLIO_RE.finditer(norm):
        url = match.group(0)
        if "linkedin.com" in url or "github.com" in url or "example.com" in url:
            continue
        return _ensure_scheme(url)
    return None


def _ensure_scheme(url: str) -> str:
    return url if url.startswith("http://") or url.startswith("https://") else f"https://{url}"


def extract_location(text: str | None) -> str | None:
    """Return a ``City, Country``-style location line when the resume states one."""
    lines = (text or "").splitlines()
    for line in lines:
        candidate = line.strip()
        parts = [part.strip() for part in candidate.split(",")]
        if len(parts) < 2:
            continue
        tail = parts[-1].lower()
        if tail in _KNOWN_COUNTRIES and len(candidate) < 80:
            return candidate
    return None


def extract_languages(text: str | None) -> list[str]:
    norm = _normalize(text)
    return [language.title() for language in _KNOWN_LANGUAGES if _has_phrase(norm, language)]


def extract_education(text: str | None) -> list[str]:
    """Return unique degree-annotated lines (up to 8), skipping non-degree titles."""
    results: list[str] = []
    source = text or ""
    for match in _DEGREE_RE.finditer(source):
        before = source[: match.start()].rsplit("\n", 1)[-1].strip().split()
        previous = before[-1].lower() if before else ""
        if previous not in _DEGREE_CONNECTORS:
            continue
        keyword = match.group(0)
        abbreviation = keyword.split()[0].replace(".", "")
        if abbreviation in _ABBR_DEGREES:
            suffix = keyword[len(keyword.split()[0]) : len(keyword.split()[0]) + 34]
            if not _ABBR_DEGREE_FIELDS.search(suffix):
                continue
        line = " ".join(keyword.split())
        if not line:
            continue
        if line not in results:
            results.append(line)
        if len(results) >= 8:
            break
    return results


def extract_certifications(text: str | None) -> list[str]:
    """Extract certification lines without treating unrelated section headings as credentials."""
    results: list[str] = []
    lines = (text or "").splitlines()
    has_cert_section = any(_CERT_SECTION_RE.fullmatch(" ".join(line.split())) for line in lines)
    in_cert_section = False
    for raw_line in lines:
        line = " ".join(raw_line.split())
        if not line:
            continue
        if _RESUME_SECTION_RE.fullmatch(line):
            in_cert_section = bool(_CERT_SECTION_RE.fullmatch(line))
            continue
        if has_cert_section:
            if not in_cert_section:
                continue
            candidate = line
        else:
            if _RESUME_SECTION_RE.fullmatch(line) or not _CERT_RE.search(line):
                continue
            candidate = line
        if candidate not in results:
            results.append(candidate)
        if len(results) >= 8:
            break
    return results


def extract_experience(text: str | None) -> list[str]:
    """Return resume lines containing employment year ranges (up to 6)."""
    results: list[str] = []
    for line in (text or "").splitlines():
        candidate = " ".join(line.split())
        if not candidate or len(candidate) > 160:
            continue
        if not _YEAR_RANGE_RE.search(candidate):
            continue
        if candidate in results:
            continue
        results.append(candidate)
        if len(results) >= 6:
            break
    return results


def build_skills(text: str | None) -> list[str]:
    """Return the skills found in the resume text, in dictionary relevance order."""
    norm = normalize_for_matching(text)
    return [
        skill
        for skill in _SKILLS
        if has_term_match(norm, skill) or _has_phrase(norm, skill)
    ]


# ---------------------------------------------------------------------------
# Contract payload builders
# ---------------------------------------------------------------------------


def _as_raw_requirements(requirements: Any) -> Any:
    """Convert canonical ``JobRequirement`` instances back to raw dicts."""
    from app.ai.contracts.job_profile import JobRequirement

    if (
        isinstance(requirements, list)
        and requirements
        and all(isinstance(item, JobRequirement) for item in requirements)
    ):
        return [item.model_dump() for item in requirements]
    return requirements


def derive_profile_payload(*, full_name: str, resume_text: str | None) -> dict[str, Any]:
    """Build a validated candidate-profile payload grounded in the resume text."""
    skills = build_skills(resume_text)
    experience = extract_experience(resume_text)
    summary = "Profile extracted from the uploaded CV."
    if experience:
        summary = "Profile extracted from the uploaded CV — employment history identified."
    return validate_candidate_profile_extraction(
        {
            "full_name": full_name,
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "email": extract_email(resume_text),
            "phone": extract_phone(resume_text),
            "location": extract_location(resume_text),
            "linkedin_url": extract_linkedin_url(resume_text),
            "github_url": extract_github_url(resume_text),
            "portfolio_url": extract_portfolio_url(resume_text),
            "education": extract_education(resume_text),
            "languages": extract_languages(resume_text),
            "certifications": extract_certifications(resume_text),
        }
    ).model_dump()


def _total_experience_years(text: str | None) -> int | None:
    spans: list[tuple[int, int]] = []
    for match in _YEAR_RANGE_RE.finditer(text or ""):
        left, right = re.split(r"\s*[-–]\s*", match.group(0), maxsplit=1)
        start = _parse_year(left)
        if right.lower() in {"present", "now"}:
            end = 2026
        else:
            end = _parse_year(right)
        if start and end and 0 <= end - start < 60:
            spans.append((start, end))
    if not spans:
        return None
    earliest = min(start for start, _ in spans)
    latest = max(end for _, end in spans)
    return max(1, latest - earliest)


def _parse_year(value: str) -> int | None:
    match = re.search(r"\b(?:19|20)\d{2}\b", value)
    return int(match.group(0)) if match else None


def _significant_tokens(text: str | None) -> list[str]:
    tokens = set()
    for token in tokenize_words(text):
        if len(token) < 3 or token in _STOPWORDS or token in ARABIC_STOPWORDS:
            continue
        tokens.add(token)
    return sorted(tokens)


def _snippet_for_term(norm: str, term: str, limit: int = 220) -> str:
    index = norm.find(term)
    if index < 0:
        return term
    start = max(0, index - 60)
    end = min(len(norm), index + limit)
    snippet = " ".join(norm[start:end].split())
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(norm):
        snippet = f"{snippet}…"
    return snippet


def derive_evidence_payload(*, resume_text: str | None, requirements: Any) -> dict[str, Any]:
    """Build a validated match-evidence payload for every requirement.

    ``requirements`` may be the canonical v1.1 structured list, the legacy flat
    list, or a list of ``JobRequirement`` instances; it is normalized just like
    the evaluation workflow does so the emitted ``requirement_key`` set equals
    the exact key set the workflow will validate against.
    """
    normalized = normalize_job_profile_requirements(_as_raw_requirements(requirements))
    norm = normalize_for_matching(resume_text)
    allowed_keys = {requirement.key for requirement in normalized}

    items = []
    for requirement in normalized:
        req_tokens = _significant_tokens(requirement.text)
        matched_terms = [
            token for token in req_tokens if has_term_match(norm, token) or _has_phrase(norm, token)
        ]
        ratio = len(matched_terms) / len(req_tokens) if req_tokens else 0.0

        if not req_tokens:
            evidence_type, strength = "missing", "none"
        elif ratio == 0.0:
            evidence_type, strength = "missing", "none"
        elif ratio < 0.5:
            evidence_type, strength = "partial", "moderate"
        else:
            evidence_type, strength = "matched", "strong"

        raw_quote = ""
        if matched_terms and resume_text:
            raw_quote = extract_verbatim_quote(resume_text, matched_terms[0], max_chars=180)
            if not raw_quote:
                raw_quote = _snippet_for_term(norm, matched_terms[0], limit=180)

        items.append(
            {
                "evidence_type": evidence_type,
                "requirement_ref": {"requirement_key": requirement.key},
                "candidate_evidence": {
                    "quote": raw_quote,
                    "evidence_text": raw_quote,
                    "matched_terms": matched_terms,
                    "coverage_ratio": f"{ratio:.2f}",
                },
                "strength": strength,
                "provenance": {
                    "method": "deterministic",
                    "source": "resume_text",
                    "edge": "resume_details_service.build_match_evidence",
                    "evidence_engine_version": "2.0",
                },
            }
        )

    # Pass through EvidenceVerificationService boundary
    verifier = EvidenceVerificationService()
    verified_items = verifier.verify_evidence_items(
        resume_text=resume_text,
        evidence_items=items,
        requirements=normalized,
    )

    validated = validate_match_evidence_list(
        {"evidence_items": verified_items},
        allowed_keys=allowed_keys,
    )
    assert isinstance(validated, MatchEvidenceListOutput)
    return validated.model_dump()


def derive_explanation_payload(
    *,
    job_title: str | None,
    requirements: Any,
    evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic explanation payload aligned with the evidence payload."""
    normalized = normalize_job_profile_requirements(_as_raw_requirements(requirements))
    evidence_by_type: dict[str, int] = {"matched": 0, "partial": 0, "missing": 0}
    index_by_key = {requirement.key: requirement for requirement in normalized}
    points: list[str] = []

    for item in evidence_payload.get("evidence_items", []):
        key = item["requirement_ref"]["requirement_key"]
        requirement = index_by_key.get(key)
        req_text = requirement.text if requirement is not None else "the requirement"
        evidence_type = item["evidence_type"]
        evidence_by_type[evidence_type] += 1
        matched_terms = (item.get("candidate_evidence") or {}).get("matched_terms") or []
        if evidence_type == "matched":
            points.append(
                "Strong match for "
                f"“{req_text}” — resume references {', '.join(matched_terms) or 'it'}."
            )
        elif evidence_type == "partial":
            points.append(
                f"Partial match for “{req_text}” — only some of its key terms were found in the CV."
            )
        else:
            points.append(f"No supporting evidence found for “{req_text}”.")

    summary = (
        f"Evaluated against {job_title or 'the job'}: "
        f"{evidence_by_type['matched']} matched, "
        f"{evidence_by_type['partial']} partial, "
        f"{evidence_by_type['missing']} missing."
    )
    validated = validate_evaluation_explanation(
        {
            "summary": summary,
            "points": points[:10],
        }
    )
    return validated.model_dump()


def derive_screening_payloads(
    *,
    full_name: str,
    job_title: str | None,
    resume_text: str | None,
    requirements: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return (profile, evidence, explanation) payloads for one screening run."""
    profile = derive_profile_payload(full_name=full_name, resume_text=resume_text)
    evidence = derive_evidence_payload(resume_text=resume_text, requirements=requirements)
    explanation = derive_explanation_payload(
        job_title=job_title,
        requirements=requirements,
        evidence_payload=evidence,
    )
    return profile, evidence, explanation
