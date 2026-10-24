# HERA HR Manager

This PHP application retains its existing MySQL database (`attendance_db`). It
can be used alongside the HERA recruitment service in `../HR create jop`, which
retains PostgreSQL. The two databases remain service-owned and are not copied
or merged.

## HR workspace sign-in

After a user with the `hr` role signs in, `workspace.php` offers HR Management
and Recruitment. Recruitment uses a short-lived HMAC-signed assertion that is
exchanged by the HERA API for a recruiter session. The API creates a stable,
organization-scoped internal user record in PostgreSQL; the MySQL account
remains authoritative for password and HR role checks.

Configure these values in the PHP environment (for local XAMPP, Apache's
environment configuration is one option):

- `HERA_SSO_SHARED_SECRET`: random secret of at least 32 characters. It must
  exactly match `HR_SSO_SHARED_SECRET` in `HR create jop/backend/.env`.
- `HERA_FRONTEND_URL`: recruitment frontend URL, such as
  `http://localhost:5173` for Vite.
- `HERA_SSO_ISSUER`: assertion issuer; it must match the API's
  `HR_SSO_ISSUER` (default `hr-manager`).

Also set `HR_SSO_ORGANIZATION_ID` in the HERA backend to the UUID of an existing
organization. The backend must have its own `JWT_SECRET_KEY` configured as
usual. Do not commit local environment files or signing secrets.

The manager login and legacy pages assume the Apache document root maps this
folder to `/BIC2_Mvp`, matching the existing application links.
