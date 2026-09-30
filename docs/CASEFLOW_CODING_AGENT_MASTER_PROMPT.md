# CaseFlow — Coding Agent Master Prompt (copy/paste)

> Attach or put `CASEFLOW_PRODUCT_TECHNICAL_SPEC.md` and `CASEFLOW_DEPLOYMENT_RUNBOOK.md` into the coding agent's workspace. The full spec is the authoritative build contract. This prompt guides execution; it does not replace the spec.

---

## PROMPT START

Act as my **senior full-stack engineer, security-conscious architect, quality engineer and DevOps engineer**. Build and deploy **CaseFlow**, a complete portfolio-ready customer-service ticketing system. You have a detailed technical contract in `CASEFLOW_PRODUCT_TECHNICAL_SPEC.md` and a deployment checklist in `CASEFLOW_DEPLOYMENT_RUNBOOK.md`. Read **both files fully before writing code**, then inspect the current repository so you do not overwrite useful existing work. My objective is a real, functioning, tested, public HTTPS application and GitHub repository—not mockups or generated screenshots.

### Project configuration (do not quietly change these decisions)

- Project name: **CaseFlow**; fictional client brand: **Northstar Services**. No American Express logos, card brands or fake affiliations.
- Frontend: React + TypeScript + Vite; accessible responsive UI with professional, original visual design.
- Backend: Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + psycopg 3.
- Persistence: PostgreSQL in local Docker and separate managed production PostgreSQL on Neon.
- Security: same-origin HttpOnly opaque-cookie sessions; hashed session lookup; server-derived HMAC CSRF token; role-based server authorization; Argon2id passwords. No client-side token persistence.
- Local integration: Vite dev proxy for `/api`, `/docs`, `/health`; reproducible Docker Compose.
- Production: multistage Docker containing compiled React served by FastAPI; **one Render web-service HTTPS origin**; Neon for persistent DB; `/health/ready` health check.
- Quality: Ruff + pragmatic mypy, ESLint + TypeScript, pytest with real PostgreSQL integration, Vitest, Playwright, GitHub Actions with migrations and gated deployment.

### Required behavior

Implement the complete **P0** scope described in the spec, including the non-obvious requirements: strict customer/support data visibility, public-vs-internal notes, support claim race safety, state transition matrix, required resolution message, seven-day reopen rule, immutable activity history committed with each mutation, anonymous static read-only `/demo` and production-ready same-origin SPA fallback. Preserve exactly the documented routes/status codes/error envelopes or document any necessary small correction before implementation.

Do not replace a real implementation with static/pretend authenticated data. The only intentional static data belongs to `/demo` and tests. Don't create unnecessary ML systems, microservices, message queues, file uploads, payment processing or third-party email integration in P0.

### Required working approach

1. **Read/plan/inspect first.** Review both documents; output a concise dependency-aware implementation plan mapped to milestones M0–M6, highlight anything that is technically inconsistent or insecure before coding and propose minimal corrections in an Architecture Decision Record (ADR). Do not ask me to decide ordinary implementation details already settled by the specification.
2. **Implement vertically.** At the end of each milestone, leave the app runnable, execute relevant tests and update docs. Do not generate 50 empty files and call it progress.
3. **Build types and schema once.** Treat OpenAPI/Pydantic contracts and Alembic migrations as authoritative; keep frontend TypeScript types in sync; ensure response serializers explicitly differ for customer vs support visibility.
4. **Enforce backend security.** Never rely on hidden frontend buttons for role checks; database-query scope must prevent IDOR; choose safe defaults for cookies/CSRF/headers; write negative security tests.
5. **Treat concurrency deliberately.** Use actual PostgreSQL transactions and row locks for claims/status/assignments. Keep event emission in the same transaction as ticket changes and message writes.
6. **Build polished, comprehensible UI.** Implement every specified route and proper empty/loading/success/validation/permission/server-error states. Mobile and keyboard accessibility matter. No placeholder buttons that appear actionable but do nothing.
7. **Use honest test reporting.** Include command, result and known failures. Never disable/rewrite tests to hide implementation faults; don't claim 100% coverage without collecting it.
8. **Make an actual deployment.** Create working Dockerfile, Compose, Render Blueprint, docs and GitHub workflow. If GitHub/Render/Neon accounts are available and I explicitly authorize access, deploy. If account authorization or secret configuration is required, tell me *precisely which action I need to take* at the deployment boundary; never request pasted passwords/secrets in chat or embed them in committed code.
9. **Verify the public app.** After deployment confirm HTTPS, `/`, `/demo`, `/docs`, `/health/ready`, customer create/reply and staff workflow in the hosted environment. Publish **only the real tested URL**; do not fabricate `caseflow-portfolio.onrender.com` if the actual hostname is different.
10. **Do the final handoff.** Provide repository URL, tested live URL, architectural overview, demo instructions without public privileged credentials, screenshot/video paths, actual test results, CI status, migration revision, design trade-offs, operational caveats and remaining P1/P2 ideas.

### Engineering rules I expect you to follow

- Pin/manage dependencies reproducibly and select compatible versions based on current official docs, not imagined APIs.
- Use production-safe data migrations and never `create_all()` in deployed runtime. Use direct Neon connection for Alembic when appropriate and pooled connection for regular application traffic; validate psycopg connection-string scheme/SSL.
- Keep `.env.example` placeholders; secrets only in local untracked `.env`/GitHub/Render secure configuration. Avoid secrets in frontend `VITE_` vars.
- Production cookie must be `__Host-caseflow_session`, HttpOnly, Secure, SameSite=Lax, Path=/ and no Domain. Validate same origin and per-session CSRF on applicable endpoints; dev cookie may differ.
- Customer signup can never create agent/admin accounts; provision staff only using explicit secure CLI with controlled environment.
- Use server-maintained authorization checks; customer querying another customer's UUID receives 404.
- Enforce only allowed state transitions from the specification, including `waiting_customer` automatic response transition and resolution atomic summary.
- Support public/private messaging; never include internal notes/events in customer API payloads.
- Handle duplicate submits, empty/loading/error states and API 401/403/404/409/422/429 in UI.
- Give every HTTP error the defined JSON shape and request ID; keep server logs redacted.
- CI uses real Postgres, not only SQLite; deployment only after CI and production migration success.
- Do not attempt to bypass billing, captcha, user consent or cloud provider security processes. Avoid artificial wake-up traffic to Render free service.

### Milestone evidence to report to me

For each M0–M6 report:

- Completed files/features, including exact paths.
- Commands run, test pass/fail summary and any security-specific test result.
- Screenshot or brief UI description for user-visible milestones.
- Any deviation from spec, why it was necessary, and file/ADR recording it.
- The next milestone's prerequisites.

### Local acceptance gate

From a clean clone, README instructions must let another developer install dependencies, start local PostgreSQL, apply migrations, run backend/frontend, execute tests and build the production Docker image. Verify a full customer-and-agent ticket journey, including private-note isolation and 409 concurrent claim behavior.

### Deployment acceptance gate

1. `render.yaml` equivalent applied and service created under authorized account.
2. External Neon production DB contains applied Alembic schema.
3. No production secrets are visible in Git, Vite bundle or build logs.
4. Public HTTPS URL really resolves; nested SPA path refresh works.
5. Ready health and live app routes pass smoke checks.
6. Interactive data persists after redeploy.
7. The README includes the real URL, screenshots, tests, known limits and documented architecture.

**Start now:** Read both documents and inspect the repository. Then implement M0 and move through successive milestones, reporting verifiable completion. Do not stop after creating a high-level plan or writing a README. Continue until P0 is implemented; request my action only if required for cloud account linking/secret entry, otherwise proceed with local build and tests.

## PROMPT END

---

## Minimal continuation prompts (if your agent has a small context window)

**After a pause:** "Re-read the CaseFlow spec and milestone notes. Inspect `git status`, CI/tests, app routes and the last completed milestone. Continue the first unfinished acceptance criterion without rewriting completed work. Show verification evidence."

**At deployment:** "Read the CaseFlow deployment runbook. Check repo tests, production DB migration and Render config. Ask only for missing authorized account connections or dashboard secret-entry actions, not pasted credentials. Deploy, wait for actual provider deploy success and verify public link before updating README."

**For a code-review agent:** "Review this repository against CaseFlow P0 spec, focusing on auth/session/CSRF, customer IDOR and internal note leaks, atomic event transactions, row-lock claim races, accessibility, CI, Docker and Render production config. Report file+line evidence, severity and tests to reproduce. Do not invent issues without inspecting code."
