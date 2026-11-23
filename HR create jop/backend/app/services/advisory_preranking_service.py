from __future__ import annotations

import re
import sys
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import settings

MODEL_REVISION = "ccc66d3bcd826f577e26b9a4072cc5fe3a7ad6a3"
MODEL_SHA256 = "4654c156f3e4171abc9c716cdb771bf9116455d15ac1aab364aeeede0e3205b0"
RANKING_ADVISORY_MESSAGE = "LLM evaluation not run; ranking is advisory only"

# Exact allow-list precedence matters: these tool/product names survive organization
# redaction, even where a word is also a company name.
_PROTECTED_PRODUCTS = (
    "Google Analytics",
    "Microsoft Excel",
    "Amazon Web Services",
    "Oracle",
    "SAP",
    "AWS",
    "Excel",
    "Power BI",
    "Google Cloud",
    "Azure",
    "Salesforce",
    "GitHub",
)
_ORGANIZATION_NAMES = (
    "Harvard University",
    "Stanford University",
    "Cairo University",
    "The American University in Cairo",
    "Massachusetts Institute of Technology",
    "MIT",
    "Google",
    "Amazon",
    "Meta",
    "Facebook",
    "Microsoft",
    "Apple",
    "IBM",
    "Oracle Corporation",
    "جامعة القاهرة",
    "جامعة عين شمس",
    "جامعة الملك سعود",
    "الجامعة الأمريكية بالقاهرة",
    "شركة جوجل",
    "شركة أمازون",
    "شركة مايكروسوفت",
    "شركة آبل",
)
_SENSITIVE_LABEL_RE = re.compile(
    r"(?i)\b(?:age|date of birth|gender|sex|marital status|religion|nationality|"
    r"military service|military status|photo|picture|ethnicity)\b|"
    r"(?:العمر|تاريخ الميلاد|النوع|الجنس|الحالة الاجتماعية|الديانة|الدين|الجنسية|"
    r"الخدمة العسكرية|الموقف من التجنيد|الصورة|العرق)"
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(?:age|date of birth|gender|sex|marital status|religion|nationality|"
    r"military service|military status|photo|picture|ethnicity)\s*[:=]\s*[^,;|.!?]+|"
    r"(?:العمر|تاريخ الميلاد|النوع|الجنس|الحالة الاجتماعية|الديانة|الدين|الجنسية|"
    r"الخدمة العسكرية|الموقف من التجنيد|الصورة|العرق)\s*[:=：]\s*[^,;|.!؟]+"
)
_SECTION_HEADERS = {
    "experience": re.compile(
        r"(?i)^(?:professional )?(?:experience|employment|work history|career history|"
        r"الخبرات? العملية|الخبرة|الخبرات|التاريخ الوظيفي)\s*:?$"
    ),
    "skills": re.compile(
        r"(?i)^(?:technical )?skills|core competencies|المهارات|المهارات التقنية\s*:?$"
    ),
    "education": re.compile(
        r"(?i)^(?:education|academic background|التعليم|المؤهلات التعليمية|المؤهل الدراسي)\s*:?$"
    ),
}
_ANY_SECTION_HEADER = re.compile(
    r"(?i)^(?:summary|profile|objective|contact|personal information|languages|"
    r"certifications|projects|references|awards|الملخص|نبذة|الهدف|معلومات شخصية|"
    r"معلومات الاتصال|اللغات|الشهادات|المشاريع|المراجع)\s*:?$"
)


class TokenizerLike(Protocol):
    def encode(self, text: str, **kwargs): ...


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class CandidateText:
    identity: str
    cv_text: str


@dataclass(frozen=True)
class AdvisoryRank:
    identity: str
    rank: int
    score: float


class PreRankingUnavailable(RuntimeError):
    """A5 cannot run safely; caller should expose status and preserve normal flow."""


class PreRankingTimedOut(PreRankingUnavailable):
    pass


def _mark_unavailable(db, applications, items, message: str) -> None:
    for application, *_ in applications:
        application.advisory_status = "unavailable"
        application.advisory_message = message
    for item in items:
        item.advisory_status = "unavailable"
        item.advisory_message = message
    db.flush()


def redact_institution_names(text: str) -> str:
    """Remove known institution/employer names while protecting approved tool names."""
    text = _SENSITIVE_VALUE_RE.sub(" ", text)
    protected: dict[str, str] = {}
    for index, product in enumerate(_PROTECTED_PRODUCTS):
        marker = f"\ue000{index}\ue001"
        text = re.sub(re.escape(product), marker, text, flags=re.IGNORECASE)
        protected[marker] = product
    for organization in sorted(_ORGANIZATION_NAMES, key=len, reverse=True):
        text = re.sub(rf"(?i)(?<!\w){re.escape(organization)}(?!\w)", " ", text)
    text = re.sub(
        r"\b(?:at|@|employer:)\s+(?:[A-Z][\w&.-]*\s+){0,4}[A-Z][\w&.-]*"
        r"(?=\s+(?:as|in|from|between|using|to|for|since|during)\b|[,;|()]"
        r"|\s+(?:19|20)\d{2}|$)",
        " ",
        text,
    )
    text = re.sub(
        r"(?u)(?:في\s+)?(?:شركة|مؤسسة|جامعة|كلية|مدرسة)\s+"
        r"[\w\u0600-\u06ff& -]{2,55}?"
        r"(?=\s+(?:19|20)\d{2}|[,;|.!؟]|$|\s+(?:باستخدام|مع|في مجال|بصفتي|حيث|وكنت)\b)",
        " ",
        text,
    )
    for marker, product in protected.items():
        text = text.replace(marker, product)
    return re.sub(r"\s+", " ", text).strip()


def _collect_sections(cv_text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"experience": [], "skills": [], "education": []}
    current: str | None = None
    for raw in cv_text.splitlines():
        line = " ".join(raw.split())
        if not line or _SENSITIVE_LABEL_RE.search(line):
            continue
        matched = next(
            (name for name, pattern in _SECTION_HEADERS.items() if pattern.fullmatch(line)), None
        )
        if matched:
            current = matched
            continue
        if _ANY_SECTION_HEADER.fullmatch(line):
            current = None
            continue
        if current:
            sections[current].append(line)
    # Unlabeled CVs only contribute year-bearing work lines, recognized skills, and
    # degree text; never fall back to full CV content.
    if not sections["experience"]:
        from app.services.resume_details_service import extract_experience

        sections["experience"] = extract_experience(cv_text)
    if not sections["skills"]:
        from app.services.resume_details_service import build_skills

        sections["skills"] = build_skills(cv_text)
    if not sections["education"]:
        from app.services.resume_details_service import extract_education

        sections["education"] = extract_education(cv_text)
    return sections


def _token_count(tokenizer: TokenizerLike, text: str) -> int:
    return len(tokenizer.encode(text).ids)


def _split_to_token_limit(
    tokenizer: TokenizerLike, text: str, *, prefix: str, max_tokens: int = 512
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    for word in text.split():
        proposed = " ".join([*current, word])
        if _token_count(tokenizer, prefix + proposed) <= max_tokens:
            current.append(word)
            continue
        if current:
            chunks.append(" ".join(current))
        current = [word]
        if _token_count(tokenizer, prefix + word) > max_tokens:
            raise PreRankingUnavailable("A token cannot fit within the model input limit.")
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_candidate_chunks(cv_text: str, tokenizer: TokenizerLike, *, max_chunks: int) -> list[str]:
    sections = _collect_sections(cv_text)
    chunks: list[str] = []
    for section_name in ("experience", "skills", "education"):
        lines = sections[section_name]
        if not lines:
            continue
        body = redact_institution_names(" ".join(lines))
        if not body:
            continue
        for piece in _split_to_token_limit(
            tokenizer, f"{section_name}: {body}", prefix="passage: "
        ):
            chunks.append("passage: " + piece)
            if len(chunks) >= max_chunks:
                return chunks
    return chunks


def build_requirement_chunks(requirements: Sequence[str], tokenizer: TokenizerLike) -> list[str]:
    chunks: list[str] = []
    for requirement in requirements:
        clean = " ".join(str(requirement).split())
        if clean:
            chunks.extend(
                "query: " + piece
                for piece in _split_to_token_limit(tokenizer, clean, prefix="query: ")
            )
    return chunks


def rank_candidates(
    requirements: Sequence[str],
    candidates: Sequence[CandidateText],
    *,
    tokenizer: TokenizerLike,
    embedder: Embedder,
    max_chunks_per_cv: int,
    timeout_seconds: float,
) -> list[AdvisoryRank]:
    """Rank by mean best requirement-to-CV-chunk cosine; never an official score."""
    started = time.monotonic()
    req_chunks = build_requirement_chunks(requirements, tokenizer)
    if not req_chunks:
        raise PreRankingUnavailable("No approved job requirements are available for ranking.")
    candidate_chunks: dict[str, list[str]] = {}
    all_texts = list(req_chunks)
    for candidate in candidates:
        chunks = build_candidate_chunks(candidate.cv_text, tokenizer, max_chunks=max_chunks_per_cv)
        candidate_chunks[candidate.identity] = chunks
        all_texts.extend(chunks)
    if not any(candidate_chunks.values()):
        raise PreRankingUnavailable("No eligible experience, skills, or education text found.")
    remaining = timeout_seconds - (time.monotonic() - started)
    if remaining <= 0:
        raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
    embed_with_timeout = getattr(embedder, "embed_with_timeout", None)
    vectors = (
        embed_with_timeout(all_texts, timeout_seconds=remaining)
        if callable(embed_with_timeout)
        else embedder.embed(all_texts)
    )
    if time.monotonic() - started > timeout_seconds:
        raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
    if len(vectors) != len(all_texts):
        raise PreRankingUnavailable("Embedding runtime returned an incomplete result.")

    def cosine(left: Sequence[float], right: Sequence[float]) -> float:
        return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))

    req_vectors = vectors[: len(req_chunks)]
    offset = len(req_chunks)
    scored: list[tuple[str, float]] = []
    for candidate in candidates:
        chunk_texts = candidate_chunks[candidate.identity]
        chunk_vectors = vectors[offset : offset + len(chunk_texts)]
        offset += len(chunk_texts)
        score = (
            sum(max(cosine(req, chunk) for chunk in chunk_vectors) for req in req_vectors)
            / len(req_vectors)
            if chunk_vectors
            else 0.0
        )
        scored.append((candidate.identity, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    # top_n is enforced by the caller; the full deterministic order is returned for UI.
    return [
        AdvisoryRank(identity=identity, rank=index + 1, score=score)
        for index, (identity, score) in enumerate(scored)
    ]


def advisory_evaluation_state(rank: int, top_n: int) -> tuple[str, str]:
    if rank > top_n:
        return "not_evaluated", RANKING_ADVISORY_MESSAGE
    return "ranked", "Advisory rank only; official score and HR decisions are unchanged."


class OnnxE5Embedder:
    """CPU ONNX adapter. Model/tokenizer must be provisioned locally by the package."""

    def __init__(
        self,
        model_path: Path,
        tokenizer_path: Path,
        *,
        threads: int,
        quantized: bool = False,
    ):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        if threads < 1:
            raise ValueError("threads must be positive")
        if quantized and not cpu_supports_avx512_vnni():
            raise PreRankingUnavailable(
                "Quantized advisory model unavailable: AVX-512 VNNI support could not be verified. "
                "Use the portable FP32 model or install on a verified Linux CPU."
            )
        expected_hash = QUANTIZED_MODEL_SHA256 if quantized else MODEL_SHA256
        if not model_path.is_file() or not tokenizer_path.is_file():
            raise PreRankingUnavailable("Pinned ONNX model or tokenizer files are missing.")
        if _sha256_file(model_path) != expected_hash:
            raise PreRankingUnavailable("Pinned ONNX model checksum does not match.")
        self._np = np
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
            sess_options=_session_options(ort, threads),
        )
        self._inputs = {item.name for item in self._session.get_inputs()}
        self._output = self._session.get_outputs()[0].name

    @property
    def tokenizer(self) -> TokenizerLike:
        return self._tokenizer

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, run_options=None)

    def embed_with_timeout(
        self, texts: Sequence[str], *, timeout_seconds: float
    ) -> list[list[float]]:
        import onnxruntime as ort

        run_options = ort.RunOptions()
        timeout_fired = threading.Event()

        def terminate_run() -> None:
            timeout_fired.set()
            run_options.terminate = True

        timer = threading.Timer(timeout_seconds, terminate_run)
        timer.daemon = True
        timer.start()
        try:
            vectors = self._embed(texts, run_options=run_options)
            if timeout_fired.is_set():
                raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
            return vectors
        except Exception as exc:
            if timeout_fired.is_set():
                raise PreRankingTimedOut(
                    "Advisory pre-ranking exceeded its configured time limit."
                ) from exc
            raise
        finally:
            timer.cancel()

    def _embed(self, texts: Sequence[str], *, run_options) -> list[list[float]]:
        if not texts:
            return []
        encoded = [self._tokenizer.encode(text) for text in texts]
        if any(len(item.ids) > 512 for item in encoded):
            raise PreRankingUnavailable("Input exceeded the 512-token model limit.")
        vectors: list[list[float]] = []
        for start in range(0, len(encoded), 16):
            if run_options is not None and run_options.terminate:
                raise PreRankingTimedOut("Advisory pre-ranking exceeded its configured time limit.")
            batch = encoded[start : start + 16]
            width = max(len(item.ids) for item in batch)
            ids = self._np.zeros((len(batch), width), dtype=self._np.int64)
            mask = self._np.zeros((len(batch), width), dtype=self._np.int64)
            types = self._np.zeros((len(batch), width), dtype=self._np.int64)
            for row, item in enumerate(batch):
                count = len(item.ids)
                ids[row, :count] = item.ids
                mask[row, :count] = 1
                if item.type_ids:
                    types[row, :count] = item.type_ids
            inputs = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                inputs["token_type_ids"] = types
            outputs = self._session.run([self._output], inputs, run_options=run_options)[0]
            pooled = (outputs * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            norms = self._np.linalg.norm(pooled, axis=1, keepdims=True)
            vectors.extend((pooled / self._np.maximum(norms, 1e-12)).tolist())
        return vectors


def _session_options(ort, threads: int):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return options


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


QUANTIZED_MODEL_SHA256 = "dd476dd0c2514e9b9be83aeb3853fac0763e0bdf4a71645407587d77c48a2d88"


def cpu_supports_avx512_vnni() -> bool:
    """Fail closed unless Linux exposes the required CPU flag to this process."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        cpu_info = Path("/proc/cpuinfo").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    flags = set(re.findall(r"(?m)^flags\s*:\s*(.*)$", cpu_info))
    return bool(flags) and all(
        {"avx512f", "avx512_vnni"}.issubset(set(line.split())) for line in flags
    )


@lru_cache(maxsize=1)
def configured_embedder() -> OnnxE5Embedder:
    if not settings.a5_prerank_enabled:
        raise PreRankingUnavailable("Advisory pre-ranking is disabled by configuration.")
    model_dir = Path(settings.a5_prerank_model_dir)
    return OnnxE5Embedder(
        model_dir
        / ("model_qint8_avx512_vnni.onnx" if settings.a5_prerank_quantized else "model_O4.onnx"),
        model_dir / "tokenizer.json",
        threads=settings.a5_prerank_threads,
        quantized=settings.a5_prerank_quantized,
    )


def rank_worker_cohort(db, *, job, batch, approved_profile, storage) -> None:
    """Rank unreviewed applications and the claimed batch cohort inside the worker."""
    from sqlalchemy import select

    from app.models import (
        CandidateEvaluation,
        Job,
        JobApplication,
        Resume,
        ScreeningBatch,
        ScreeningBatchItem,
    )
    from app.services.text_extraction_service import extract_text

    if not settings.a5_prerank_enabled:
        return
    scoped_job = db.scalar(
        select(Job).where(Job.id == job.id, Job.organization_id == batch.organization_id)
    )
    if scoped_job is None:
        return

    message_unavailable = "Advisory pre-ranking unavailable; standard evaluation continued."
    pending_apps = list(
        db.execute(
            select(JobApplication, Resume.extracted_text)
            .join(Resume, Resume.id == JobApplication.resume_id)
            .where(
                JobApplication.job_id == scoped_job.id,
                JobApplication.organization_id == batch.organization_id,
                JobApplication.status.in_(("created", "analysis_pending", "analysis_failed")),
                ~select(CandidateEvaluation.id)
                .where(
                    CandidateEvaluation.job_application_id == JobApplication.id,
                    CandidateEvaluation.is_current.is_(True),
                )
                .exists(),
            )
        ).all()
    )
    cohort_items = list(
        db.scalars(
            select(ScreeningBatchItem)
            .join(ScreeningBatch, ScreeningBatch.id == ScreeningBatchItem.batch_id)
            .where(
                ScreeningBatch.job_id == scoped_job.id,
                ScreeningBatch.organization_id == batch.organization_id,
                ScreeningBatchItem.status.in_(("queued", "running")),
            )
        ).all()
    )
    already_in_apps = {app.id for app, _ in pending_apps}
    applications_by_id = {app.id: app for app, _ in pending_apps}
    application_text_by_id = {app.id: text for app, text in pending_apps}
    if pending_apps or cohort_items:
        work_is_ranked = all(
            app.advisory_rank is not None
            and app.advisory_status
            == advisory_evaluation_state(app.advisory_rank, scoped_job.prerank_top_n)[0]
            for app, _ in pending_apps
        ) and all(
            item.advisory_rank is not None
            and item.advisory_status
            == advisory_evaluation_state(item.advisory_rank, scoped_job.prerank_top_n)[0]
            for item in cohort_items
        )
        if work_is_ranked:
            return
    candidates: list[CandidateText] = [
        CandidateText(identity=f"app:{app.id}", cv_text=text or "")
        for app, text in pending_apps
        if text
    ]
    candidate_identities = {candidate.identity for candidate in candidates}
    item_identity: dict[uuid.UUID, str] = {}
    for cohort_item in cohort_items:
        if cohort_item.application_id in already_in_apps:
            if application_text_by_id[cohort_item.application_id]:
                item_identity[cohort_item.id] = f"app:{cohort_item.application_id}"
                continue
        try:
            raw = storage.read(
                file_uri=cohort_item.storage_key,
                organization_id=batch.organization_id,
                file_id=(
                    cohort_item.resume_id
                    if cohort_item.source == "public_application"
                    else cohort_item.id
                ),
            )
            cv_text = extract_text(
                raw,
                filename=cohort_item.filename,
                max_pdf_pages=settings.max_pdf_pages,
                max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
                max_docx_entries=settings.max_docx_entries,
            )
        except Exception:
            _mark_unavailable(db, pending_apps, cohort_items, message_unavailable)
            return
        identity = (
            f"app:{cohort_item.application_id}"
            if cohort_item.application_id in already_in_apps
            else f"item:{cohort_item.id}"
        )
        item_identity[cohort_item.id] = identity
        if identity not in candidate_identities:
            candidates.append(CandidateText(identity=identity, cv_text=cv_text))
            candidate_identities.add(identity)

    try:
        model = configured_embedder()
        requirements = []
        for item in approved_profile.profile_data.get("requirements") or []:
            text = item.get("text") if isinstance(item, dict) else item
            if text and not _SENSITIVE_LABEL_RE.search(str(text)):
                requirements.append(str(text))
        ranked = rank_candidates(
            requirements,
            candidates,
            tokenizer=model.tokenizer,
            embedder=model,
            max_chunks_per_cv=settings.a5_prerank_max_chunks_per_cv,
            timeout_seconds=settings.a5_prerank_timeout_seconds,
        )
        by_identity = {result.identity: result for result in ranked}
        for identity, result in by_identity.items():
            rank_status, advisory_message = advisory_evaluation_state(
                result.rank, scoped_job.prerank_top_n
            )
            if identity.startswith("app:"):
                application_id = uuid.UUID(identity[4:])
                application = applications_by_id.get(application_id)
                if application is not None:
                    application.advisory_rank = result.rank
                    application.advisory_score = result.score
                    application.advisory_status = rank_status
                    application.advisory_message = advisory_message
            else:
                item_id = uuid.UUID(identity[5:])
                item = next((value for value in cohort_items if value.id == item_id), None)
                if item is not None:
                    item.advisory_rank = result.rank
                    item.advisory_score = result.score
                    item.advisory_status = rank_status
                    item.advisory_message = advisory_message
        # A public application belongs to both the item and application record.
        for cohort_item in cohort_items:
            identity = item_identity.get(cohort_item.id)
            result = by_identity.get(identity or "")
            if result is None:
                continue
            status, message = advisory_evaluation_state(result.rank, scoped_job.prerank_top_n)
            cohort_item.advisory_rank = result.rank
            cohort_item.advisory_score = result.score
            cohort_item.advisory_status = status
            cohort_item.advisory_message = message
            application = applications_by_id.get(cohort_item.application_id)
            if application is not None:
                application.advisory_rank = result.rank
                application.advisory_score = result.score
                application.advisory_status = status
                application.advisory_message = message
    except PreRankingUnavailable as exc:
        _mark_unavailable(db, pending_apps, cohort_items, str(exc))
    except Exception:
        _mark_unavailable(db, pending_apps, cohort_items, message_unavailable)
    db.flush()
