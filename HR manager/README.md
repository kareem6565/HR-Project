# HERA HR Manager

This PHP application stores its data in the `hr_ops` schema of the HERA
PostgreSQL database (`hr_ai_assistant`). It is used alongside the HERA
recruitment service in `../HR create jop`, which keeps its own tables in the
`public` schema of the same database. The old MySQL `attendance_db` has been
migrated and removed.

## Runtime

Nginx and PHP-FPM 8.2 serve the application from Docker. **XAMPP, Apache,
MySQL, and a local PHP installation are not required.** Start HR Manager and
PostgreSQL with:

```powershell
Set-Location "../HR create jop"
tools\start_hera.ps1 -InfraOnly
```

Or start the containers directly:

```powershell
docker compose up -d postgres hr_php hr_web
```

Open `http://localhost/BIC2_Mvp/login.php`. The Nginx and PHP-FPM configuration
lives in `../HR create jop/docker/hr-manager/`.

## Database connection

`includes/db.php` uses an environment-driven PDO PostgreSQL connection. Docker
Compose supplies `DB_HOST=postgres`; these are the defaults for a direct PHP
process outside Docker:

| Variable    | Default           |
| ----------- | ----------------- |
| `DB_HOST`   | `127.0.0.1`       |
| `DB_PORT`   | `5432`            |
| `DB_NAME`   | `hr_ai_assistant` |
| `DB_USER`   | `hr_ai_assistant` |
| `DB_PASS`   | `hr_ai_assistant` |
| `DB_SCHEMA` | `hr_ops`          |

An optional `includes/db.local.php` can define the same constants. Each
connection runs `SET search_path TO "hr_ops", public`.

## Schema changes

The `hr_ops` schema is managed by Alembic revision `020_hr_ops_schema`. Apply
schema changes from the backend:

```powershell
Set-Location "../HR create jop/backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

`setup.php` and the `update_db*.php` installers are retired and return HTTP 410
so they can never run MySQL DDL against PostgreSQL.

## HR workspace sign-in

After a user with the `hr` role signs in, `workspace.php` offers HR Management
and Recruitment. Recruitment uses a short-lived HMAC-signed assertion that is
exchanged by the HERA API for a recruiter session. The API creates a stable,
organization-scoped internal user record in PostgreSQL; the `hr_ops` account
remains authoritative for password and HR role checks.

Docker Compose loads the local `.env` file into PHP-FPM. Configure:

- `HERA_SSO_SHARED_SECRET`: random secret of at least 32 characters. It must
  exactly match `HR_SSO_SHARED_SECRET` in `HR create jop/backend/.env`.
- `HERA_FRONTEND_URL`: recruitment frontend URL, such as
  `http://localhost:5174` for Vite.
- `HERA_SSO_ISSUER`: assertion issuer; it must match the API's
  `HR_SSO_ISSUER` (default `hr-manager`).

Also set `HR_SSO_ORGANIZATION_ID` in the HERA backend to the UUID of an existing
organization. The backend must have its own `JWT_SECRET_KEY` configured as
usual. Do not commit local environment files or signing secrets.

Nginx maps this folder to `/BIC2_Mvp`, matching the existing application links.

## Email sign-in

The `users.email` column is part of the `hr_ops` schema. Accounts with an email
use the email form; accounts without one can keep using the temporary **legacy
employee-code** option. Add each current user's real email from the employee
management screen; new employee accounts require a unique email.
