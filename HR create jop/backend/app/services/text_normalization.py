"""Text normalization and tokenization for Arabic and English resume processing (HERA Prompt 8).

Provides conservative Unicode, Arabic, and Latin normalization used strictly
for comparison, verification, and heuristic candidate-requirement matching:
- Unicode NFKC normalization.
- Arabic tatweel (ـ) and diacritics/tashkeel removal.
- Arabic alef variant normalization ([إأآٱ] -> ا).
- Arabic teh marbuta (ة -> ه) and yeh/alef maksura (ى -> ي) normalization for matching.
- Case-folding for Latin text.
- Whitespace collapsing and punctuation boundary handling.
- Bidirectional technical synonym support (e.g., قواعد البيانات <-> SQL/Database).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Arabic diacritics / tashkeel range: \u064B to \u065F plus \u0670 (superscript alef)
_ARABIC_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]")
_ARABIC_TATWEEL = "\u0640"
_ARABIC_ALEFS_RE = re.compile(r"[إأآٱ]")

# Word pattern matching Unicode letters, digits, and programming characters (#, +, ., /)
_UNICODE_WORD_RE = re.compile(r"[\w+#./-]+", re.UNICODE)

# Common Arabic/English technical synonyms for equitable criteria evaluation
TECHNICAL_SYNONYMS: dict[str, list[str]] = {
    "python": ["python", "بايثون"],
    "java": ["java", "جافا"],
    "database": ["database", "databases", "sql", "قواعد البيانات", "قاعدة بيانات"],
    "postgresql": ["postgresql", "postgres", "بوستجريس"],
    "fastapi": ["fastapi", "فاست اي بي اي", "فاست ابي"],
    "docker": ["docker", "دوكر"],
    "kubernetes": ["kubernetes", "k8s", "كوبرنيتس"],
    "machine learning": ["machine learning", "ml", "تعلم الالة", "تعلم الآلة"],
    "data science": ["data science", "علم البيانات"],
    "react": ["react", "react.js", "رياكت"],
    "spring boot": ["spring boot", "springboot", "سبرينج بوت", "سبرنج بوت"],
    "rest api": ["rest api", "restful api", "apis", "واجهات برمجة التطبيقات", "واجهة برمجة التطبيقات"],
    "testing": ["testing", "unit testing", "qa", "اختبار البرمجيات", "فحص البرمجيات"],
    "security": ["security", "cybersecurity", "امن المعلومات", "أمن المعلومات", "الأمن السيبراني"],
    "agile": ["agile", "scrum", "أجايل", "اجايل", "سكروم"],
}

ARABIC_STOPWORDS: frozenset[str] = frozenset(
    {
        "في",
        "من",
        "على",
        "إلى",
        "الى",
        "عن",
        "مع",
        "هذا",
        "هذه",
        "ذلك",
        "تلك",
        "التي",
        "الذي",
        "الذين",
        "اللذين",
        "اللائي",
        "اللاتي",
        "كان",
        "كانت",
        "يكون",
        "تكون",
        "أن",
        "ان",
        "إن",
        "أو",
        "او",
        "ثم",
        "حيث",
        "كل",
        "غير",
        "بين",
        "بعد",
        "قبل",
        "خلال",
        "تم",
        "تمت",
        "قد",
        "لقد",
        "ما",
        "لا",
        "لم",
        "لن",
        "حتى",
        "إذا",
        "اذا",
        "إذ",
        "اذ",
        "كما",
        "لكن",
        "لأن",
        "لان",
        "عند",
        "فوق",
        "تحت",
        "نحو",
        "ضد",
    }
)


def normalize_arabic(text: str) -> str:
    """Apply conservative Arabic normalization without altering non-Arabic characters."""
    if not text:
        return ""
    # Remove tatweel (kashida)
    cleaned = text.replace(_ARABIC_TATWEEL, "")
    # Remove tashkeel (diacritics)
    cleaned = _ARABIC_DIACRITICS_RE.sub("", cleaned)
    # Normalize alef variants to bare alef
    cleaned = _ARABIC_ALEFS_RE.sub("ا", cleaned)
    # Normalize alef maksura to yeh for comparison
    cleaned = cleaned.replace("ى", "ي")
    # Normalize teh marbuta to heh for comparison
    cleaned = cleaned.replace("ة", "ه")
    return cleaned


def normalize_for_matching(text: str | None) -> str:
    """Normalize text conservatively for comparison, quote verification, and search.

    Preserves original characters in memory while producing a canonical
    lowercased, NFKC-normalized, diacritic-free, and whitespace-collapsed string.
    """
    if not text:
        return ""
    # Unicode NFKC normalization
    nfkc = unicodedata.normalize("NFKC", text)
    # Lowercase Latin characters
    lowered = nfkc.lower()
    # Apply Arabic normalization
    norm_arabic = normalize_arabic(lowered)
    # Collapse multiple whitespace characters to a single space
    collapsed = re.sub(r"\s+", " ", norm_arabic).strip()
    return collapsed


def tokenize_words(text: str | None) -> list[str]:
    """Tokenize a string into words supporting both Latin and Arabic scripts."""
    norm = normalize_for_matching(text)
    if not norm:
        return []
    tokens = []
    for match in _UNICODE_WORD_RE.finditer(norm):
        token = match.group(0).strip(".,/-")
        if token and len(token) >= 2:
            tokens.append(token)
    return tokens


def get_synonym_variants(term: str) -> list[str]:
    """Return all equivalent forms (English and Arabic) for a technical term."""
    norm_term = normalize_for_matching(term)
    variants = {norm_term}

    for key, syn_list in TECHNICAL_SYNONYMS.items():
        norm_syns = [normalize_for_matching(s) for s in syn_list]
        if norm_term == normalize_for_matching(key) or norm_term in norm_syns:
            for s in norm_syns:
                variants.add(s)

    return list(variants)


def has_term_match(normalized_source: str, term: str) -> bool:
    """Determine whether normalized_source contains term or any of its technical synonyms.

    Uses boundary checks to avoid substring false positives (e.g. 'go' in 'good').
    """
    variants = get_synonym_variants(term)
    for variant in variants:
        if not variant:
            continue
        # If variant is multi-word or has special punctuation, use exact phrase containment
        if " " in variant or any(char in variant for char in "#+./-"):
            if variant in normalized_source:
                return True
        else:
            # Single word: enforce word boundary
            pattern = rf"(?<![\w\u0600-\u06FF]){re.escape(variant)}(?![\w\u0600-\u06FF])"
            if re.search(pattern, normalized_source):
                return True
    return False


def find_quote_in_source(quote: str, source_text: str) -> tuple[bool, dict[str, Any] | None]:
    """Verify whether a proposed quote exists in the source text and locate its position.

    Returns:
        (is_verified: bool, location_metadata: dict | None)
    """
    cleaned_quote = (quote or "").strip()
    if not cleaned_quote or not source_text:
        return False, None

    # 1. Attempt exact verbatim match in source text
    exact_idx = source_text.find(cleaned_quote)
    if exact_idx >= 0:
        return True, {
            "start": exact_idx,
            "end": exact_idx + len(cleaned_quote),
            "match_type": "exact",
            "verbatim_quote": cleaned_quote,
        }

    # 2. Attempt normalized match for whitespace or diacritic variations
    norm_quote = normalize_for_matching(cleaned_quote)
    norm_source = normalize_for_matching(source_text)

    if norm_quote and norm_quote in norm_source:
        norm_idx = norm_source.find(norm_quote)
        # Approximate offset estimate in source text
        ratio = len(source_text) / max(1, len(norm_source))
        est_start = int(norm_idx * ratio)
        est_end = min(len(source_text), int((norm_idx + len(norm_quote)) * ratio))
        return True, {
            "start": est_start,
            "end": est_end,
            "match_type": "normalized",
            "verbatim_quote": cleaned_quote,
        }

    # Quote does not appear in source text (fabricated, altered, or from another CV)
    return False, None


def extract_verbatim_quote(source_text: str | None, term: str, max_chars: int = 180) -> str:
    """Extract a verbatim quote from source_text surrounding a match for term or its variants."""
    if not source_text or not term:
        return ""

    variants = get_synonym_variants(term)
    source_lower = source_text.lower()
    best_idx = -1
    matched_len = len(term)

    # 1. Search for direct substring variants in lowercase source
    for var in variants:
        idx = source_lower.find(var.lower())
        if idx >= 0:
            best_idx = idx
            matched_len = len(var)
            break

    # 2. If not found directly, try normalized match
    if best_idx < 0:
        norm_source = normalize_for_matching(source_text)
        for var in variants:
            norm_var = normalize_for_matching(var)
            idx = norm_source.find(norm_var)
            if idx >= 0:
                ratio = len(source_text) / max(1, len(norm_source))
                best_idx = int(idx * ratio)
                matched_len = len(var)
                break

    if best_idx < 0:
        return ""

    # Extract verbatim slice around the match
    start = max(0, best_idx - 30)
    end = min(len(source_text), best_idx + matched_len + max_chars)
    snippet = " ".join(source_text[start:end].split())
    return snippet
