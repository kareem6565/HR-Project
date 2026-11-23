from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.schemas.jobs import JobCreate
from app.core.config import Settings, settings
from app.services.advisory_preranking_service import (
    CandidateText,
    OnnxE5Embedder,
    PreRankingTimedOut,
    advisory_evaluation_state,
    build_candidate_chunks,
    build_requirement_chunks,
    cpu_supports_avx512_vnni,
    rank_candidates,
    rank_worker_cohort,
    redact_institution_names,
)


class WordTokenizer:
    def encode(self, text: str):
        return type("Encoding", (), {"ids": text.split()})()


class LookupEmbedder:
    def embed(self, texts):
        return [
            [1.0, 0.0] if text.startswith("query:") or "Python" in text else [0.0, 1.0]
            for text in texts
        ]


class SlowEmbedder:
    def embed(self, texts):
        time.sleep(0.02)
        return [[1.0] for _ in texts]


def test_sensitive_identity_fields_are_removed_and_product_names_survive():
    first = redact_institution_names(
        "Worked at Google, Harvard University using Google Analytics, Oracle, and AWS. "
        "العمر: 36 والجنسية: مصرية. عمل في شركة جوجل باستخدام SAP."
    )
    swapped = redact_institution_names(
        "Worked at Microsoft, Stanford University using Google Analytics, Oracle, and AWS. "
        "العمر: 36 والجنسية: مصرية. عمل في شركة أمازون باستخدام SAP."
    )

    assert first == swapped
    assert "Google Analytics" in first
    assert "Oracle" in first
    assert "AWS" in first
    assert "SAP" in first
    assert "Harvard" not in first
    assert "العمر" not in first
    assert "الجنسية" not in first
    work_history = redact_institution_names(
        "Built distributed services at Google as a senior backend engineer using Python."
    )
    assert "Google" not in work_history
    assert "senior backend engineer" in work_history
    assert "Python" in work_history


def test_sensitive_bilingual_attributes_are_removed():
    redacted = redact_institution_names(
        "Experience\nSenior engineer\nSkills\nPython, AWS\n"
        "Marital status: married; religion: sample; military service: completed\n"
        "الحالة الاجتماعية: متزوج; الديانة: عينة; الموقف من التجنيد: أدى الخدمة"
    )
    for value in ("married", "sample", "completed", "متزوج", "عينة", "أدى الخدمة"):
        assert value not in redacted


def test_candidate_chunks_only_use_allowed_sections_and_add_prefixes():
    cv = """Name: Example Person
    Gender: woman
    Summary
    Principal engineer
    Experience
    Led Python backend services at Google, 2021-2024
    Skills
    Python, FastAPI, AWS
    Education
    Computer Science, Harvard University, 2017
    Personal Information
    Age: 36"""

    chunks = build_candidate_chunks(cv, WordTokenizer(), max_chunks=8)

    assert chunks
    assert all(chunk.startswith("passage: ") for chunk in chunks)
    assert all(len(WordTokenizer().encode(chunk).ids) <= 512 for chunk in chunks)
    joined = " ".join(chunks)
    assert "Python" in joined and "FastAPI" in joined and "AWS" in joined
    assert "Example Person" not in joined
    assert "Google" not in joined
    assert "Harvard" not in joined
    assert "woman" not in joined


def test_long_requirements_are_chunked_with_query_prefix_under_model_limit():
    requirement = "distributed systems " * 600
    chunks = build_requirement_chunks([requirement], WordTokenizer())

    assert len(chunks) > 1
    assert all(chunk.startswith("query: ") for chunk in chunks)
    assert all(len(WordTokenizer().encode(chunk).ids) <= 512 for chunk in chunks)


def test_advisory_rank_is_deterministic_and_never_official_score():
    ranked = rank_candidates(
        ["Python backend"],
        [
            CandidateText("strong", "Experience\nexperience Python backend\nSkills\nPython"),
            CandidateText("weak", "Experience\nexperience graphic design"),
        ],
        tokenizer=WordTokenizer(),
        embedder=LookupEmbedder(),
        max_chunks_per_cv=4,
        timeout_seconds=1,
    )

    assert [(item.identity, item.rank) for item in ranked] == [("strong", 1), ("weak", 2)]
    assert all(0.0 <= item.score <= 1.0 for item in ranked)


def test_outside_top_n_has_exact_notice_and_can_be_manually_evaluated():
    status, message = advisory_evaluation_state(rank=21, top_n=20)
    assert status == "not_evaluated"
    assert message == "LLM evaluation not run; ranking is advisory only"
    assert advisory_evaluation_state(rank=21, top_n=21)[0] == "ranked"


def test_top_n_job_setting_is_defaulted_and_bounded():
    assert JobCreate(title="Platform Engineer").prerank_top_n == 20
    with pytest.raises(ValueError):
        JobCreate(title="Platform Engineer", prerank_top_n=101)


def test_quantized_model_fails_closed_when_vnni_cannot_be_verified(monkeypatch):
    import app.services.advisory_preranking_service as service

    monkeypatch.setattr(service.sys, "platform", "win32")
    assert cpu_supports_avx512_vnni() is False
    with pytest.raises(service.PreRankingUnavailable, match="AVX-512 VNNI support"):
        OnnxE5Embedder(Path("missing-model"), Path("missing-tokenizer"), threads=2, quantized=True)


def test_worker_ranks_public_application_once_and_syncs_batch_item(monkeypatch):
    import app.services.advisory_preranking_service as service

    organization_id = uuid4()
    application_id = uuid4()
    other_application_id = uuid4()
    job = SimpleNamespace(id=uuid4(), organization_id=organization_id, prerank_top_n=20)
    batch = SimpleNamespace(id=uuid4(), job_id=job.id, organization_id=organization_id)
    application = SimpleNamespace(
        id=application_id,
        advisory_rank=None,
        advisory_score=None,
        advisory_status=None,
        advisory_message=None,
    )
    other_application = SimpleNamespace(
        id=other_application_id,
        advisory_rank=None,
        advisory_score=None,
        advisory_status=None,
        advisory_message=None,
    )
    item = SimpleNamespace(
        id=uuid4(),
        organization_id=organization_id,
        batch_id=batch.id,
        status="running",
        application_id=application_id,
        storage_key="org-scoped-key",
        source="public_application",
        resume_id=uuid4(),
        filename="synthetic.pdf",
        advisory_rank=None,
        advisory_score=None,
        advisory_status=None,
        advisory_message=None,
    )
    other_item = SimpleNamespace(
        id=uuid4(),
        batch_id=uuid4(),
        status="queued",
        application_id=other_application_id,
        storage_key="other-org-scoped-key",
        source="public_application",
        resume_id=uuid4(),
        filename="another-synthetic.pdf",
        advisory_rank=None,
        advisory_score=None,
        advisory_status=None,
        advisory_message=None,
    )

    class FakeResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class FakeDB:
        def scalar(self, _query):
            return job

        def execute(self, _query):
            return FakeResult([(application, None), (other_application, None)])

        def scalars(self, query):
            sql = str(query)
            assert "screening_batches.job_id" in sql
            assert "screening_batches.organization_id" in sql
            assert "screening_batch_items.batch_id = " not in sql
            return FakeResult([item, other_item])

        def flush(self):
            return None

    class FakeEmbedder:
        tokenizer = WordTokenizer()

        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    class FakeStorage:
        def read(self, **kwargs):
            assert kwargs["organization_id"] == organization_id
            assert kwargs["file_id"] in {item.resume_id, other_item.resume_id}
            return b"synthetic-cv-content"

    monkeypatch.setattr(settings, "a5_prerank_enabled", True)
    monkeypatch.setattr(service, "configured_embedder", lambda: FakeEmbedder())
    monkeypatch.setattr(
        "app.services.text_extraction_service.extract_text",
        lambda *_args, **_kwargs: "Experience\nPython backend services",
    )
    profile = SimpleNamespace(profile_data={"requirements": [{"text": "Python backend"}]})

    rank_worker_cohort(
        FakeDB(), job=job, batch=batch, approved_profile=profile, storage=FakeStorage()
    )

    assert application.advisory_status == "ranked"
    assert other_application.advisory_status == "ranked"
    assert item.advisory_status == "ranked"
    assert other_item.advisory_status == "ranked"
    assert application.advisory_rank == item.advisory_rank
    assert other_application.advisory_rank == other_item.advisory_rank
    assert application.advisory_score == item.advisory_score

    monkeypatch.setattr(
        service,
        "configured_embedder",
        lambda: pytest.fail("a completed batch cohort must not be re-ranked"),
    )
    rank_worker_cohort(
        FakeDB(), job=job, batch=batch, approved_profile=profile, storage=FakeStorage()
    )


def test_ranking_timeout_is_visible_and_does_not_return_a_partial_ranking():
    with pytest.raises(PreRankingTimedOut):
        rank_candidates(
            ["Python backend"],
            [CandidateText("candidate", "Experience\nPython backend")],
            tokenizer=WordTokenizer(),
            embedder=SlowEmbedder(),
            max_chunks_per_cv=4,
            timeout_seconds=0.001,
        )


def test_onnx_run_is_cancelled_when_the_per_run_deadline_expires():
    import numpy as np

    class Encoded:
        ids = [1, 2]
        type_ids = [0, 0]

    class FakeTokenizer:
        def encode(self, _text):
            return Encoded()

    class BlockingSession:
        def run(self, _outputs, _inputs, *, run_options):
            while not run_options.terminate:
                time.sleep(0.001)
            raise RuntimeError("cancelled")

    embedder = OnnxE5Embedder.__new__(OnnxE5Embedder)
    embedder._np = np
    embedder._tokenizer = FakeTokenizer()
    embedder._session = BlockingSession()
    embedder._inputs = {"input_ids", "attention_mask", "token_type_ids"}
    embedder._output = "last_hidden_state"

    with pytest.raises(PreRankingTimedOut):
        embedder.embed_with_timeout(["passage: test"], timeout_seconds=0.01)


def test_preranking_feature_flag_is_off_by_default():
    assert Settings.model_fields["a5_prerank_enabled"].default is False
