# HERA pipeline stages

## Status and stage are separate

`job_applications.status` remains the operational/decision status used by existing
screens and integrations. `pipeline_stage` records HR's recruitment progression.
AI output never changes this stage. A scheduled interview may prompt HR to move an
application to `interview`, but the move requires an HR action.

### Allowed status/stage matrix

The database check constraint and service enforce this matrix:

| Application status | Allowed pipeline stages |
| --- | --- |
| `created`, `analysis_pending`, `analyzing`, `analysis_failed`, `ready_for_review`, `hold`, `advanced` | `screening`, `review`, `interview`, `offer`, `hired`, `withdrawn` |
| `rejected` | `rejected` only |
| `archived` | `archived` only |

HR rejection is recorded through the existing HR decision endpoint and atomically
adds a `review`/current-stage → `rejected` transition. Archiving is an explicit
stage transition; it sets both `status` and `pipeline_stage` to `archived`.

## Legacy backfill mapping (migration 034)

| Existing status | Initial stage |
| --- | --- |
| `created` | `screening` |
| `analysis_pending` | `screening` |
| `analyzing` | `screening` |
| `analysis_failed` | `screening` |
| `ready_for_review` | `review` |
| `advanced` | `interview` if an interview record exists; otherwise `review` |
| `hold` | `interview` if an interview record exists; otherwise `review` |
| `rejected` | `rejected` |
| `archived` | `archived` |

The existence of any interview record is the only legacy evidence used to infer
`interview`; `advanced` by itself never implies an interview. The migration inserts
one initial row per application with `source="migration"`, `from_stage=NULL`, and
`reason_code="migration_baseline"`. Its UTC timestamp means “baseline recorded by
this migration”, not a historical stage-change timestamp. Backfill runs in bounded
batches. Unknown statuses stop the migration.

Run a read-only count preflight before upgrade:

```powershell
Set-Location "HR create jop/backend"
.\.venv\Scripts\python.exe tools\migrate_pipeline_stages.py --dry-run
```

## Transition policy

| Current stage | Normal next stages |
| --- | --- |
| `screening` | `review`, `withdrawn`, `archived` |
| `review` | `screening`, `interview`, `withdrawn`, `archived` |
| `interview` | `review`, `offer`, `withdrawn`, `archived` |
| `offer` | `interview`, `hired`, `withdrawn`, `archived` |
| `hired` | none; final in the normal flow |
| `rejected` | `archived` |
| `withdrawn` | `archived` |
| `archived` | none |

Rejection remains an explicit HR decision, not a generic stage-picker action.
Withdrawn and backward transitions require a reason code. Optional free-text notes
are limited to 500 characters, treated as sensitive, omitted from API history, and
scrubbed during candidate anonymization. Admins may correct a `hired` stage to a
prior stage only with a reason code and mandatory reason; both stages are logged.

The hired correction changes only recruitment pipeline state. When H3 later creates
an employee record, this correction must not delete or silently roll back that
employee; H3 needs an explicit coordinated employee correction workflow.

## API and concurrency

- `GET /api/v1/job-applications/{id}/pipeline` returns the current stage, allowed
  next stages, admin-correction availability, and recent transition metadata.
- `POST /api/v1/job-applications/{id}/pipeline-transitions` requires
  `expected_stage`, `to_stage`, and a UUID `idempotency_key`. The server checks the
  stage graph, same-organization HR role, and status/stage matrix.
- `POST /api/v1/job-applications/{id}/pipeline-corrections` is admin-only and
  requires `expected_stage="hired"`, `to_stage`, `reason_code`, and a non-empty
  reason.
- Transitions use row locking plus a compare-and-set update. An idempotency key is
  unique per organization/application/actor; identical retries return the original
  transition without adding another row. A competing stale transition receives 409.
- Transition history stores identifiers, stage values, reason code, source and UTC
  timestamp. Actor foreign keys are nullable with `ON DELETE SET NULL`; the history
  index begins `(organization_id, job_application_id, created_at)`. Notes are not
  returned by the history API and are cleared when candidate data is anonymized.
- The permission decision is centralized in `authorize_pipeline_action`; future H4
  roles should extend this policy rather than adding route-specific checks.
