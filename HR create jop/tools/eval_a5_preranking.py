"""Measure advisory pre-ranking on a fixed, synthetic-only known-label cohort."""

from __future__ import annotations

import ast
import time
from pathlib import Path

from app.services.advisory_preranking_service import (
    MODEL_REVISION,
    CandidateText,
    OnnxE5Embedder,
    rank_candidates,
)

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
QUALITY_TOOL = Path(__file__).with_name("eval_quality.py")


def synthetic_cohort() -> tuple[list[CandidateText], set[str]]:
    constants = _quality_constants()
    cases = constants["SYNTHETIC_BENCHMARK"]
    candidates = [CandidateText(identity=case["id"], cv_text=case["cv_text"]) for case in cases]
    positives = {case["id"] for case in cases if case["ground_truth_shortlist"]}
    return candidates, positives


def _quality_constants() -> dict:
    tree = ast.parse(QUALITY_TOOL.read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "SYNTHETIC_BENCHMARK",
                    "DEFAULT_JOB_PROFILE",
                }:
                    constants[target.id] = ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in {"SYNTHETIC_BENCHMARK", "DEFAULT_JOB_PROFILE"}:
                constants[node.target.id] = ast.literal_eval(node.value)
    return constants


def main() -> int:
    model_dir = BACKEND_DIR / "models/multilingual-e5-small"
    embedder = OnnxE5Embedder(
        Path(model_dir) / "model_O4.onnx",
        Path(model_dir) / "tokenizer.json",
        threads=2,
    )
    candidates, positives = synthetic_cohort()
    profile = _quality_constants()["DEFAULT_JOB_PROFILE"]
    requirements = [item["text"] for item in profile["requirements"]]
    started = time.perf_counter()
    ranked = rank_candidates(
        requirements,
        candidates,
        tokenizer=embedder.tokenizer,
        embedder=embedder,
        max_chunks_per_cv=24,
        timeout_seconds=600,
    )
    seconds = time.perf_counter() - started
    top_n = 20
    retrieved = {row.identity for row in ranked[:top_n]} & positives
    print(f"model=intfloat/multilingual-e5-small revision={MODEL_REVISION}")
    print("device=CPUExecutionProvider threads=2 quantized=false")
    print(f"synthetic_cvs={len(candidates)} known_strong={len(positives)} top_n={top_n}")
    print(
        f"recall@{top_n}={len(retrieved)}/{len(positives)} ({len(retrieved) / len(positives):.1%})"
    )
    print(f"cpu_seconds_per_cv={seconds / len(candidates):.4f}")
    print("ground_truth=tools/eval_quality.py SYNTHETIC_BENCHMARK (known by construction)")
    if len(candidates) <= top_n:
        print("note=cohort smaller than top_n; recall@N is an upper-bound smoke check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
