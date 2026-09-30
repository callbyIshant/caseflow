# CaseFlow

CaseFlow is a customer-service ticketing app for **Northstar Services**, a fictional company. It is a portfolio project with synthetic data; it is not affiliated with a financial institution.

**Live demo:** Not deployed yet. A link will be added after the hosted service passes the documented smoke checks.

## Project status

The project is being implemented in milestones against the [product and technical specification](docs/CASEFLOW_PRODUCT_TECHNICAL_SPEC.md) and [deployment runbook](docs/CASEFLOW_DEPLOYMENT_RUNBOOK.md). Complete: M0 application skeleton and M1 authentication. In progress: M2 customer ticket workflow.

## Architecture

```text
Browser (one origin)
  ├── React + TypeScript + Vite
  └── FastAPI /api/v1 + health + OpenAPI
       ├── Argon2id credentials; opaque sessions and per-session CSRF
       └── PostgreSQL 16
```

Local development runs Vite at `http://localhost:5173` and FastAPI at `http://localhost:8000`; Vite proxies `/api`, `/docs`, `/openapi.json` and `/health` to FastAPI. Production packages the compiled React app into a non-root FastAPI Docker image. PostgreSQL is the only persistent store.

The Compose database maps to host port `5433` to avoid conflicting with a PostgreSQL service already running on the usual `5432` port.

## Requirements

- Docker Engine/Desktop with Compose
- Python 3.12
- Node.js 22.12 or newer
- `uv` 0.12.21 for the locked Python environment (`python -m pip install uv==0.12.21`)

## Run the integrated local stack

From the repository root:

```powershell
docker compose up --build
```

Compose starts local PostgreSQL, runs the one-shot Alembic migration service, then starts the app. Open `http://localhost:8000`. The database is local synthetic development data only. Stop the services with `Ctrl+C`; use `docker compose down` to stop containers while retaining the local database volume.

## Run frontend/backend development servers

Create a local `.env` from `.env.example`, then start PostgreSQL and apply migrations:

```powershell
Copy-Item .env.example .env
docker compose up -d db
Set-Location backend
uv sync --locked --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --app-dir .
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies the API, docs and health checks so browser requests remain same-origin. Do not commit `.env` or use its development-only values in production.

## Quality commands

```powershell
Set-Location backend
uv run ruff check app tests alembic
uv run mypy app
uv run pytest

Set-Location ..\frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Backend integration tests use real PostgreSQL. The GitHub Actions workflow runs backend checks with a PostgreSQL 16 service and builds the production container after frontend/backend checks pass.

## Authentication available in M1

- Customer registration and sign-in at `/register` and `/login`; staff roles cannot be selected at signup.
- A seven-day server-managed session cookie. Only its SHA-256 hash is stored in PostgreSQL; customer mutations need the matching per-session HMAC CSRF token held in browser memory.
- Same-origin validation on all unsafe requests, generic invalid-credential responses, active-account checks, and immediate logout revocation.
- `/api/v1/auth/session` restores browser state after reload; `/api/v1/users/me` returns only the signed-in user's public profile.
- Agent/admin accounts are provisioned out of band with `uv run python -m app.scripts.provision_staff` after the four `CASEFLOW_STAFF_*` values are set securely in the trusted terminal. Public registration rejects privilege fields.

Run `docker compose up --build` to apply migrations and open the integrated app. The local database is disposable development data. Public registration is intended for synthetic portfolio use; email verification and password recovery are not implemented.

## Security and operations

- Production uses one HTTPS origin, server-managed opaque sessions, HttpOnly cookies, CSRF protection and server-side role checks.
- PostgreSQL schema changes are applied with Alembic. The application does not create schema at startup.
- The production database is intended for Neon; Render hosts the Docker web service. No production credentials or live URL are present in this repository yet.
- Do not enter real customer, payment-card or financial account data. Account verification/recovery and persistent distributed abuse controls are future work before real-world use.

See [ADR-001](docs/ADR-001-implementation-clarifications.md) for implementation clarifications and the deployment runbook for the authorized production setup steps.
