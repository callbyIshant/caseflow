# CaseFlow — Deployment and Live-Link Runbook

**Goal:** Deliver one verified HTTPS URL for the compiled React frontend and versioned FastAPI backend; persist tickets in managed PostgreSQL. This runbook supplements the full product/technical spec.

**Provisioning status:** This document is a recipe. It does **not** mean a GitHub repository, hosted application, public domain or provider account has already been created. A real link exists only after code is implemented, pushed and the authorized cloud deployment succeeds.

## 1. Architecture

```text
GitHub main + green CI
          |
          +--> production Alembic migrations (GitHub secret -> Neon direct PostgreSQL)
          |
          +--> Render deploy hook (GitHub secret)
                     |
              Render Docker web service
              React built as static assets and served by FastAPI
              GET /               frontend
              GET /demo           synthetic read-only demo
              /api/v1/*           live backend
              /health/ready       DB-readiness health check
              GET /docs           OpenAPI documentation
                     |
                     +------> Neon PostgreSQL (pooled runtime URL)
```

No Vercel or separate frontend hosting is needed. Browser API calls use relative `/api/v1`, so frontend and backend share a single origin. Public demo uses local frontend fixtures and does not expose editable shared accounts.

## 2. Account/config prerequisites

- A GitHub repository the developer is authorized to push to.
- Render account authorized to create a Docker web service, free plan if available.
- Neon account authorized to create a PostgreSQL database/project.
- Project code from the complete spec, not just these docs.
- Trusted local machine or protected CI environment to hold DB migration URL.

Use **separate** local/test DB and production Neon DB. Prefer nearby Neon/Render regions when available. Read current plan limits before activating paid services or adding payment methods. This guide never requires pasting cloud secrets into a public issue, README or AI chat.

## 3. Expected environment variables

| Variable | Local dev | Production in Render | Required purpose |
|---|---|---|---|
| `ENV` | `development` | `production` | Controls fail-closed config and cookie mode. |
| `PUBLIC_APP_URL` | `http://localhost:5173` in Vite mode | Real HTTPS Render origin | Origin and canonical app URL. |
| `ALLOWED_ORIGIN` | `http://localhost:5173` | Same Render HTTPS origin | Rejects cross-origin unsafe browser requests. |
| `DATABASE_URL` | Local Postgres psycopg DSN | Neon **pooled** psycopg DSN | App runtime DB. |
| `DATABASE_URL_DIRECT` | Local Postgres DSN | **Do not need on Render runtime**; GitHub secret instead | Alembic migration DB. |
| `CSRF_SECRET` | Random local-only dev value | Render generated cryptographically strong secret | HMAC per-session CSRF tokens. |
| `SESSION_TTL_HOURS` | `168` | `168` | Seven-day absolute sessions. |
| `COOKIE_SECURE` | `false` for localhost HTTP | `true` | Secure cookies on public HTTPS. |
| `COOKIE_NAME` | `caseflow_dev_session` | `__Host-caseflow_session` | Host-only production cookie. |
| `LOG_LEVEL` | `DEBUG` or `INFO` | `INFO` | Redacted structured logs. |
| `ALLOW_DEMO_SEED` | `false` by default | `false` | Prevent accidental dangerous DB seeding. |

The server must fail to start in production if `CSRF_SECRET` is missing or insecure, `DATABASE_URL` is missing or the public origin isn't HTTPS. Do not print env values during debugging. Alembic should need only its database setting, not application session secrets.

## 4. Project files the coding agent must deliver

```text
Dockerfile
.dockerignore
compose.yaml
render.yaml
.env.example
backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/*.py
backend/app/main.py
frontend/package.json
frontend/package-lock.json
frontend/vite.config.ts
.github/workflows/ci.yml
.github/workflows/deploy.yml
README.md
docs/DEPLOYMENT.md
```

The source tree and exact settings module are in the product/technical spec.

## 5. Reference multistage Dockerfile

This is a **deployment template**; ensure package-manager/lock-file names and paths match the actual built repository. If using a different dependency manager, rewrite both build and CI consistently.

```dockerfile
# frontend build
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# backend runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY --chown=app:app backend/ /app/backend/
COPY --from=frontend-build --chown=app:app /src/frontend/dist/ /app/backend/app/static/
WORKDIR /app/backend
USER app
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Important:** `requirements.txt` above must be generated from the project's reproducible dependency workflow and committed intentionally. Don't hand-write unpinned ranges for deploys if a lock file is available. Add a proper `.dockerignore`, use an image-security scan where practical and test the compiled SPA fallback routes in the built image.

## 6. Recommended Render Blueprint

```yaml
services:
  - type: web
    name: caseflow-portfolio
    runtime: docker
    plan: free
    region: frankfurt
    dockerfilePath: ./Dockerfile
    dockerContext: .
    autoDeployTrigger: off
    healthCheckPath: /health/ready
    envVars:
      - key: ENV
        value: production
      - key: COOKIE_SECURE
        value: "true"
      - key: COOKIE_NAME
        value: __Host-caseflow_session
      - key: SESSION_TTL_HOURS
        value: "168"
      - key: LOG_LEVEL
        value: INFO
      - key: CSRF_SECRET
        generateValue: true
      - key: DATABASE_URL
        sync: false
      - key: PUBLIC_APP_URL
        sync: false
      - key: ALLOWED_ORIGIN
        sync: false
```

Check current available free plan and regions. Exact `PUBLIC_APP_URL`/`ALLOWED_ORIGIN` can be set after obtaining Render's real service hostname; then redeploy. `sync:false` prompts for secrets only during initial Blueprint creation; update existing services in the Render dashboard. Render Blueprint doesn't interpolate env variables, so enter both exact origin values explicitly.

Render's free Docker web-service filesystem is ephemeral and its free service may sleep after inactivity; never store the application's SQLite data, uploads or long-lived session state in its local filesystem.

## 7. Local Docker Compose template

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: caseflow
      POSTGRES_PASSWORD: caseflow   # LOCAL DEVELOPMENT ONLY
      POSTGRES_DB: caseflow
    ports: ["5432:5432"]
    volumes:
      - local_pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U caseflow -d caseflow"]
      interval: 5s
      timeout: 5s
      retries: 15

  app:
    build: .
    environment:
      ENV: development
      PUBLIC_APP_URL: http://localhost:8000
      ALLOWED_ORIGIN: http://localhost:8000
      DATABASE_URL: postgresql+psycopg://caseflow:caseflow@db:5432/caseflow
      DATABASE_URL_DIRECT: postgresql+psycopg://caseflow:caseflow@db:5432/caseflow
      CSRF_SECRET: local-compose-only-random-placeholder-change-before-shared-use
      COOKIE_SECURE: "false"
      COOKIE_NAME: caseflow_dev_session
    ports: ["8000:8000"]
    depends_on:
      db:
        condition: service_healthy

volumes:
  local_pg:
```

For local Vite development, run backend and frontend as separate processes, point backend to localhost DB, and set `PUBLIC_APP_URL`/`ALLOWED_ORIGIN` to `http://localhost:5173` to match the Vite proxy browser origin. For local production-like Docker Compose, the compiled frontend is at `http://localhost:8000`, so allowed origin differs correctly. The checked-in Compose password is deliberately local-only; don't reuse it for Neon.

Recommended initial local commands, after the app is implemented:

```bash
# From repository root
cp .env.example .env          # fill local only; never commit .env
docker compose up -d db
docker compose build app
docker compose run --rm app alembic upgrade head
docker compose up -d app
curl -f http://localhost:8000/health/ready
```

If using host backend/Vite rather than full Docker, install dependencies, run Alembic using host-local DB URL, start backend on port 8000 and Vite on port 5173; confirm proxy and cookie behavior.

## 8. First production deploy: authoritative order

**Step A — Develop and verify locally.** Run all tests and production Docker build. Run a clean migration against an empty local PostgreSQL DB. Verify local end-to-end flows and read-only demo.

**Step B — Push to GitHub.** Commit only source, dependency lock files, migrations, public fixtures and docs. Confirm `.env`, real passwords, database URLs and deploy-hook URLs are not tracked and not present in earlier commits. CI must be green.

**Step C — Create Neon database.** Choose nearest available region. Copy Neon direct and pooled connection strings privately into authorized config. For SQLAlchemy+psycopg use `postgresql+psycopg://...` preserving `sslmode=require` where appropriate. Keep pooled runtime connection in Render and direct migration URL in secure terminal / GitHub secret.

**Step D — Apply initial production migration.** From trusted environment:

```bash
# Enter actual values securely in your terminal environment, not in docs or Git
cd backend
# DATABASE_URL_DIRECT must already be securely set
alembic upgrade head
alembic current
```

Migrations should use direct URL only in `alembic/env.py`, while app uses runtime pooled `DATABASE_URL`. If production migration fails, **do not create/deploy an app that assumes those tables exist**. Fix/rollback appropriately.

**Step E — Create Render Docker web service.** Connect GitHub repo, load `render.yaml` or equivalent dashboard settings, select Docker + available plan/region; configure required Render secrets. Obtain the actual generated hostname. Enter it as exact `https://...` for both public origin variables if not known during creation. Deploy/redeploy until logs show success and `/health/ready` works.

**Step F — Test actual URL.** In a fresh browser window open landing + `/demo`; verify `/docs`; register fictional account; create/reply; verify private tester agent claim/respond; refresh nested SPA route; restart/redeploy and confirm ticket persists. Inspect cookies for correct production flags and ensure no secrets in client JS or logs.

**Step G — Wire automatic deployments.** Render auto deploy OFF; create Render deploy hook in service settings and put URL in GitHub secret `RENDER_DEPLOY_HOOK_URL`. Add direct Neon migration connection under `PROD_DATABASE_URL_DIRECT` secret. Configure gated GitHub workflow and protect production environment if supported. Never expose these values in README.

**Step H — README.** Add **actual** public origin as live demo link only after Step F; add screenshots and free-tier cold-start note.

## 9. Reference GitHub Actions deploy-stage pseudocode

The coding agent should create a complete `deploy.yml` with `backend-tests`, `frontend-tests`, optional container build, and a gated `deploy` job on `push: main`. The following is a focused template of the **deploy job**, not a standalone complete workflow:

```yaml
# Within .github/workflows/deploy.yml, after required test jobs
  deploy:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    needs: [backend-tests, frontend-tests]
    runs-on: ubuntu-latest
    environment: production
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4  # pin to verified current release/SHA in actual repo
      - uses: actions/setup-python@v5  # pin to verified current release/SHA in actual repo
        with:
          python-version: '3.12'
      - name: Install migration dependencies
        working-directory: backend
        run: pip install -r requirements.txt
      - name: Apply production migrations
        working-directory: backend
        env:
          DATABASE_URL_DIRECT: ${{ secrets.PROD_DATABASE_URL_DIRECT }}
          ENV: migration
        run: alembic upgrade head
      - name: Trigger Render deploy
        env:
          DEPLOY_HOOK: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}
        run: |
          test -n "$DEPLOY_HOOK"
          curl --fail --silent --show-error --request POST "$DEPLOY_HOOK" >/dev/null
```

This is illustrative; the agent must implement separate real test jobs and choose current supported action versions. Render's hook success means a deploy was **triggered**, not necessarily completed. To verify the deployed revision, check Render deployment status through authenticated provider API/dashboard and then run public smoke tests; polling `/health/ready` alone could still hit the previous healthy revision during rollout.

**Why not Render `preDeployCommand`?** At the time of this spec, Render's pre-deploy command is a paid-service feature. The recommended free-tier architecture runs migrations from guarded CI before triggering the Render deployment, rather than relying on an unavailable free-tier feature.

**Migration compatibility warning:** During zero-downtime deploys, old and new app versions can briefly coexist. Apply additive/backward-compatible migrations first; avoid breaking old code before new deployment is fully live. For a portfolio demo, explicitly document this choice and limit high-risk schema migrations.

## 10. Health-check and smoke-test checklist

Public, no credentials required:

```bash
APP_URL="https://<ACTUAL-RENDER-HOST>" # Placeholder, replace only after deploy
curl -f "$APP_URL/" >/dev/null          # frontend HTML
curl -f "$APP_URL/health/live"
curl -f "$APP_URL/health/ready"
curl -f "$APP_URL/openapi.json" >/dev/null
curl -f "$APP_URL/demo" >/dev/null
```

**Important correction for static SPAs:** depending on router/backend configuration, `curl /demo` should return frontend `index.html` with HTTP 200; JavaScript then renders `/demo`. A simple curl doesn't validate displayed UI. Use Playwright/real browser for anonymous demo/nested routes.

Authenticated workflows in browser/private E2E: login/CSRF cookie, create/list/reply, staff claim/private note/resolution, customer note isolation, reopen policy. Use synthetic data only. Use test accounts privately, not shared passwords in a public README. Re-deploy service and repeat persistence test.

## 11. Troubleshooting matrix

| Symptom | Likely cause | Corrective action |
|---|---|---|
| `/health/ready` 503 | DB missing, unreachable or migrations not applied | Inspect redacted logs, URL scheme/TLS/region and `alembic current`; do not log URL. |
| Docker build frontend fails | package lock/version mismatch | Match npm/Node versions and run `npm ci` locally; commit updated lock. |
| `/app/tickets` refresh -> 404 | SPA route fallback missing | Return built `index.html` for non-API GET paths only. |
| Browser requests wrong API domain | hard-coded frontend origin | Use relative `/api/v1` URLs in production; Vite dev proxy locally. |
| Login sets cookie but next request unauthenticated | wrong host/Secure/Path/proxy config | Verify single HTTPS origin, cookie flags, actual host and trusted proxy config. |
| Form mutation returns CSRF 403 | missing `X-CSRF-Token` or wrong Origin | Inspect session bootstrap and HMAC secret continuity; never disable CSRF in production. |
| Production migration connects but fails | wrong direct URL, insufficient grants, model drift | Inspect migration revision, privileges and SSL; fix safely before deploy. |
| Deploy hook returns success but site unchanged | provider deploy queued/failed, old revision still live | Inspect Render deployment status and commit; don't equate hook 200 with completion. |
| First request loads slowly | Render free web service sleeping | Document idle spin-down and upgrade if always-on access needed. |
| Data disappears after deploy | wrote state to container filesystem | Move all persistent data to managed PostgreSQL; re-test. |
| Secrets in Vite bundle | used `VITE_` variable for secret | Rotate leaked secret, remove client exposure, rebuild and review Git history. |

## 12. No-fabrication final proof

Before reporting success, the agent must supply:

```text
Source repository URL:       <actual URL>
Verified live app URL:       <actual HTTPS URL>
Public demo URL:             <actual URL>/demo
API docs URL:                <actual URL>/docs
Ready health URL:            <actual URL>/health/ready
GitHub CI status:            <actual workflow run link/status>
Production migration head:  <actual Alembic revision>
Deployment commit:           <actual SHA confirmed on Render>
Manual smoke-test result:    <what passed and when>
Known limitations:           <truthful current issues / free-tier behavior>
```

If account access is unavailable or any smoke test fails, say clearly **deployment not yet completed**; provide the built repo/files and the precise remaining authenticated action rather than making up a public URL.

## 13. Official sources to recheck

- Render Docker: https://render.com/docs/docker
- Render Blueprint YAML (including `autoDeployTrigger`): https://render.com/docs/blueprint-spec
- Render deploy hooks: https://render.com/docs/deploy-hooks
- Render Free plan limitations: https://render.com/docs/free
- Render health checks: https://render.com/docs/health-checks
- Render pre-deploy command limitations: https://render.com/docs/deploys
- Neon docs and live pricing: https://neon.com/docs and https://neon.com/pricing
- GitHub Actions PostgreSQL service container: https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers
- Vite client-exposed variables: https://vite.dev/guide/env-and-mode
