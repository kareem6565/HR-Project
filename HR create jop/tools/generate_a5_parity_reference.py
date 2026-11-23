"""Generate a small synthetic parity fixture using sentence-transformers test tooling."""

from __future__ import annotations

import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "ccc66d3bcd826f577e26b9a4072cc5fe3a7ad6a3"
SAMPLES = [
    "query: Senior backend engineer building Python microservices with PostgreSQL and AWS.",
    "passage: خبرة في بناء خدمات بايثون وقواعد بيانات PostgreSQL على AWS.",
    "query: Candidate with experience in frontend accessibility and React testing.",
]


def main() -> int:
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION, device="cpu")
    vectors = model.encode(
        SAMPLES,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    fixture = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "sentence_transformers_version": __import__("sentence_transformers").__version__,
        "normalize_embeddings": True,
        "texts": SAMPLES,
        "embeddings": vectors.astype("float32").tolist(),
    }
    target = Path(__file__).resolve().parents[1] / "backend/tests/fixtures/a5_parity_reference.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Saved synthetic parity reference to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
