# CPU advisory pre-ranking

## What it does

When `A5_PRERANK_ENABLED=true`, the worker runs a cheap CPU embedding pass over
applications for the job, including queued/running items in other screening
batches, and marks the top N (default 20) for the usual AI evidence evaluation.
This rank is advisory only: it never writes the official
score or HR decision. Applicants outside N show **“LLM evaluation not run;
ranking is advisory only”** and remain manually evaluable from their review
page. Pre-ranking never runs inside an HTTP request.

The feature is OFF by default. If its pinned model files are absent, have the
wrong checksum, or the run exceeds its limit, the feature reports an unavailable
status and the worker continues its standard flow. It does not silently fall
back to another model. Embeddings are held in memory only; vectors are not
persisted. The full CV remains visible to HR. Only the minimized text described
below is passed to the ranking model.

## Model and privacy

- Model: `intfloat/multilingual-e5-small`, revision
  `ccc66d3bcd826f577e26b9a4072cc5fe3a7ad6a3`.
- License: MIT. Its model card lists 94 languages, including Arabic, and
  explicitly requires `query:` / `passage:` prefixes and a 512-token input
  limit.
- Portable default: `model_O4.onnx` (235,052,531 bytes) plus `tokenizer.json`
  (17,082,730 bytes); FP32 ONNX export is used for broad CPU compatibility.
- The pinned files are checksum-verified by `tools/fetch_preranker_assets.py`.
  They are excluded from Git by the repository `.gitignore`, so a clean clone
  does not contain the weights. The release build must fetch the pinned files
  before building the backend image; `backend/Dockerfile` then copies
  `backend/models/` into `/app/models/` in the image. A customer deploys that
  complete image, which already contains the verified model and tokenizer.
  For a non-Docker offline install, ship the same
  `models/multilingual-e5-small/` directory beside the backend package and set
  `A5_PRERANK_MODEL_DIR` to that directory. Do not fetch assets on application
  startup or at request time. The application never uses `trust_remote_code`
  or sends CV content to an embedding service.
- `onnxruntime==1.31.0` occupies 48.2 MB installed; the three new direct
  dependencies together occupy 114.5 MB installed in the measured Windows
  environment (`numpy==2.3.4`, `onnxruntime==1.31.0`, `tokenizers==0.23.3`).
  The standard model plus tokenizer occupies 252.1 MB.
- Lighter opt-in model: `model_qint8_avx512_vnni.onnx` (118,346,824 bytes),
  reducing model size by about 116.7 MB. It is accepted only when Linux exposes
  both AVX-512F and AVX-512 VNNI flags. Other platforms fail closed to the
  visible unavailable status; keep `A5_PRERANK_QUANTIZED=false` unless the
  supported CPU capability is verified.
- Sections used: experience, skills, and education only. Name, photo, age,
  gender, marital status, religion, nationality, military-service status, and
  institution/employer names are removed or excluded. Known company/university
  names are stripped with a small English/Arabic rule list; product and tool
  names such as Oracle, SAP, AWS, Excel, and Google Analytics are protected by
  an explicit allow-list. No NLP dependency was added.
- Text is split into chunks no longer than 512 tokenizer tokens, with `passage:`
  and `query:` prefixes. Every job requirement is matched against its best CV
  chunk. The per-CV chunk cap, worker thread count, per-run timeout, and top N
  are configurable. Top N is a job setting, bounded to 1–100.

Name detection is deterministic, not entity recognition. The curated list will
miss unfamiliar or alternate spellings of organizations, and substring rules
can remove a mention that is not an institution. The product allow-list reduces
over-stripping for common tools; keep these limits in mind when reviewing an
advisory rank. Unlabeled personal attributes inside an eligible section may
also evade the field-label filters; common CV headers and non-eligible sections
are excluded, but this is not a replacement for a fairness audit. HR always has
the original CV and makes the final decision.

Two workers may calculate the same job ranking concurrently. Rankings are
deterministic and safe to repeat; in that case the only impact is extra CPU
work.

## Install and enable

Run from `HR create jop/backend` in PowerShell. The lock targets CPython 3.11,
Windows x64 and Linux glibc x86-64:

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-a5.lock
.\.venv\Scripts\python.exe ..\tools\fetch_preranker_assets.py --output models\multilingual-e5-small
```

For a Linux CPU verified to expose AVX-512 VNNI, fetch the smaller model as an
optional additional file:

```powershell
.\.venv\Scripts\python.exe ..\tools\fetch_preranker_assets.py --output models\multilingual-e5-small --include-quantized
```

Build the backend image only after fetching assets so Docker bundles the pinned
files. This is the required customer-image packaging sequence from
`HR create jop`:

```powershell
.\backend\.venv\Scripts\python.exe .\tools\fetch_preranker_assets.py --output .\backend\models\multilingual-e5-small
docker compose build backend
```

The asset script checks the pinned revision and SHA-256 values before writing
the files; the Dockerfile copies those files into `/app/models`. A clean Git
checkout without the fetched assets cannot produce the A5-enabled image, by
design. The release pipeline must retain and publish the resulting image (or
include the verified model directory in its offline installer artifact).
Runtime deployments need no Hugging Face access. The feature still defaults
to OFF. To test locally, set these variables in the backend environment and
restart the worker:

The A5 migration can be checked without touching the app or test database:
`.\.venv\Scripts\python.exe ..\tools\verify_a5_migration.py` creates a
randomly named local PostgreSQL database, verifies upgrade and downgrade, and
drops that throw-away database. The script refuses non-local database hosts.

```powershell
$env:A5_PRERANK_ENABLED = "true"
$env:A5_PRERANK_MODEL_DIR = ".\models\multilingual-e5-small"
$env:A5_PRERANK_THREADS = "2"
$env:A5_PRERANK_MAX_CHUNKS_PER_CV = "24"
$env:A5_PRERANK_TIMEOUT_SECONDS = "45"
$env:A5_PRERANK_QUANTIZED = "false"
```

To opt into the quantized asset on a verified supported Linux worker, set
`A5_PRERANK_QUANTIZED=true`. The currently implemented capability check is
Linux-only and requires both CPU flags; Windows and macOS intentionally remain
on the portable model. Do not enable quantization where flags cannot be
verified.

## Evaluation and parity

`tools/eval_a5_preranking.py` creates two independently labeled cohorts with
120 synthetic applicants each (Senior Backend Engineer and Data Analyst). Each
cohort contains 24 strong candidates known by construction, 48 partial matches,
and 48 unrelated applicants; English and Arabic CVs are balanced. CVs range
from 690–913 words (about 2–3 pages) and 1,193–1,452 E5 input tokens across
their <=512-token chunks. No real CVs or LLM judgments are used.

Run on Windows 11 x64, Intel Core i7-13700HX (16 cores / 24 logical processors),
15.7 GiB RAM, ONNX Runtime 1.31.0, FP32 `model_O4.onnx`, and 2 CPU threads:

| Synthetic job | Recall@20 | CPU seconds/CV | Wall seconds/CV |
|---|---:|---:|---:|
| Senior Backend Engineer | 20/24 (83.3%) | 1.1055 | 0.9634 |
| Data Analyst | 12/24 (50.0%) | 1.2099 | 0.9702 |

These are advisory ranking measurements only. Recall is modest for the Data
Analyst cohort; keep A5 OFF until the owner reviews the results. At roughly
0.97 wall seconds per CV, a 120-applicant pass takes about 116 seconds on this
machine, longer than the current 45-second default timeout. The guard therefore
marks that run unavailable unless the operator deliberately raises the
configurable timeout (up to 600 seconds); it does not return partial results.
Re-measure on customer hardware before enabling the feature for large jobs.

`tests/test_a5_onnx_parity.py` compares the pinned ONNX output against a
`sentence-transformers` reference generated from the same model revision and
synthetic English/Arabic/mixed inputs. The reference tooling is not a runtime
dependency. Maximum absolute difference: **0.00028401613** (limit: 5e-4).

The feature remains disabled until the owner reviews these measurements and
enables the flag in the intended environment.
