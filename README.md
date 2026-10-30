# HERA HR Platform

This workspace contains two existing applications joined by an HR workspace
selector and signed single sign-on. Each service keeps its existing database:

- `HR manager/` — PHP HR, attendance and payroll application backed by MySQL.
- `HR create jop/` — FastAPI recruitment API and React frontend backed by PostgreSQL 16.

No tables or database engines are migrated by the integration. The HERA API
creates an organization-scoped recruiter identity in PostgreSQL the first time
an HR manager account enters recruitment. The MySQL HR account remains the
source of truth for password verification and the HR role.

An authenticated HR user receives both `recruiter` and `hr_operations`
workspace roles on the same HERA identity. Recruitment API routes require the
`recruiter` or `admin` role; HR Operations continues to use the PHP/MySQL HR
session and its existing page-level role checks. If SSO setup or organization
association fails, Recruitment displays an actionable message and denies entry.

Recruitment provides an organization-scoped dashboard and vacancy workflow.
Vacancies begin as drafts; activation requires a complete vacancy and an
HR-approved job profile. Job descriptions can combine manual text, structured
specifications, and retained PDF/DOCX sources. AI profile proposals include
source evidence and uncertainty markers, can be edited by HR, and are never
used for evaluation until approved.

## Local prerequisites

- Python 3.11 or newer
- Node.js and npm supported by the Vite toolchain
- Docker Desktop / Docker Engine for PostgreSQL 16
- PHP with PDO MySQL enabled and Apache (for the existing PHP application)
- An existing MySQL `attendance_db` with its HR users
- An Ollama Cloud key only when using the real screening provider; fake mode is
  available for offline development

## Configure once

1. Copy `HR create jop/backend/.env.example` to
   `HR create jop/backend/.env`. Set a private `JWT_SECRET_KEY`, the same
   random 32+ character value for `HR_SSO_SHARED_SECRET` that will be used in
   PHP, and `HR_SSO_ORGANIZATION_ID` to an existing HERA organization UUID.
2. Copy `HR manager/.env.example` to `HR manager/.env`, then set
   `HERA_SSO_SHARED_SECRET` to that same shared value. Keep
   `HERA_FRONTEND_URL=http://localhost:5173` for the local Vite frontend.
3. In Apache, map the `HR manager/` folder to `/BIC2_Mvp`, as expected by the
   existing PHP links, and ensure PHP has `pdo_mysql` enabled. Configure Apache
   to use the local `.env` values or set the two HERA variables in its process
   environment.

## Start the services

Start PostgreSQL from `HR create jop/`:

```powershell
Set-Location "HR create jop"
docker compose up -d postgres
```

Install and run the API:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, install and run React:

```powershell
Set-Location "HR create jop\frontend\frontend_last"
Copy-Item .env.example .env
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

For XAMPP, add this mapping to `C:\xampp\apache\conf\httpd.conf` and restart
Apache so the legacy `/BIC2_Mvp` URLs resolve to this workspace:

```apache
Alias /BIC2_Mvp "E:/HR Project/HR manager"
<Directory "E:/HR Project/HR manager">
    AllowOverride All
    Require all granted
</Directory>
```

Start Apache and the existing MySQL service, then open
`http://localhost/BIC2_Mvp/login.php`. Signing in
with an `hr` account opens the HERA workspace selector. Choose recruitment to
enter the React application without a second login, or choose HR Management to
continue in the existing PHP application.

The PostgreSQL test suite uses `TEST_DATABASE_URL`, a separate disposable
database. Keep it distinct from `DATABASE_URL`; the test fixture recreates its
tables.
