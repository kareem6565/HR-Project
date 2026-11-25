# HERA Deployment Guide

How to take the HERA recruitment platform (this directory, `HR create jop/`) from
the repo to a running production instance. Written for the team as a reference;
follow it when the current round of edits is done and you are ready to launch.

Stack overview:

| Piece | Tech | Default port | What it does |
| --- | --- | --- | --- |
| Backend | FastAPI (Python 3.11), Uvicorn | 8000 | API, screening worker, outbox worker |
| Frontend | React + Vite, served by Nginx | 8080 (prod) / 5174 (dev) | The HERA web app |
| Database | PostgreSQL 16 | 5432 | All state, migrations via Alembic |
| HR Manager (optional) | PHP + Nginx | 80 | Legacy HR ops UI, SSO entry point |

Everything except external services runs from the root `docker-compose.yml`.

---

## 1. Pick a hosting path

### Option A - one cheap VPS (recommended, simplest)

One small VM runs everything via Docker Compose.

- Hetzner CX22 (~EUR 4/mo), DigitalOcean Basic Droplet ($6/mo), or Oracle Cloud
  Always Free ARM VM ($0).
- Minimum: 2 vCPU, 4 GB RAM, 40 GB disk, Ubuntu 24.04.
- Install Docker + the compose plugin, clone the repo, point a DNS A record at
  the VM, done (section 2-4 below).

Monthly cost: $0-6 plus whatever AI provider you use (see section 5).

### Option B - free-tier split hosting

If no one wants to pay for a VM yet:

- **Database:** Neon or Supabase free Postgres (500 MB). Copy the connection
  string into `DATABASE_URL`.
- **Backend:** Render or Railway free/low tier as a Docker service from
  `backend/Dockerfile`. The container runs `alembic upgrade head` on start, so
  the schema migrates itself. Set every backend env var from section 4 in the
  provider dashboard. Free tiers sleep when idle, so the first request after a
  quiet period is slow; keep the screening worker in mind (it polls, so a
  sleeping service delays screening - on Render use a "worker" instance type or
  accept the delay).
- **Frontend:** Vercel, Netlify, or Cloudflare Pages. Build
  `frontend/frontend_last` with `VITE_API_BASE_URL=https://<your-backend>/api/v1`
  and `VITE_TURNSTILE_SITE_KEY` set, publish the `dist` output, and proxy
  `/api/v1` to the backend (or set the full backend URL and configure CORS).

Monthly cost: $0 with free-tier limits (sleeps, small DB).

### What NOT to use

Shared PHP hosting can run the HR Manager but not the FastAPI backend or
Postgres properly. The Python backend needs a real VM or container host.

---

## 2. Server setup (Option A)

```bash
# on the VM
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # log out/in once

git clone <repo-url> hera && cd hera/"HR create jop"
```

Copy and edit the backend environment:

```bash
cp backend/.env.example backend/.env
nano backend/.env   # fill in every value from section 4
```

## 3. Run it

```bash
docker compose up -d --build
docker compose ps                 # all services should be "healthy"
curl http://localhost:8000/api/v1/health
```

- The backend container runs `alembic upgrade head` automatically on every
  start, so first boot creates the whole schema (current head:
  `031_sourcing_contact`).
- Frontend: `http://<server>:8080` (set `FRONTEND_PORT` to change it).
- API docs: `http://<server>:8000/docs`.
- Resume uploads land in `backend/storage/` inside the container; mount a
  volume there if you want them on the host disk.
- The PHP HR Manager (`hr_php` + `hr_web`) is part of the compose file. If you
  are not using it yet, run only the app: `docker compose up -d postgres
  backend frontend`.

Put Nginx or Caddy in front for HTTPS (Caddy is the fastest path: one
`caddy reverse-proxy --from app.yourdomain.com --to localhost:8080` line gets
you a cert). Set `FRONTEND_BASE_URL` and `TURNSTILE_EXPECTED_HOSTNAME` to the
real domain.

## 4. Production environment checklist (backend/.env)

The backend validates config at startup and **refuses to boot in production**
with weak secrets, so set these deliberately:

| Variable | Production value | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | Turns on strict validation |
| `JWT_SECRET_KEY` | 32+ char random secret | `openssl rand -hex 32`; weak values block startup |
| `DATABASE_URL` | real Postgres URL | compose default is fine for Option A |
| `CORS_ALLOW_ORIGINS` | `["https://app.yourdomain.com"]` | exact frontend origin(s) |
| `FRONTEND_BASE_URL` | `https://app.yourdomain.com` | used in links |
| `AI_PROVIDER` + matching key | e.g. `openrouter` + `OPENROUTER_API_KEY` | see cost limits below |
| `AI_GLOBAL_RPM_LIMIT` / `AI_GLOBAL_DAILY_LIMIT` / `AI_USER_*` | keep or tighten | hard caps so a busy day cannot run up the bill |
| `AI_PAID_MODE_ENABLED` / `AI_PAID_BUDGET_USD` | only if using paid models | budget cap in USD |
| `APPLICATION_PRIVACY_NOTICE_TEXT` | your real privacy notice | shown on the public application form |
| `APPLICATION_PRIVACY_NOTICE_VERSION` | e.g. `v1-2026-11` | bump whenever the text changes |
| `APPLICATION_PRIVACY_NOTICE_APPROVED` | `true` | **production refuses public applications until this is true** |
| `TURNSTILE_REQUIRED` | `true` | spam protection on the public form |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret | free from cloudflare.com -> Turnstile |
| `TURNSTILE_EXPECTED_HOSTNAME` | `app.yourdomain.com` | must match the site key's domain |
| `PUBLIC_APPLICATION_RATE_LIMIT` / `..._WINDOW_SECONDS` | `5` / `3600` | per-IP submissions per hour, persisted in DB |
| `ENABLE_SCREENING_WORKER` | `true` | without it applications arrive but never screen |
| `GOOGLE_TOKEN_ENCRYPTION_KEY` | 32+ char secret | required in production if Calendar is used |
| `GOOGLE_OAUTH_*` | real OAuth client | needed for interview scheduling on real calendars |
| `GOOGLE_CALENDAR_MODE` | `google` | `hera` is a dev fallback with warnings |
| `ALLOW_LOCAL_LOGIN` | `false` normally | `true` gives a direct email/password login - useful as a break-glass while HR Manager SSO is not wired |
| `HR_SSO_SHARED_SECRET` / `HR_SSO_ORGANIZATION_ID` | shared with the PHP HR Manager | required if HR Manager is the login entry point |
| `APIFY_API_TOKEN` | your Apify token | only if using job import / sourcing |
| `APIFY_IMPORT_ENABLED` | `true` only with a token set | LinkedIn job import |
| `APIFY_SOURCING_ENABLED` | `true` only with a token set | candidate sourcing (see section 6) |

Frontend env (build-time, `frontend/frontend_last/.env` or compose/Docker
args):

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` behind one domain, or `https://api.yourdomain.com/api/v1` |
| `VITE_TURNSTILE_SITE_KEY` | the public site key matching `TURNSTILE_SECRET_KEY` |

## 5. AI provider and cost guardrails

Screening, extraction, outreach personalization, and the chatbot all call an
LLM through one OpenAI-compatible provider setting. Cheapest sane defaults:

- `AI_PROVIDER=openrouter` with `OPENROUTER_MODEL=openrouter/free` costs $0 at
  low volume and is what the repo defaults to.
- The `AI_*_LIMIT` env vars are real enforcement, not decoration - set them so
  the whole platform cannot exceed your daily budget even if someone batch
  uploads 200 CVs.
- `AI_PAID_MODE_ENABLED=false` (default) keeps paid models off entirely.

## 6. Sourcing features (Apify)

The sourcing stack (LinkedIn profile search, per-profile email enrichment,
outreach drafts) is off until `APIFY_SOURCING_ENABLED=true` with
`APIFY_API_TOKEN` set.

- Only no-login/public-index Apify actors are used (search:
  `harvestapi/linkedin-profile-search`, enrichment:
  `harvestapi/linkedin-profile-scraper`). Do not switch to cookie/account
  scrapers.
- Enrichment costs about $10 per 1,000 profiles in email-search mode; plain
  profile details about $4 per 1,000.
- Before production/revenue use, the plan is to move to a licensed data
  provider (Coresignal recommended) and purge dev-time scraped data.

## 7. Public application links - go-live checklist

The publish -> public link -> apply -> screening loop is implemented and
covered by tests. Before announcing a public link, verify on the live server:

1. `APPLICATION_PRIVACY_NOTICE_APPROVED=true` with final text and version -
   production rejects public applications without it.
2. `TURNSTILE_REQUIRED=true`, secret set, and the site key's domain matches
   `TURNSTILE_EXPECTED_HOSTNAME`.
3. Alembic head applied (the rate-limit table ships in the migrations; the
   container auto-migrates on start).
4. Screening worker running (`ENABLE_SCREENING_WORKER=true`; it is the default
   and runs inside the backend process).
5. Do one real run: publish a job, open its `/careers/<publicId>` link in an
   incognito window, submit a real application, and watch it appear in the
   pipeline.

## 8. After deploy

- Health: `GET /api/v1/health`.
- Logs: `docker compose logs -f backend` (JSON logs, one line per event).
- Backups: `docker exec hr_ai_assistant_postgres pg_dump -U hr_ai_assistant
  hr_ai_assistant > backup-$(date +%F).sql` nightly via cron is enough at this
  scale.
- Upgrades: `git pull && docker compose up -d --build` - migrations run on
  boot.
