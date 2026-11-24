from __future__ import annotations

import math
import time
from collections import Counter
from collections.abc import Sequence

from app.services.advisory_preranking_service import (
    AdvisoryRank,
    CandidateText,
    PreRankingTimedOut,
    PreRankingUnavailable,
    _collect_sections,
    redact_institution_names,
)
from app.services.text_normalization import normalize_for_matching, tokenize_words

# Canonical concepts map common English and Arabic skill labels to the same tokens.
# Keep this deterministic and dependency-free; adding aliases never changes scoring.
BILINGUAL_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "accountant": ("accountant", "محاسب", "محاسبا", "محاسبة", "محاسبي", "محاسبه"),
    "accounts payable": (
        "accounts payable",
        "الحسابات الدائنة",
        "حسابات الموردين",
        "الدائنون",
    ),
    "microsoft excel": ("microsoft excel", "excel", "إكسل", "اكسل"),
    "data analysis": ("data analysis", "تحليل البيانات", "تحليل بيانات", "محلل بيانات"),
    "python": ("python", "بايثون"),
    "sql": ("sql", "اس كيو ال"),
    "tableau": ("tableau", "تابلو"),
    "fastapi": ("fastapi", "فاست اي بي اي", "فاست ابي"),
    "docker": ("docker", "دوكر"),
    "kubernetes": ("kubernetes", "كوبرنيتس"),
    "react": ("react", "رياكت"),
}

# Fielded BM25: demonstrated work counts more than a bare keyword/skills list.
_FIELD_WEIGHTS = {"experience": 2.0, "skills": 1.0, "education": 0.4}
_K1 = 1.2
_B = 0.75


def _alias_sequences() -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    sequences = []
    for canonical, aliases in BILINGUAL_SKILL_ALIASES.items():
        canonical_tokens = tuple(tokenize_words(normalize_for_matching(canonical)))
        if not canonical_tokens:
            continue
        for alias in aliases:
            alias_tokens = tuple(tokenize_words(normalize_for_matching(alias)))
            if alias_tokens:
                sequences.append((alias_tokens, canonical_tokens))
    return sorted(sequences, key=lambda item: (-len(item[0]), item[0]))


_ALIAS_SEQUENCES = _alias_sequences()


def _tokens(text: str, *, bilingual_aliases: bool) -> list[str]:
    normalized = normalize_for_matching(text)
    tokens = tokenize_words(normalized)
    if not bilingual_aliases:
        return tokens
    result: list[str] = []
    index = 0
    while index < len(tokens):
        for alias, canonical in _ALIAS_SEQUENCES:
            end = index + len(alias)
            if tuple(tokens[index:end]) == alias:
                result.extend(canonical)
                index = end
                break
        else:
            result.append(tokens[index])
            index += 1
    return result


def _candidate_fields(candidate: CandidateText, *, bilingual_aliases: bool) -> dict[str, list[str]]:
    sections = _collect_sections(candidate.cv_text)
    return {
        field: _tokens(
            redact_institution_names(" ".join(sections[field])), bilingual_aliases=bilingual_aliases
        )
        for field in _FIELD_WEIGHTS
    }


def rank_lexically(
    requirements: Sequence[str],
    candidates: Sequence[CandidateText],
    *,
    timeout_seconds: float,
    bilingual_aliases: bool = True,
) -> list[AdvisoryRank]:
    """Rank eligible CV evidence with fielded BM25; no identity fields or embeddings."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    started = time.monotonic()
    deadline = started + timeout_seconds
    query_terms = {
        term
        for requirement in requirements
        for term in _tokens(str(requirement), bilingual_aliases=bilingual_aliases)
    }
    if not query_terms:
        raise PreRankingUnavailable("No approved job requirements are available for ranking.")

    documents: list[dict[str, list[str]]] = []
    for candidate in candidates:
        if time.monotonic() >= deadline:
            raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
        documents.append(_candidate_fields(candidate, bilingual_aliases=bilingual_aliases))
    if not any(any(document[field] for field in _FIELD_WEIGHTS) for document in documents):
        raise PreRankingUnavailable("No eligible experience, skills, or education text found.")

    total_docs = len(documents)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        present = {term for field in document.values() for term in field}
        document_frequency.update(present & query_terms)

    average_length = {
        field: (
            sum(len(document[field]) for document in documents) / total_docs if total_docs else 0.0
        )
        for field in _FIELD_WEIGHTS
    }
    idf = {
        term: math.log(
            1.0 + (total_docs - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
        )
        for term in query_terms
    }

    scored: list[tuple[str, float]] = []
    for candidate, document in zip(candidates, documents, strict=True):
        if time.monotonic() >= deadline:
            raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
        score = 0.0
        for field, field_weight in _FIELD_WEIGHTS.items():
            terms = document[field]
            counts = Counter(terms)
            length = len(terms)
            avg_len = average_length[field] or 1.0
            for term in query_terms:
                frequency = counts[term]
                if frequency == 0:
                    continue
                # BM25's saturation prevents repeated keywords from scaling without bound.
                denominator = frequency + _K1 * (1.0 - _B + _B * length / avg_len)
                score += field_weight * idf[term] * frequency * (_K1 + 1.0) / denominator
        scored.append((candidate.identity, score))

    max_score = max((score for _, score in scored), default=0.0)
    if max_score <= 0:
        raise PreRankingUnavailable("No eligible CV terms matched the job requirements.")
    normalized = [(identity, score / max_score) for identity, score in scored]
    normalized.sort(key=lambda item: (-item[1], item[0]))
    if time.monotonic() >= deadline:
        raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
    return [
        AdvisoryRank(identity=identity, rank=index + 1, score=score)
        for index, (identity, score) in enumerate(normalized)
    ]
