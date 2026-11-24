"""Measure advisory pre-ranking on a fixed, synthetic-only known-label cohort."""

# Synthetic CV prose remains as complete, readable sentences in the fixture templates.
# ruff: noqa: E501

from __future__ import annotations

import os
import statistics
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

APPLICANTS_PER_JOB = 120
TOP_N = 20
_EN_FILLER = (
    "Coordinated quarterly delivery plans with product, operations, and support teams, kept clear decision records, and followed agreed release and review procedures.",
    "Investigated production incidents, documented causes and follow-up actions, and shared concise handover notes so that colleagues could continue work without delays.",
    "Reviewed routine work for accuracy, tracked agreed service indicators, and raised delivery risks early with practical options for the responsible team.",
    "Supported onboarding and peer learning through written guides, structured demonstrations, and regular knowledge-sharing sessions across distributed teams.",
    "Translated stakeholder requests into sequenced work, confirmed acceptance details, and maintained progress updates through planning and delivery checkpoints.",
    "Balanced several concurrent assignments, recorded dependencies, and adjusted schedules when scope or operational priorities changed during a reporting period.",
    "Prepared concise monthly summaries, verified source records, and presented trends and unresolved questions to managers for review and follow-up.",
    "Worked with colleagues across business functions to improve handovers, reduce repeated manual steps, and keep service documentation current.",
)
_AR_FILLER = (
    "نسق خطط التسليم الفصلية مع فرق المنتج والتشغيل والدعم، ووثق القرارات وتابع إجراءات المراجعة والإطلاق المتفق عليها.",
    "تابع حوادث التشغيل وسجل أسبابها والإجراءات اللاحقة، وشارك ملاحظات تسليم واضحة تساعد الزملاء على استكمال العمل دون تأخير.",
    "راجع الأعمال الدورية للتأكد من دقتها، وتابع مؤشرات الخدمة، وأبلغ الفريق مبكرا بالمخاطر والخيارات العملية المتاحة.",
    "دعم تعريف الزملاء الجدد من خلال أدلة مكتوبة وعروض منظمة وجلسات منتظمة لتبادل المعرفة بين الفرق.",
    "حول طلبات أصحاب المصلحة إلى خطوات عمل واضحة، وأكد معايير القبول، وحافظ على تحديثات التقدم خلال مراحل التنفيذ.",
    "وازن بين مهام متزامنة، ووثق الاعتماديات، وعدل الجداول عند تغير نطاق العمل أو الأولويات التشغيلية.",
    "أعد ملخصات شهرية موجزة، وتحقق من السجلات المصدرية، وعرض الاتجاهات والأسئلة المفتوحة على المديرين للمراجعة.",
    "تعاون مع وظائف أعمال مختلفة لتحسين التسليم وتقليل الخطوات اليدوية المتكررة وتحديث وثائق الخدمة.",
)


def _profile_for_job(job_key: str) -> dict:
    requirements = {
        "backend": ["Python", "SQL database", "FastAPI", "Docker"],
        "analytics": ["SQL", "Python", "Tableau", "Microsoft Excel"],
    }[job_key]
    return {
        "title": "Senior Backend Engineer" if job_key == "backend" else "Data Analyst",
        "requirements": requirements,
    }


def _synthetic_cv(job_key: str, language: str, category: str, index: int) -> str:
    arabic = language == "arabic"
    filler = _AR_FILLER if arabic else _EN_FILLER
    if job_key == "backend":
        strong = (
            "طورت خدمات خلفية باستخدام Python وFastAPI، وصممت استعلامات SQL وقواعد بيانات علائقية، وشغلت الخدمات داخل Docker."
            if arabic
            else "Designed backend services with Python and FastAPI, optimized SQL relational database queries, and packaged repeatable deployments with Docker."
        )
        partial = (
            "استخدمت Python وDocker في أتمتة مهام داخلية، مع خبرة محدودة في تطوير الخدمات الخلفية."
            if arabic
            else "Used Python and Docker to automate internal tasks, with limited exposure to backend service development."
        )
        unrelated = (
            "أدرت جداول الموظفين وسجلات الحضور وإجراءات التوظيف وخدمات العملاء في بيئة تشغيلية."
            if arabic
            else "Managed employee records, attendance schedules, recruitment administration, and customer-service operations in a business environment."
        )
        skill_core = (
            "Python، SQL، FastAPI، Docker، تصميم واجهات الخدمات، قواعد البيانات، ومراجعة الإصدارات."
            if arabic
            else "Python, SQL databases, FastAPI, Docker, service API design, relational data, and version review."
        )
        partial_skills = (
            "Python, Docker, task automation, technical documentation"
            if not arabic
            else "Python، Docker، أتمتة المهام، التوثيق التقني"
        )
        other_skills = "خدمة العملاء، إدارة السجلات، تنسيق الجداول، إعداد التقارير"
        degree = (
            "بكالوريوس علوم الحاسب، مع مقررات في هندسة البرمجيات ونظم المعلومات."
            if arabic
            else "Bachelor of Computer Science with coursework in software engineering and information systems."
        )
    else:
        strong = (
            "حللت مجموعات بيانات باستخدام SQL وPython، وبنيت لوحات Tableau، وأعددت تقارير دقيقة باستخدام Microsoft Excel."
            if arabic
            else "Analyzed operational datasets with SQL and Python, built Tableau dashboards, and prepared validated reports in Microsoft Excel."
        )
        partial = (
            "استخدمت Microsoft Excel وPython لإعداد تقارير داخلية بسيطة ومتابعة مؤشرات التشغيل."
            if arabic
            else "Used Microsoft Excel and Python for basic internal reports and routine operational tracking."
        )
        unrelated = (
            "أدرت جداول الموظفين وسجلات الحضور وإجراءات التوظيف وخدمات العملاء في بيئة تشغيلية."
            if arabic
            else "Managed employee records, attendance schedules, recruitment administration, and customer-service operations in a business environment."
        )
        skill_core = (
            "SQL، Python، Tableau، Microsoft Excel، تحليل البيانات، تنظيف السجلات، ولوحات المؤشرات."
            if arabic
            else "SQL, Python, Tableau, Microsoft Excel, data analysis, record validation, and dashboard reporting."
        )
        partial_skills = (
            "Python, Microsoft Excel, report preparation, routine tracking"
            if not arabic
            else "Python، Microsoft Excel، إعداد التقارير، متابعة التشغيل"
        )
        other_skills = "خدمة العملاء، إدارة السجلات، تنسيق الجداول، إعداد التقارير"
        degree = (
            "بكالوريوس إدارة الأعمال، مع مقررات في الإحصاء وتحليل المعلومات."
            if arabic
            else "Bachelor of Business Administration with coursework in statistics and information analysis."
        )

    core = strong if category == "strong" else partial if category == "partial" else unrelated
    skills = (
        skill_core
        if category == "strong"
        else partial_skills
        if category == "partial"
        else other_skills
    )
    filler_count = 30 + index % 8
    filler_lines = [filler[(index + offset) % len(filler)] for offset in range(filler_count)]
    midpoint = filler_count // 2
    if arabic:
        experience = "الخبرات العملية\nمحلل / أخصائي أول | 2022-2026\n" + core + "\n"
        experience += "\n".join(filler_lines[:midpoint])
        experience += "\nأخصائي | 2018-2022\n" + core + "\n" + "\n".join(filler_lines[midpoint:])
        skills_section = "المهارات\n" + skills + "\n" + "، ".join(filler[:5])
        education = (
            "التعليم\n"
            + degree
            + "\nدراسة مستمرة في أساليب توثيق العمل وقياس الجودة والتواصل بين الفرق."
        )
        extras = "الشهادات\nتدريب مهني في تخطيط الأعمال والتوثيق والتحقق من الجودة وتحليل مؤشرات الأداء.\nالمشاريع\nمبادرة داخلية لتحسين تسليم المهام وتوحيد التقارير ومتابعة الملاحظات التشغيلية."
        summary = "الملخص\nمتخصص بخبرة عملية في فرق متعددة التخصصات، مع مسؤوليات تشغيلية وتوثيقية وتعاون مستمر مع أصحاب المصلحة."
    else:
        experience = "Experience\nSenior Specialist | 2022-2026\n" + core + "\n"
        experience += "\n".join(filler_lines[:midpoint])
        experience += (
            "\nSpecialist | 2018-2022\n" + core + "\n" + "\n".join(filler_lines[midpoint:])
        )
        skills_section = "Skills\n" + skills + ", " + ", ".join(filler[:5])
        education = (
            "Education\n"
            + degree
            + "\nContinued professional learning in documentation, quality measurement, and cross-team communication."
        )
        extras = "Certifications\nProfessional training in planning, documentation, quality assurance, and performance reporting.\nProjects\nInternal initiative to improve handovers, standardize reports, and track operational feedback."
        summary = "Profile\nExperienced contributor in multidisciplinary teams, with operational, documentation, and stakeholder coordination responsibilities."
    return f"Synthetic profile {index}\n{summary}\n{experience}\n{skills_section}\n{education}\n{extras}"


def synthetic_cohort(job_key: str) -> tuple[list, set[str], dict]:
    from app.services.advisory_preranking_service import CandidateText

    strong_count = APPLICANTS_PER_JOB // 5
    partial_count = (APPLICANTS_PER_JOB * 2) // 5
    candidates = []
    positives = set()
    for index in range(APPLICANTS_PER_JOB):
        category = (
            "strong"
            if index < strong_count
            else "partial"
            if index < strong_count + partial_count
            else "unrelated"
        )
        language = "arabic" if index % 2 else "english"
        identity = f"{job_key}-{index + 1:03d}"
        candidates.append(
            CandidateText(identity, _synthetic_cv(job_key, language, category, index))
        )
        if category == "strong":
            positives.add(identity)
    return candidates, positives, _profile_for_job(job_key)


def cross_language_cases() -> list[tuple[str, list[str], list, set[str]]]:
    """Small known-positive cases for language crossing and Arabic skill aliases."""
    from app.services.advisory_preranking_service import CandidateText

    return [
        (
            "english_job_arabic_cv",
            ["Accountant", "Accounts payable", "Microsoft Excel"],
            [
                CandidateText(
                    "decoy",
                    "Experience\nBuilt data dashboards and analytical pipelines.\n"
                    "Skills\nPython, SQL, Tableau",
                ),
                CandidateText(
                    "strong",
                    "Experience\nعملت محاسبا ماليا وأدرت الحسابات الدائنة وتسوية الفواتير.\n"
                    "Skills\nمحاسب، الحسابات الدائنة، Excel",
                ),
            ],
            {"strong"},
        ),
        (
            "arabic_job_english_cv",
            ["محاسب", "الحسابات الدائنة", "إكسل"],
            [
                CandidateText(
                    "decoy",
                    "Experience\nBuilt data dashboards and analytical pipelines.\n"
                    "Skills\nPython, SQL, Tableau",
                ),
                CandidateText(
                    "strong",
                    "Experience\nWorked as an accountant handling accounts payable and invoice reconciliation.\n"
                    "Skills\nAccountant, accounts payable, Excel",
                ),
            ],
            {"strong"},
        ),
        (
            "accountant_synonym_arabic_cv",
            ["Accountant"],
            [
                CandidateText("decoy", "Experience\nBuilt data dashboards.\nSkills\nPython, SQL"),
                CandidateText("strong", "Experience\nعملت محاسبا ماليا.\nSkills\nمحاسب"),
            ],
            {"strong"},
        ),
    ]


def lexical_rank(
    candidates: list, requirements: list[str], *, bilingual_aliases: bool = True
) -> list[str]:
    """Use the production BM25 lexical ranker and its bilingual aliases by default."""
    from app.services.lexical_preranking_service import rank_lexically

    ranked = rank_lexically(
        requirements,
        candidates,
        timeout_seconds=45,
        bilingual_aliases=bilingual_aliases,
    )
    return [item.identity for item in ranked]


def r_precision(ranked: list[str], positives: set[str]) -> tuple[int, int, float]:
    n = len(positives)
    hits = len(set(ranked[:n]) & positives)
    return hits, n, hits / n if n else 0.0


def validate_analytics_labels(candidates: list, positives: set[str]) -> None:
    """Check known-by-construction target/partial skill separation before ranking."""
    by_id = {candidate.identity: candidate.cv_text.casefold() for candidate in candidates}
    target_terms = ("sql", "python", "tableau", "microsoft excel")
    assert all(all(term in by_id[identity] for term in target_terms) for identity in positives)
    partial = [
        text for identity, text in by_id.items() if "analytics-025" <= identity <= "analytics-072"
    ]
    assert partial and all("tableau" not in text and "sql" not in text for text in partial)


def keyword_stuffing_case() -> tuple[list[str], list, set[str]]:
    from app.services.advisory_preranking_service import CandidateText

    requirements = ["SQL", "Python", "Tableau", "Microsoft Excel"]
    candidates = [
        CandidateText(
            "honest_strong",
            "Experience\nAnalyzed operational datasets with SQL and Python, built Tableau "
            "dashboards, and validated Excel reports for business decisions.\n"
            "Skills\nSQL, Python, Tableau, Microsoft Excel",
        ),
        CandidateText(
            "keyword_stuffer",
            "Experience\nMaintained schedules, filed records, and provided routine office support.\n"
            "Skills\n" + ("SQL Python Tableau Microsoft Excel " * 100),
        ),
    ]
    return requirements, candidates, {"honest_strong"}


def _language(identity: str) -> str:
    index = int(identity.rsplit("-", 1)[1]) - 1
    return "english" if index % 2 == 0 else "arabic"


def _distribution(values: list[float]) -> str:
    return (
        f"min={min(values):.4f},median={statistics.median(values):.4f},"
        f"mean={statistics.mean(values):.4f},max={max(values):.4f}"
    )


def main() -> int:
    from app.services.advisory_preranking_service import (
        MODEL_REVISION,
        OnnxE5Embedder,
        build_candidate_chunks,
        rank_candidates,
        ranking_timeout_for_cohort,
    )
    from app.services.lexical_preranking_service import rank_lexically

    model_dir = Path(os.environ.get("A5_EVAL_MODEL_DIR", BACKEND_DIR / "models/multilingual-e5-small"))
    threads = 1
    embedder = OnnxE5Embedder(
        Path(model_dir) / "model_O4.onnx",
        Path(model_dir) / "tokenizer.json",
        threads=threads,
    )
    print(f"model=intfloat/multilingual-e5-small revision={MODEL_REVISION}")
    print(f"device=CPUExecutionProvider threads={threads} quantized=false")
    selected_jobs = os.environ.get("A5_EVAL_JOBS", "backend,analytics").split(",")
    if any(job not in {"backend", "analytics"} for job in selected_jobs):
        raise ValueError("A5_EVAL_JOBS may contain only backend and analytics.")
    for job_key in selected_jobs:
        candidates, positives, profile = synthetic_cohort(job_key)
        if job_key == "analytics":
            validate_analytics_labels(candidates, positives)
        requirements = profile["requirements"]
        base_timeout = float(os.environ.get("A5_EVAL_BASE_TIMEOUT_SECONDS", "120"))
        max_timeout = float(os.environ.get("A5_EVAL_MAX_TIMEOUT_SECONDS", "1800"))
        timeout = ranking_timeout_for_cohort(
            len(candidates), base_timeout_seconds=base_timeout, max_timeout_seconds=max_timeout
        )

        e5_start = time.process_time()
        e5_ranked = rank_candidates(
            requirements,
            candidates,
            tokenizer=embedder.tokenizer,
            embedder=embedder,
            max_chunks_per_cv=24,
            timeout_seconds=timeout,
        )
        e5_cpu_per_cv = (time.process_time() - e5_start) / len(candidates)
        lexical_start = time.process_time()
        lexical_ranked = rank_lexically(
            requirements, candidates, timeout_seconds=timeout, bilingual_aliases=True
        )
        lexical_cpu_per_cv = (time.process_time() - lexical_start) / len(candidates)

        e5_ids = [item.identity for item in e5_ranked]
        lexical_ids = [item.identity for item in lexical_ranked]
        e5_hits = len(set(e5_ids[:TOP_N]) & positives)
        lexical_hits = len(set(lexical_ids[:TOP_N]) & positives)
        e5_r_hits, n, e5_r_precision = r_precision(e5_ids, positives)
        lexical_r_hits, _, lexical_r_precision = r_precision(lexical_ids, positives)
        word_counts = [len(candidate.cv_text.split()) for candidate in candidates]
        model_token_counts = [
            sum(
                len(embedder.tokenizer.encode(chunk).ids)
                for chunk in build_candidate_chunks(
                    candidate.cv_text, embedder.tokenizer, max_chunks=24
                )
            )
            for candidate in candidates
        ]
        print(
            f"job={profile['title']} applicants={len(candidates)} strong={n} "
            f"strong_per_language=12/12 top_n={TOP_N} labels=synthetic_known_by_construction"
        )
        print(
            f"  cv_words_min_median_max={min(word_counts)}/"
            f"{statistics.median(word_counts):.0f}/{max(word_counts)} "
            f"e5_tokens_min_median_max={min(model_token_counts)}/"
            f"{statistics.median(model_token_counts):.0f}/{max(model_token_counts)}"
        )
        print(
            f"  E5 recall@{TOP_N}={e5_hits}/{n} ({e5_hits / n:.1%}) "
            f"R-precision@{n}={e5_r_hits}/{n} ({e5_r_precision:.1%}) "
            f"CPU_seconds_per_CV={e5_cpu_per_cv:.4f}"
        )
        print(
            f"  lexical_BM25_aliases recall@{TOP_N}={lexical_hits}/{n} "
            f"({lexical_hits / n:.1%}) R-precision@{n}={lexical_r_hits}/{n} "
            f"({lexical_r_precision:.1%}) CPU_seconds_per_CV={lexical_cpu_per_cv:.4f}"
        )
        e5_scores = {item.identity: item.score for item in e5_ranked}
        lexical_scores = {item.identity: item.score for item in lexical_ranked}
        for language in ("english", "arabic"):
            language_positives = {
                identity for identity in positives if _language(identity) == language
            }
            e5_language_hits = len(set(e5_ids[:TOP_N]) & language_positives)
            lexical_language_hits = len(set(lexical_ids[:TOP_N]) & language_positives)
            e5_language_r = len(set(e5_ids[:n]) & language_positives)
            lexical_language_r = len(set(lexical_ids[:n]) & language_positives)
            e5_distribution = [e5_scores[identity] for identity in language_positives]
            lexical_distribution = [lexical_scores[identity] for identity in language_positives]
            print(
                f"  language={language} strong={len(language_positives)} "
                f"E5_recall@{TOP_N}={e5_language_hits}/{len(language_positives)} "
                f"E5_R_hits@{n}={e5_language_r}/{len(language_positives)} "
                f"E5_strong_score_distribution[{_distribution(e5_distribution)}] "
                f"lexical_recall@{TOP_N}={lexical_language_hits}/{len(language_positives)} "
                f"lexical_R_hits@{n}={lexical_language_r}/{len(language_positives)} "
                f"lexical_strong_score_distribution[{_distribution(lexical_distribution)}]"
            )

    print("cross_language_and_synonym_cases=synthetic_known_by_construction")
    for case_id, requirements, candidates, positives in cross_language_cases():
        e5 = rank_candidates(
            requirements,
            candidates,
            tokenizer=embedder.tokenizer,
            embedder=embedder,
            max_chunks_per_cv=24,
            timeout_seconds=30,
        )
        lexical = rank_lexically(
            requirements, candidates, timeout_seconds=30, bilingual_aliases=True
        )
        e5_rank = next(item.rank for item in e5 if item.identity in positives)
        lexical_rank_number = next(item.rank for item in lexical if item.identity in positives)
        print(
            f"  case={case_id} E5_positive_rank={e5_rank} lexical_positive_rank={lexical_rank_number}"
        )

    requirements, candidates, positives = keyword_stuffing_case()
    e5 = rank_candidates(
        requirements,
        candidates,
        tokenizer=embedder.tokenizer,
        embedder=embedder,
        max_chunks_per_cv=24,
        timeout_seconds=30,
    )
    lexical = rank_lexically(requirements, candidates, timeout_seconds=30)
    for ranker_name, ranked in (("E5", e5), ("lexical_BM25", lexical)):
        print(
            f"keyword_stuffing ranker={ranker_name} "
            f"honest_rank={next(item.rank for item in ranked if item.identity in positives)} "
            f"stuffer_rank={next(item.rank for item in ranked if item.identity == 'keyword_stuffer')} "
            f"honest_score={next(item.score for item in ranked if item.identity in positives):.4f} "
            f"stuffer_score={next(item.score for item in ranked if item.identity == 'keyword_stuffer'):.4f}"
        )
    print(
        "ground_truth=synthetic labels known by construction; no real CVs or LLM judgments; "
        "CPU-only measurements on this machine"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
