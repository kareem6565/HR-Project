# Storage encryption and candidate retention

## File encryption

The local storage adapter encrypts resume, screening batch, and job-description
files with AES-256-GCM. Ciphertext is authenticated against the organization
UUID, file UUID, and key id. Keep `RESUME_ENCRYPTION_KEYS` in the deployment
secret store as a JSON mapping from key id to base64-encoded 32-byte keys; do
not put key values in the repository. Keep old keys available until all files
encrypted with them have been migrated. `APP_ENV=production` requires
`RESUME_ENCRYPTION_ENABLED=true` and a valid active key at startup. Encrypted
reads require ownership context; plaintext reads fail while encryption is on.

Before enabling encryption for an existing storage directory, configure the
active key and run a preview from `backend/`:

```powershell
python -m tools.migrate_storage_encryption --dry-run
```

For conversion, stop all writers, choose a new backup directory outside both
the repository and storage root, then run:

```powershell
python -m tools.migrate_storage_encryption --backup-dir D:\hera-backups\storage-2026-11 --apply
```

The tool backs up every file and verifies its checksum before replacing any
source. It writes only encrypted temporary copies beside source files, decrypts
them in memory for checksum comparison, and atomically replaces a source only
after verification. If interrupted, rerun with the same backup directory; it
verifies the existing backup and continues. Protect and expire backups under
the organization's backup policy; they retain the original data until expiry.

## Candidate deletion and retention

An admin may set an organization-scoped legal hold with
`PATCH /api/v1/candidates/{candidate_id}/legal-hold` and preview or request
erasure with `POST /api/v1/candidates/{candidate_id}/erase?dry_run=true|false`.
Erasure anonymizes the candidate, removes resume and batch files, extracted
resume text, profiles, evaluations, evidence, and candidate-specific workflow
traces and interview question sets. It clears application contact, portfolio,
and source-attribution data and cancels invitations.
Applications, HR decisions, interview records, consent history, and append-only
audit logs remain connected by internal IDs. Deleting a held candidate is
rejected. Repeating erasure is a no-op.

Retention is **disabled by default**. Set `RETENTION_ENABLED=true` only after
policy review and run the scheduled command from `backend/`:

```powershell
python -m app.cli.retention --dry-run
python -m app.cli.retention --apply
```

The apply command does nothing unless enabled. Each run is capped by
`RETENTION_MAX_DELETIONS_PER_RUN` (default 100); a smaller cap can be supplied
with `--max-deletions`. Organization defaults are 12 months after the latest
rejection without accepted, non-revoked talent-pool consent, and 24 months from
the latest accepted consent grant. Renewing consent restarts that 24-month
window. Candidates with legal holds or any application whose latest HR
decision is not rejection are excluded. Organization admins can configure the
two month values at `/api/v1/organization/retention-policy`; this does not
enable the global retention job.

Deletion audit entries contain candidate and organization IDs plus aggregate
counts only. Extracted text and evidence held in other database columns remain
plaintext and are outside this change. Existing immutable audit records and
interview free-text may already contain personal information and are retained
by the approved scope. Backups can retain erased data until their expiry.
