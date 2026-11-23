"""Measure advisory pre-ranking on a fixed, synthetic-only known-label cohort."""

# Synthetic CV prose remains as complete, readable sentences in the fixture templates.
# ruff: noqa: E501

from __future__ import annotations

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


def main() -> int:
    from app.services.advisory_preranking_service import (
        MODEL_REVISION,
        OnnxE5Embedder,
        build_candidate_chunks,
        rank_candidates,
    )

    model_dir = BACKEND_DIR / "models/multilingual-e5-small"
    embedder = OnnxE5Embedder(
        Path(model_dir) / "model_O4.onnx",
        Path(model_dir) / "tokenizer.json",
        threads=2,
    )
    print(f"model=intfloat/multilingual-e5-small revision={MODEL_REVISION}")
    print("device=CPUExecutionProvider threads=2 quantized=false")
    for job_key in ("backend", "analytics"):
        candidates, positives, profile = synthetic_cohort(job_key)
        requirements = profile["requirements"]
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        ranked = rank_candidates(
            requirements,
            candidates,
            tokenizer=embedder.tokenizer,
            embedder=embedder,
            max_chunks_per_cv=24,
            timeout_seconds=600,
        )
        cpu_seconds = time.process_time() - started_cpu
        wall_seconds = time.perf_counter() - started_wall
        retrieved = {row.identity for row in ranked[:TOP_N]} & positives
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
            f"job={profile['title']} synthetic_applicants={len(candidates)} "
            f"known_strong={len(positives)} top_n={TOP_N}"
        )
        print(
            f"  cv_words_min_median_max={min(word_counts)}/"
            f"{statistics.median(word_counts):.0f}/{max(word_counts)} "
            f"model_tokens_min_median_max={min(model_token_counts)}/"
            f"{statistics.median(model_token_counts):.0f}/{max(model_token_counts)}"
        )
        print(
            f"  recall@{TOP_N}={len(retrieved)}/{len(positives)} "
            f"({len(retrieved) / len(positives):.1%})"
        )
        print(
            f"  cpu_seconds_per_cv={cpu_seconds / len(candidates):.4f} "
            f"wall_seconds_per_cv={wall_seconds / len(candidates):.4f}"
        )
    print(
        "ground_truth=synthetic cohort labels, known by construction; no real CVs or LLM judgments"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
