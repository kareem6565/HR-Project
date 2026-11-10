# HERA HR Platform

This workspace contains two applications joined by an HR workspace selector and
signed single sign-on. Both share **one PostgreSQL database**
(`hr_ai_assistant`):

- `HR manager/` — PHP HR, attendance and payroll application. Its tables live in
  the `hr_ops` schema and it is served by Nginx + PHP-FPM in Docker.
- `HR create jop/` — FastAPI recruitment API and React frontend. Recruitment
  tables live in the `public` schema.

The legacy MySQL database (`attendance_db`) was migrated into `hr_ops` with
`HR create jop/tools/migrate_mysql_to_postgres.py` and then removed. Backups of
the legacy databases and XAMPP content are kept in `backups/`; they are local
safety nets and are not needed at runtime. **XAMPP, Apache, and MySQL are not
required.**

## Single sign-on

`HR manager/login.php` is the only interactive login. The recruitment API's
`POST /auth/login` endpoint is disabled unless `ALLOW_LOCAL_LOGIN=true`, so a
password is never checked by the recruitment side. Instead, the PHP session
issues a short-lived HMAC assertion in `launch_recruitment.php`, and the React
frontend exchanges it at `POST /auth/sso/exchange`.

An authenticated HR user receives both `recruiter` and `hr_operations`
workspace roles on the same HERA identity. Recruitment API routes require the
`recruiter` or `admin` role; HR Operations uses the PHP session and its
page-level role checks. If SSO setup or organization association fails,
Recruitment displays an actionable message and denies entry.

Recruitment provides an organization-scoped dashboard and vacancy workflow.
Vacancies begin as drafts; activation requires a complete vacancy and an
HR-approved job profile. Job descriptions can combine manual text, structured
specifications, and retained PDF/DOCX sources. AI profile proposals include
source evidence and uncertainty markers, can be edited by HR, and are never
used for evaluation until approved.

## Local prerequisites

- Docker Desktop / Docker Engine for PostgreSQL 16, Nginx, and PHP-FPM 8.2
- Python 3.11 or newer for the local FastAPI development server
- Node.js and npm supported by the Vite toolchain for the local frontend
- An Ollama Cloud key only when using the real screening provider; fake mode is
  available for offline development

PHP and its PostgreSQL extension are installed inside the `hr_php` container;
no local PHP, Apache, XAMPP, or MySQL installation is used.

## Configure once

1. Copy `HR create jop/backend/.env.example` to
   `HR create jop/backend/.env`. Set a private `JWT_SECRET_KEY`, the same
   random 32+ character value for `HR_SSO_SHARED_SECRET` that will be used in
   PHP, and `HR_SSO_ORGANIZATION_ID` to an existing HERA organization UUID.
   Leave `ALLOW_LOCAL_LOGIN=false`.
2. Copy `HR manager/.env.example` to `HR manager/.env`, then set
   `HERA_SSO_SHARED_SECRET` to that same shared value. Keep
   `HERA_FRONTEND_URL=http://localhost:5174` for the local Vite frontend.
   Docker Compose passes this file to PHP-FPM.
3. Optionally copy `HR create jop/.env.example` to `HR create jop/.env` to
   change published ports or PostgreSQL credentials.

Inside Docker, Compose sets `DB_HOST=postgres` and the PHP connection uses the
`hr_ops` schema. For a direct PHP process outside Docker, the defaults are
`127.0.0.1:5432`, database/user/password `hr_ai_assistant`. Override them with
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, and `DB_SCHEMA`, or with
an optional `HR manager/includes/db.local.php`.

## First-time backend and frontend setup

```powershell
Set-Location "HR create jop\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head

Set-Location "..\frontend\frontend_last"
Copy-Item .env.example .env
npm install
```

`alembic upgrade head` creates/updates both the recruitment tables and the
`hr_ops` schema used by the PHP application. The one-off MySQL migration tool
already ran; it is only needed if restoring from the dump.

Seed the sign-in data (default category, company settings, leave types, and the
accounts). It is idempotent, so running it on an existing database is safe:

```powershell
Set-Location "HR create jop\backend"
.\.venv\Scripts\python.exe ..\tools\seed_hr_manager.py
```

The seeded accounts use employee code `HR001` (HR) and `ADM001`
(system admin) with the password from `HR_SEED_PASSWORD` (default `hr123`).
Change it from the employee management screen before real use.

## Start the services

From `HR create jop/`:

```powershell
tools\start_hera.ps1
```

This starts PostgreSQL, Nginx + PHP-FPM, the FastAPI backend on `:8000`, and the
Vite frontend on `:5174`. To start only HR Manager and PostgreSQL:

```powershell
tools\start_hera.ps1 -InfraOnly
```

The equivalent infrastructure command is:

```powershell
docker compose up -d postgres hr_php hr_web
```

Open `http://localhost/BIC2_Mvp/login.php`. Signing in with an `hr` account
opens the HERA workspace selector. Choose recruitment to enter the React
application without a second login, or choose HR Management to continue in the
PHP application.

Nginx serves the `HR manager/` folder at `/BIC2_Mvp`; its configuration and the
PHP-FPM image are in `HR create jop/docker/hr-manager/`.

The PostgreSQL test suite uses `TEST_DATABASE_URL`, a separate disposable
database. Keep it distinct from `DATABASE_URL`; the test fixture recreates its
tables.
