from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.advisory_preranking_service import OnnxE5Embedder

BACKEND = Path(__file__).resolve().parents[1]
MODEL_DIR = BACKEND / "models/multilingual-e5-small"
REFERENCE = Path(__file__).parent / "fixtures/a5_parity_reference.json"


@pytest.mark.skipif(
    not (MODEL_DIR / "model_O4.onnx").is_file()
    or not (MODEL_DIR / "tokenizer.json").is_file()
    or not REFERENCE.is_file(),
    reason="Pinned model bundle and reference fixture are provisioned outside git.",
)
def test_onnx_embeddings_match_sentence_transformers_reference():
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    embedder = OnnxE5Embedder(MODEL_DIR / "model_O4.onnx", MODEL_DIR / "tokenizer.json", threads=2)
    actual = np.asarray(embedder.embed(reference["texts"]), dtype=np.float32)
    expected = np.asarray(reference["embeddings"], dtype=np.float32)
    maximum_absolute_difference = float(np.max(np.abs(actual - expected)))
    print(f"max_abs_difference={maximum_absolute_difference:.8g}")

    assert reference["model_id"] == "intfloat/multilingual-e5-small"
    assert reference["model_revision"] == "ccc66d3bcd826f577e26b9a4072cc5fe3a7ad6a3"
    assert actual.shape == expected.shape == (3, 384)
    assert maximum_absolute_difference <= 5e-4
