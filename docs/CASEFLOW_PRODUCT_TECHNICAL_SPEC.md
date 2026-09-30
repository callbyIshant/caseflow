# CaseFlow — Complete Product and Technical Specification

**Document status:** Build contract for a portfolio application; version 1.0  
**Project type:** Deployable full-stack customer support ticketing application  
**Primary audience:** AI coding agent and engineer reviewing generated implementation  
**Default stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16+, React + TypeScript + Vite, pytest, Vitest, Playwright, Docker, GitHub Actions  
**Hosting:** One Docker web service on Render + hosted PostgreSQL on Neon; one public web URL  
**Document hierarchy:** Requirements and security invariants here take precedence over coding-agent implementation preferences.

> **Meaning of "complete":** Every MVP behavior, role, table, endpoint, UI route, security expectation, test criterion, and deployment deliverable is specified. Features explicitly marked P1/P2 are extensions, not silent requirements. Don't present the application as a real financial service or use real customer/card data. Build original styling; do not use American Express marks or imply endorsement.

---

## 1. Executive brief

### 1.1 The product

CaseFlow is a browser-based customer service management platform for a fictional company, **Northstar Services**. Customers register, submit service issues, view their requests and reply to support. Support agents see the shared queue, claim or receive assignments, respond publicly, leave internal notes and move tickets through a controlled lifecycle. Administrators have support access and can assign tickets to any active agent; agent/admin provisioning is done through a secured management CLI, not public registration.

The public landing page provides a **read-only Explore Demo** using fixed synthetic fixtures so recruiters can see the product immediately without credentials. Live interactive workflows require registration. The deployed service hosts both the compiled React application and `/api/v1` under the **same origin**, avoiding cross-site-cookie/CORS complexity and giving one live portfolio link.

### 1.2 What hiring reviewers should see

- Working full-stack application, useful mobile-responsive UI, appropriate empty/loading/error states.
- Real PostgreSQL-backed REST API with readable OpenAPI schemas, validation and pagination.
- Authentication using secure same-origin server-managed sessions, CSRF protections and server-enforced role-based authorization.
- Transactional status changes with immutable activity history and public-vs-internal communications.
- Real integration tests against PostgreSQL; frontend tests; CI; Docker and a live, verifiable deployment.
- Explicit design trade-offs, threat model, known limitations, screenshots and a short demo recording.

### 1.3 Success criteria

1. A new customer can create an account, submit a ticket, view it and reply.
2. A support agent can list tickets, claim a ticket, respond, write a private note and move its status.
3. Customers can never access someone else's ticket or any internal note, even through direct API calls.
4. Status-changing operations and comments are captured transactionally and shown in the appropriate timelines.
5. All core workflows pass automated tests, both locally and in CI.
6. The application loads from one public HTTPS URL, with persisted data in a managed database.
7. Anonymous reviewers can explore a synthetic read-only product demo without exposing real/interactive support data.

---

## 2. Scope, priorities and exclusions

**P0 (mandatory for first public deployment):** landing/demo, registration/login/logout/session, customer and agent roles, admin CLI provisioning, customer ticket create/read/reply/reopen (no arbitrary editing/deletion), ticket list/filter/detail, assignment, status transitions, public replies, internal notes, append-only activity, server-side validation, role access, accessibility fundamentals, integrated React UI, test suite, CI, Docker, Render+Neon deployment, README and verified demo link.

**P1 (after P0):** admin web screens for user/agent management; transactional email notification provider; password-reset and email-verification flows (both required before handling real users); attachment support with object storage and malware scanning; analytics dashboard; advanced searching; persistent distributed rate limiting; keyboard shortcuts; exported audit data; observability dashboard.

**P2 (future):** configurable SLAs, escalation engine, customer satisfaction surveys, rules-based AutoTriage, WebSockets/live notifications, multi-tenancy, advanced reporting, queue-based background tasks, SSO, localization.

**Operational quality for P0:** use a documented 32 KB maximum request body, <=50 records per page, query timeouts, safe connection pool size and a reproducible synthetic load/smoke procedure. Record observed latency with test conditions rather than promising an invented production SLA. Handle DB outages with a neutral retryable error and never display tracebacks.

**Explicitly out of scope for P0:** accepting payments, integration with actual card accounts, genuine customer PII, real banking infrastructure, AI-generated financial guidance, SMS/email delivery, file uploads, service-level guarantees, multi-region HA and payment-card compliance certifications. Do not start those features during P0.

**Time planning:** A disciplined P0 can be developed iteratively; estimates depend on developer experience. Ship a smaller functioning slice before adding decorative UI or extensions. No fake claims of enterprise readiness.

---

## 3. Personas, goals and user stories

### 3.1 Personas

- **Visitor:** evaluate the product without creating an account; can view public marketing/architecture information and fixed demo pages only.
- **Customer:** self-register, sign in, submit and view only their own requests, post public replies, reopen recently resolved requests under specific conditions.
- **Agent:** authenticated staff member; list all tickets in the common queue, search/filter, claim unassigned tickets, update owned tickets, post public/internal messages; no user-role administration.
- **Admin:** all agent abilities, may assign/reassign any ticket to an active agent, may manage privileged accounts via the secured CLI in P0. No magic unrestricted bypass of API authentication.

### 3.2 Primary user stories and acceptance rules

| ID | User story | Acceptance condition |
|---|---|---|
| US-01 | As a visitor, I can inspect a demo. | `/demo` loads synthetic data with no API mutations; clearly says "read-only sample." |
| US-02 | As a visitor, I can register as a customer. | Email unique case-insensitively; role cannot be supplied/escalated; secure session created. |
| US-03 | As a customer, I can submit a request. | Valid subject/description/category creates unique ticket reference, OPEN status and activity event. |
| US-04 | As a customer, I can track my requests. | Only my tickets appear in lists and details regardless of query-string manipulation. |
| US-05 | As a customer, I can reply. | My public reply visible to authorized support; cannot create internal notes. |
| US-06 | As an agent, I can see a queue. | All queue tickets visible to authenticated agents only, paginated/filterable. |
| US-07 | As an agent, I can claim a request. | Two concurrent claims cannot overwrite each other; losing request receives 409. |
| US-08 | As an agent, I can move a claimed ticket. | Only allowed transitions; state change and event committed together. |
| US-09 | As an agent, I can make private notes. | Internal note never returned by customer-facing API/serializer or public demo. |
| US-10 | As a customer, I can reopen a resolved ticket. | Only own ticket; only within seven calendar days after resolution. |
| US-11 | As an admin, I can reassign a ticket. | Only active agents eligible; old/new assignee recorded in internal audit. |
| US-12 | As a reviewer, I can inspect engineering evidence. | README, API docs, seeded demo, tests, CI result and live link present. |

---

## 4. Architecture and request flow

```
                                     ONE PUBLIC HTTPS ORIGIN
                            https://<your-service>.onrender.com
                                           |
                            Render Docker Web Service (single)
                +------------------------------------------------------+
  Browser ----->| FastAPI app                                           |
  React SPA <---|   / and /assets/* -> compiled Vite React files         |
                |   /api/v1/*      -> versioned REST API                |
                |   /health/live   -> process alive                    |
                |   /health/ready  -> DB reachability                   |
                |   /docs          -> OpenAPI UI (never show secrets)   |
                +------------------------+-----------------------------+
                                         |
                                TLS PostgreSQL connection
                                         |
                               Neon managed PostgreSQL
                              (separate dev/prod databases)
```

**Local developer mode:** Vite on `localhost:5173` proxies `/api`, `/docs` and `/health` to FastAPI on `localhost:8000`; local PostgreSQL runs in Docker Compose. Same-site cookie behavior must be tested against the actual local proxy origin, not by calling a second unrelated domain from the browser.

**Production build:** multistage Docker image compiles React with Node; final Python image contains FastAPI, migrations, built frontend and only runtime dependencies. Use one Uvicorn worker for the free-tier proof of concept; choose a small, bounded SQLAlchemy connection pool. Avoid storing any persistent data on the Render container filesystem.

**Backend layering:** Router (HTTP/authorization wiring) -> service (business rules/transactions) -> repository/query (persistence) -> SQLAlchemy models. Pydantic request/response contracts are separate from ORM models. Services own business decisions and activity-event emission; keep routers thin.

**Dependency direction:** API never imports frontend; ORM models never return directly from HTTP endpoints; public demo reads a version-controlled fixture, not the live database.

### 4.1 Decisions and rationale

- **Modular monolith**, not microservices: relevant engineering depth without needless orchestration.
- **Server-managed opaque cookie sessions**, not tokens in localStorage: mitigates browser-token theft; add CSRF protection and same-origin hosting.
- **PostgreSQL for all persistence**: consistent real DB semantics for app and tests.
- **UUID primary keys + sequential display number for tickets**: private nonsemantic IDs and memorable references (`CF-000042`).
- **Explicit DB migration workflow**: separate schema change control from ordinary application startup; Render Free has no paid-only pre-deploy migration step.
- **Synthetic anonymous demo**: visitors can inspect a populated product without shared editable credentials.

---

## 5. Technical stack, conventions and dependency management

| Concern | Required choice | Notes |
|---|---|---|
| Language/runtime | Python 3.12 | Pin exact package versions in lock/constraints file; use current security patches. |
| Backend | FastAPI, Pydantic v2 | `/api/v1` routing; generated `/openapi.json` and `/docs`. |
| ORM/database | SQLAlchemy 2, PostgreSQL >=16, psycopg 3 | Small pool; `pool_pre_ping=True`; explicit transactions. |
| Migrations | Alembic | Every schema change gets a migration; never `create_all()` in production. |
| Password security | `pwdlib[argon2]` or equivalent maintained Argon2id library | Hash only; never log plaintext credentials. |
| Session IDs | `secrets.token_urlsafe()` + SHA-256 for stored lookup | Signed JWT not required for this architecture. |
| Frontend | React, TypeScript, Vite | Functional components, hooks, route-based layout. |
| API client | native `fetch` wrapped in typed client | `credentials: 'same-origin'`, typed errors, request-id surface. |
| React routing | React Router | Protected customer/agent routes plus anonymous demo. |
| Forms | React Hook Form + Zod (recommended) | Client validation must mirror, not replace, backend validation. |
| CSS | Tailwind CSS or CSS modules; choose one | Accessible visual design; avoid UI-library bloat. |
| Backend tests | pytest, httpx TestClient or AsyncClient, real test PostgreSQL | Test auth/authorization and concurrent assignment. |
| Frontend tests | Vitest + React Testing Library | Routes, forms, error/loading handling. |
| E2E | Playwright | Main customer and agent journeys. |
| Quality | Ruff, mypy (pragmatic scope), ESLint, `tsc` | Lint/typecheck in CI. |
| Containers | Docker multistage, Docker Compose | Build and run production-like stack locally. |
| Delivery | GitHub Actions -> Render deploy hook | Test first; run Alembic migration; then trigger deploy. |
| Deployment | Render Docker + Neon PostgreSQL | One HTTPS URL; free-tier restrictions documented. |

**Style:** Black-compatible Python formatting via Ruff; 100-character soft limit; TypeScript strict mode; no `any` except documented external boundaries; ISO-8601 UTC timestamps over wire; UTC-aware datetimes in backend; use lowercase snake_case JSON keys consistently across client/server.

**Credentials:** Never commit real `.env` files, database URLs, cookie tokens, demo user passwords, deploy hook URLs, private keys or API tokens. Keep `.env.example` placeholders only. For GitHub CI use repo/environment secrets. Pin GitHub Actions to maintained releases or verified commit SHAs.

---

## 6. Data model / authoritative schema

Unless explicitly marked nullable, fields are NOT NULL. All IDs use PostgreSQL UUID; store UTC timestamps as `TIMESTAMPTZ`. Prefer Python `uuid.uuid4()` defaults or a supported DB UUID generator. Migrations must create indexes and constraints, not just ORM declarations.

### 6.1 `users`

| Column | Type | Rules |
|---|---|---|
| `id` | UUID PK | Generated server-side. |
| `email` | VARCHAR(320) UNIQUE | Normalize trim + Unicode-aware lowercase policy; simplest MVP: validated ASCII email and `email.lower()`; unique DB constraint on normalized column. |
| `full_name` | VARCHAR(100) | Trim; nonblank; 2–100 chars. |
| `password_hash` | TEXT | Argon2id hash; never serialized. |
| `role` | enum | `customer`, `agent`, `admin`; registration always forces `customer`. |
| `is_active` | BOOLEAN | Default true; disabled users cannot sign in or maintain sessions. |
| `created_at` | TIMESTAMPTZ | Server-generated. |
| `updated_at` | TIMESTAMPTZ | Updated on profile/role changes. |

Do not permit users to update `role`, `is_active` or `password_hash` through general profile requests. P0 changes to staff privileges only through authenticated administrative CLI running with separately supplied operational credentials.

### 6.2 `sessions`

| Column | Type | Rules |
|---|---|---|
| `id` | UUID PK | Session record ID. |
| `user_id` | UUID FK users | ON DELETE CASCADE for explicit account deletion operations only. |
| `token_hash` | CHAR(64) UNIQUE | SHA-256 of random opaque cookie token; no raw token retained. |
| `csrf_nonce` | CHAR(32) | Random hex nonce for HMAC-derived CSRF; never returned directly. |
| `created_at` | TIMESTAMPTZ | UTC. |
| `expires_at` | TIMESTAMPTZ | `created_at + 7 days`; absolute expiration, no sliding renewal P0. |
| `revoked_at` | TIMESTAMPTZ NULL | Non-null on explicit logout/forced logout. |

Indexes: unique token hash; (`user_id`,`expires_at`); optional expired-session cleanup CLI. Never include sessions in public API schemas/log output.

### 6.3 `tickets`

| Column | Type | Rules |
|---|---|---|
| `id` | UUID PK | API route identifier. |
| `ticket_number` | BIGINT IDENTITY UNIQUE | Strictly increasing; render display ref `CF-` plus minimum six zero-padded digits. Gaps are acceptable. |
| `customer_id` | UUID FK users | Not client-overridable. |
| `assignee_id` | UUID FK users NULL | Must refer to an active agent/admin; enforce in service layer transaction. |
| `subject` | VARCHAR(150) | Trim, 8–150 chars. |
| `description` | TEXT | Trim, 30–5000 chars. Immutable after creation P0. |
| `category` | enum | `account`, `billing`, `technical`, `general`; fictional company examples only. |
| `priority` | enum | `low`, `medium`, `high`; default medium; only agent/admin can change. |
| `status` | enum | `open`, `in_progress`, `waiting_customer`, `resolved`, `closed`. |
| `created_at` | TIMESTAMPTZ | UTC. |
| `updated_at` | TIMESTAMPTZ | Updated on state/assignment/priority/public or internal note. |
| `resolved_at` | TIMESTAMPTZ NULL | Current resolution time; clear on reopen. |
| `closed_at` | TIMESTAMPTZ NULL | Current close time; clear on reopen (reopening closed not supported P0). |
| `version` | INTEGER | Default 1, increment on mutations to support conflict detection if needed. |

Constraints: subject/description nonblank after trim; category/status/priority restricted to allowed values; relevant timestamps consistent with status. Index (`customer_id`,`created_at DESC`), (`status`,`created_at DESC`), (`assignee_id`,`status`,`updated_at DESC`), (`ticket_number`). Postgres enum or CHECK constraints are both acceptable if Alembic handles them cleanly.

### 6.4 `ticket_messages`

| Column | Type | Rules |
|---|---|---|
| `id` | UUID PK | Generated. |
| `ticket_id` | UUID FK tickets | ON DELETE RESTRICT; no ticket deletion P0. |
| `author_id` | UUID FK users | Historical authors are not hard-deleted P0. |
| `body` | TEXT | Trim, 1–3000 chars; escape/render as plain text only. |
| `visibility` | enum | `public` or `internal`; customer always public. |
| `created_at` | TIMESTAMPTZ | Append-only. |

Messages cannot be edited/deleted through P0 APIs. Agent internal notes are never serialized to customer endpoints, including counts/previews/full-text search.

### 6.5 `ticket_events` (immutable activity timeline)

| Column | Type | Rules |
|---|---|---|
| `id` | UUID PK | Generated. |
| `ticket_id` | UUID FK tickets | ON DELETE RESTRICT. |
| `actor_id` | UUID FK users NULL | Null only for future/system-managed events. |
| `event_type` | enum | `ticket_created`, `ticket_claimed`, `ticket_assigned`, `priority_changed`, `status_changed`, `ticket_reopened`, `public_message_added`, `internal_note_added`. |
| `visibility` | enum | `public`/`internal`; default internal for assignment, priority, internal notes. |
| `old_value` | JSONB NULL | Only controlled server-generated scalar/compact structured values. |
| `new_value` | JSONB NULL | Do not store passwords, session IDs, full secret details or whole message bodies. |
| `created_at` | TIMESTAMPTZ | UTC, append-only. |

For public replies, event contains message ID, not repeated body. Customer timeline must apply `visibility='public'` at the database query level; also use an explicit output schema. Internal events may contain assignee IDs, but never secret credential material.

### 6.6 Entity relationships

```
users (1) ---- (N) tickets          [tickets.customer_id]
users (1) ---- (N) tickets          [tickets.assignee_id, optional]
users (1) ---- (N) sessions
users (1) ---- (N) ticket_messages
users (1) ---- (N) ticket_events
 tickets (1) ---- (N) ticket_messages
 tickets (1) ---- (N) ticket_events
```

**Deletion policy P0:** no ticket/message/event hard deletion endpoint; session revoke allowed; customer self-delete excluded until a defensible data-retention/anonymization design exists. Public demo uses no stored user data.

### 6.7 Deterministic synthetic seeds

Provide `backend/app/scripts/seed_demo.py`, allowed only after `ALLOW_DEMO_SEED=true` is explicitly set and target DB fingerprint confirms it is the intended nonproduction demo database. Idempotently create 12–20 fictional tickets across categories, priorities and statuses; 2 fictional customers; 2 agents; meaningful messages/events with sensible timestamps. Accept initial staff/demo passwords through secure env input or generate once to local console; never print passwords in CI or production logs; never check credentials into source. For public reviewer exploration use separate **static** `frontend/src/demo/demoData.ts` fixtures only; never publish privileged shared login credentials.

---

## 7. Role-based access and information boundaries

Legend: `own` = owns ticket; `assigned` = assigned agent; `all` = shared support queue. Every authorization check occurs in backend after loading the authenticated user; frontend route guards are UX only.

| Capability | Visitor | Customer | Agent | Admin |
|---|---|---|---|---|
| View public landing and static demo | Yes | Yes | Yes | Yes |
| Register account | Yes, customer role only | No need | No | No |
| View own tickets | No | Own | Support queue | Support queue |
| Create customer ticket | No | Own | No | No |
| View support queue | No | No | All | All |
| Add public reply | No | Own unless closed | Assigned unless closed | Any unless closed |
| Add internal note | No | Never | Assigned unless closed | Any unless closed |
| Claim unassigned ticket | No | No | Yes | Yes |
| Assign/reassign to any agent | No | No | No | Yes |
| Change priority | No | No | Assigned | Any |
| Change support-controlled status | No | No | Assigned | Any |
| Reopen resolved within 7 days | No | Own | Assigned (optional support pathway specified below) | Any |
| Provision agents/admins | No | No | No | Privileged CLI only P0 |
| View internal notes/events | No | Never | All support tickets | All support tickets |

**Security invariants:** Customer `GET /tickets/{id}` for another customer's UUID returns **404**, not details or a 403 revealing existence. Customer list queries are constrained before pagination. Agent support read-all is by deliberate design; write restrictions remain enforced. All user-supplied customer/assignee/author/role fields are ignored/rejected rather than trusted.

---

## 8. Ticket lifecycle and business rules

### 8.1 States

- `open`: customer submitted; not yet being worked on. May be unassigned or assigned.
- `in_progress`: support actively investigating; must have an assigned active agent (admin may act as agent).
- `waiting_customer`: agent requires customer input; must have an assigned support user.
- `resolved`: support has completed work; customer has up to 7 calendar days to reopen.
- `closed`: archived outcome; read-only for everyone in P0.

### 8.2 Transition contract

| Current state | Actor | Next state | Requirements |
|---|---|---|---|
| `open` | assigned agent/admin | `in_progress` | Must be assigned. |
| `in_progress` | assigned agent/admin | `waiting_customer` | Optional public explanatory reply recommended. |
| `waiting_customer` | assigned agent/admin | `in_progress` | Must be assigned. |
| `in_progress` | assigned agent/admin | `resolved` | Require resolution summary: public reply of 10–1000 chars in same atomic operation. |
| `waiting_customer` | assigned agent/admin | `resolved` | Same resolution summary requirement. |
| `resolved` | assigned agent/admin | `closed` | No extra reply required. |
| `resolved` | owner customer | `open` | `now - resolved_at <= 7*24h`; include customer reopening reply 10–3000 chars; clear `resolved_at`. |
| `resolved` | assigned agent/admin | `open` | Within 7 days, require written reopening reason as public reply. |
| `waiting_customer` | owner customer | `in_progress` | Happens automatically when customer posts a public reply; atomic with reply/event. |

Everything else -> **409 Conflict** with machine code `INVALID_STATUS_TRANSITION` and safe message. P0 `closed` is terminal; no comments/notes. `resolved` accepts only reopening replies (not generic customer comments); support resolution-to-closed is allowed. `open` cannot become `resolved` in one step. Do not silently invent extra transitions.

### 8.3 Claim and reassignment

- `POST /tickets/{id}/claim` is only valid for active support user and when `assignee_id IS NULL`; two concurrent claim requests must serialize correctly using `SELECT ... FOR UPDATE` and transaction. Loser receives 409 `TICKET_ALREADY_ASSIGNED`.
- Claiming does **not** silently update `open` status; the claimant then explicitly starts work.
- Admin may reassign to any active agent (or admin when acting as support) using `PUT /tickets/{id}/assignee`. An unassign action may set `assignee_id=null` only while state is `open`; for other states return 409.
- Agent cannot reassign ticket to another person; assigned agent may request admin reassignment outside app P0.
- Status/priority changes and message creation must commit with their corresponding event in the **same database transaction**; never emit a success response if the activity event fails to persist.

### 8.4 Customer-facing activity

Only show ticket created, public status changes, public replies and reopen events. Hide support internal notes, assignment events, internal priority adjustments and diagnostic information. A customer may see high-level status and creation/resolution timestamps, but not confidential support workflow content.

---

## 9. Authentication, sessions and app security

### 9.1 Signup and identity

- `full_name`: trim, 2–100 characters; Unicode letters/spaces/apostrophes/hyphens permitted; reject control characters.
- `email`: validate using maintained email validator; normalize consistently and enforce a unique normalized column; refuse disposable-email support only if using a maintained policy (not required P0).
- `password`: minimum 12 and maximum 128 characters, allow spaces and passphrases, don't silently truncate; never return password in API responses; no mandatory confusing character-composition rules.
- `role` and `is_active` are strictly server-controlled. Signup payload rejects unknown/privileged fields (strict Pydantic schema).
- Duplicate email signup returns 409 `EMAIL_ALREADY_REGISTERED` (acceptable for this learning demo; document email enumeration trade-off). Sign-in always gives generic credential error.
- Password hashing: Argon2id through maintained dependency; hash on signup, verify constant-time via library; optional dummy verification for unknown email to lessen timing variation.

### 9.2 Session design

On successful signup/login create a cryptographically random 32+ byte opaque session token and a separate random CSRF nonce. Persist **only the SHA-256 hash of the opaque session token**, plus the nonsecret nonce, in `sessions`. Derive a stable per-session CSRF token as `HMAC-SHA256(CSRF_SECRET, raw_session_token + "." + csrf_nonce)`; `CSRF_SECRET` must be high entropy and provided only through server environment. The server can recompute the CSRF token on subsequent requests using the HttpOnly cookie submitted by the browser; never persist or log the raw token. Set an HttpOnly cookie named `__Host-caseflow_session` in production with `Secure=true`, `SameSite=Lax`, `Path=/`, **no Domain attribute**. Expire after 7 days (absolute). For HTTP local development use a separate cookie `caseflow_dev_session`, `Secure=false`, never enable insecure cookie in production.

`GET /api/v1/auth/session` validates the cookie and returns either `{ "authenticated": false }` or `{ "authenticated": true, "user": ..., "csrf_token": "..." }`. If authenticated, derive and return the current CSRF token only in this same-origin JSON response, add `Cache-Control: no-store`, and ensure it is never logged/cached. The frontend holds the CSRF token **in React memory**, re-fetches session on reload and sends `X-CSRF-Token` on every authenticated mutation (POST/PUT/PATCH/DELETE, including logout). `POST /auth/login` and `/auth/register` require validated same-origin `Origin` when issued from a browser; reject a mismatched or missing Origin for browser cookie-creating requests (tests and direct HTTP clients must supply the configured origin). On login/register success return authenticated user and csrf token and set cookie. After logout revoke session server-side and delete cookie.

Validate request Origin on all unsafe HTTP methods; require matching CSRF header on authenticated unsafe methods. No broad cross-origin CORS wildcard. CSRF cannot be a substitute for authorization. Sessions for disabled users are invalid. Use constant-time comparison of the received CSRF token against the recomputed HMAC result; do not accept a token from a different session. Configure strict trusted proxy settings; never trust a user-supplied `X-Forwarded-For` without known proxy configuration.

**Frontend:** fetch with `credentials: 'same-origin'`; do **not** store opaque session token or CSRF token in localStorage; route guards fetch `/auth/session` on boot; 401 -> redirect to login and preserve only safe internal return path.

### 9.3 Request and response hardening

- Enforce TLS in public deployment; use proxy-aware HTTPS handling only for trusted Render ingress.
- `Content-Security-Policy` with restrictive default; production scripts/styles rules must match built Vite app. Avoid unsafe inline dynamic scripts; test SPA on deployment. Self-host Swagger/OpenAPI UI static assets or use an explicitly limited path-specific CSP for `/docs`, because the default CDN-hosted documentation assets may otherwise be blocked by a strict same-origin policy.
- `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` appropriate restrictions; clickjacking protection using CSP `frame-ancestors 'none'`.
- Caching: `no-store` for authentication responses and all authenticated ticket responses; hashed static assets may use long immutable caching; `index.html` short/no cache.
- JSON body size cap (e.g., 32 KB) and explicit Pydantic field limits; reject unexpected media types for JSON mutation endpoints.
- Rich text/HTML not supported P0. Render messages as escaped plain text. Never use `dangerouslySetInnerHTML` for user content.
- Rate-limit authentication and ticket creation using a maintained library/provider: baseline 5 failed login attempts/15 minutes per IP+normalized identity, 20 per IP, registration 3/hour/IP, ticket creation 20/day/customer. For MVP single Render instance, an in-process limiter is allowed **only if** documented as restart-resettable and not distributed; persistent provider required before real-world use. Add `429 RATE_LIMITED` and `Retry-After` when relevant.
- Log security-relevant events without raw personal details beyond what is justified and without tokens/passwords/connection URLs. Generate `X-Request-ID`; report safe request IDs in errors.
- Backend must reject SQL injection (parameterized SQL/ORM), IDOR, mass assignment, privilege escalation, invalid status transitions and unauthorized internal note access. Configure DB account least privilege to practical hosting limits.

### 9.4 Real-world caveat

This is a **portfolio demo**, not a security-certified helpdesk. Do not claim compliance with PCI DSS, GDPR, SOC 2 or actual financial-sector controls. Before collecting real user information, implement email verification, password recovery, abuse handling, retention/deletion policy, managed audit monitoring, dependency security reviews and security testing.

---

## 10. API versioning and shared contracts

All business endpoints begin `/api/v1`; API returns JSON, uses ISO-8601 timestamps with timezone (`Z` in UTC), Pydantic strict input validation and consistent HTTP semantics. All list endpoints use `page` (starting 1) and `page_size` (default 20, max 50), with deterministic `created_at DESC, id DESC` ordering unless explicitly overridden.

**Success page envelope**:

```json
{
  "items": [],
  "pagination": { "page": 1, "page_size": 20, "total_items": 0, "total_pages": 0 }
}
```

**Standard error envelope** (including 422 validation errors through custom handler):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the highlighted fields.",
    "details": [{ "field": "subject", "issue": "Minimum 8 characters." }],
    "request_id": "req_20a3d..."
  }
}
```

**Other standard errors:** `AUTH_REQUIRED` (401), `INVALID_CREDENTIALS` (401), `CSRF_INVALID` (403), `FORBIDDEN` (403, where appropriate), `TICKET_NOT_FOUND` (404), `EMAIL_ALREADY_REGISTERED` (409), `INVALID_STATUS_TRANSITION` (409), `TICKET_ALREADY_ASSIGNED` (409), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500; generic, logged server-side).

### 10.1 Auth API

| Method | Endpoint | Request | Response | Auth |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | `{full_name,email,password}` | `201 { user, csrf_token }` + cookie | Visitor + same-origin check |
| `POST` | `/api/v1/auth/login` | `{email,password}` | `200 { user, csrf_token }` + cookie | Visitor + same-origin check |
| `GET` | `/api/v1/auth/session` | none | `200 {authenticated,user?,csrf_token?}` | Cookie optional |
| `POST` | `/api/v1/auth/logout` | CSRF header | `204` + clear cookie | Any signed-in user |
| `GET` | `/api/v1/users/me` | none | `200 UserPublic` | Signed-in |

`UserPublic` contains `id, full_name, email, role, created_at`, never hashes or session metadata. Login should return identical error for unknown email/wrong password. Cookie `Max-Age` and DB expiry must agree.

### 10.2 Ticket API

| Method | Endpoint | Caller | Behavior |
|---|---|---|---|
| `POST` | `/api/v1/tickets` | Customer | Create own ticket. |
| `GET` | `/api/v1/tickets` | Customer/support | Customer = own list; support = shared queue; filter parameters validated. |
| `GET` | `/api/v1/tickets/{ticket_id}` | Owner/support | Customer gets safe public detail; support gets safe support detail incl. internal notes/events. |
| `POST` | `/api/v1/tickets/{ticket_id}/messages` | Owner/assigned support/admin | Add authorized public or internal message; optional automatic waiting->in-progress transition. |
| `POST` | `/api/v1/tickets/{ticket_id}/claim` | Agent/admin | Atomic claim unassigned ticket. |
| `PUT` | `/api/v1/tickets/{ticket_id}/assignee` | Admin | Assign/reassign/unassign (unassign only OPEN). |
| `PATCH` | `/api/v1/tickets/{ticket_id}/priority` | Assigned support/admin | Change priority; record internal event. |
| `PATCH` | `/api/v1/tickets/{ticket_id}/status` | Assigned support/admin | Enforce transition table; `resolution_message` required for resolved. |
| `POST` | `/api/v1/tickets/{ticket_id}/reopen` | Owner within 7 days; assigned support/admin within 7 days | Reopen with required public explanation. |
| `GET` | `/api/v1/tickets/{ticket_id}/timeline` | Owner/support | Customer events/messages public only; support all authorized details. |

`GET /tickets` query: `page`, `page_size`, `status`, `category`, `priority` (support only), `assigned_to` (`me`/`unassigned` for support), `q` (search subject and display ref only; 2–100 chars); customer list never reveals other users' work. Search and filter occur in SQL **before** pagination and count. Avoid loading all rows into Python. DB/ORM must whitelist sortable columns to prevent injection.

**Customer create payload:**

```json
{
  "subject": "Unable to access my account",
  "description": "I receive a sign-in error even after resetting my fictional demo password.",
  "category": "account"
}
```

**Customer create response** `201`:

```json
{
  "id": "171e3d24-7b75-4d34-9ddc-754d8cd88790",
  "reference": "CF-000042",
  "subject": "Unable to access my account",
  "description": "I receive a sign-in error even after resetting my fictional demo password.",
  "category": "account",
  "priority": "medium",
  "status": "open",
  "created_at": "2026-09-30T08:30:00Z",
  "updated_at": "2026-09-30T08:30:00Z",
  "resolved_at": null,
  "closed_at": null
}
```

**Public message payload**: `{ "body": "Thanks, I can provide more details.", "visibility": "public" }`. Customer-sent `internal` -> **403**; do not silently reinterpret it. For support, author must be current assignee or admin. For a customer responding to `waiting_customer`, create message, set `in_progress`, create events in one transaction. Posting to `closed` -> 409; posting generic message to `resolved` -> 409 (use `/reopen`).

**Claim response:** `200` with updated support ticket representation. On simultaneous claim, exactly one request succeeds; other 409.

**Priority payload:** `{ "priority": "high" }`; update must log old/new if changed; same priority request should be idempotent (200, no duplicate event).

**Status payload:** `{ "status": "resolved", "resolution_message": "We verified the test configuration and corrected the demo account access setting." }`. `resolution_message` is mandatory only for resolution; create a public message and corresponding event in one transaction. Same-state mutation -> 409, except where explicitly defined otherwise.

**Reopen payload:** `{ "reason": "The same fictional issue appeared again after the initial resolution." }` length 10–3000; creates public reply/event; moves to OPEN, clears `resolved_at`, retains old historical events. The previous assignee can be retained, but the new OPEN state remains distinct and requires an explicit start-work transition.

**Timeline response** recommended shape:

```json
{
  "ticket_id": "171e3d24-7b75-4d34-9ddc-754d8cd88790",
  "items": [
    {
      "id": "event-uuid-here",
      "kind": "event",
      "type": "ticket_created",
      "created_at": "2026-09-30T08:30:00Z",
      "actor": { "display_name": "Customer" },
      "summary": "Ticket submitted"
    },
    {
      "id": "message-uuid-here",
      "kind": "message",
      "visibility": "public",
      "body": "Thanks, I can provide more details.",
      "created_at": "2026-09-30T09:00:00Z",
      "actor": { "display_name": "Customer" }
    }
  ]
}
```

Merge messages and **non-message** activity events in timeline to avoid duplicating entries for `public_message_added`/`internal_note_added`; sort by `(created_at,id)` ascending. Support sees internal events/notes clearly labeled; customer serializer must not contain internal keys or inadvertently leak via ordering/counts. Include `next` pagination later if needed; P0 ticket messages capped by reasonable demo usage.

### 10.3 Health and metadata endpoints

- `GET /health/live` -> 200 `{ "status": "ok" }` without DB access; used for container/process troubleshooting.
- `GET /health/ready` -> 200 `{ "status": "ready" }` only if DB `SELECT 1` completes inside timeout; return 503 generic response if unavailable; configure Render HTTP health-check path here.
- `/docs`, `/openapi.json` -> available for reviewers, contain no live secrets; provide example auth directions and schemas. Documenting routes does not bypass session/CSRF requirements.
- No additional public endpoints to retrieve users, messages or live customer data.

---

## 11. UI/UX specification

### 11.1 Visual identity

Original **CaseFlow / Northstar Services** branding, not American Express branding. Professional, airy support-product look: deep navy `#10223E`, action blue `#265DAB`, teal highlight `#167D84`, light background `#F6F8FB`, text `#202B38`, warning `#A85B00`, error `#B42318`. These are starting tokens; verify actual foreground/background combinations against WCAG AA contrast. Font: a widely available system UI stack; no dependency on external paid fonts.

Use 8px spacing scale, max content width 1200px, 10–12px card radii, consistent form errors, distinct status badges and subtle hover/focus feedback. No excessive animation or distracting marketing copy. Support desktop (>=1024px), tablet and mobile (>=320px). Provide visible focus indicator, semantic buttons, real form labels, proper headings and ARIA announcements for errors/toasts.

### 11.2 Required routes

| Route | Access | Required content |
|---|---|---|
| `/` | Public | Hero, concise product explanation, screenshots/features, buttons `Explore Demo` and `Get Started`, visible "portfolio demo" disclaimer. |
| `/demo` | Public | Fixed synthetic tickets/list/detail/timeline previews; read-only actions disabled with explanation; route never requests live support data. |
| `/login` | Anonymous | Email/password, validation, general login error, link to register. |
| `/register` | Anonymous | Full name/email/password/confirm password + demo disclaimer. |
| `/app/dashboard` | Customer | Welcome, counts of *own* tickets by state, recent own tickets, primary create CTA. |
| `/app/tickets` | Customer | Own list with search/status/category filters and pagination; accessible empty state. |
| `/app/tickets/new` | Customer | New form, validation, submit, success navigation to detail. |
| `/app/tickets/:id` | Customer | Safe detail, status badge, customer timeline, reply form where allowed, reopen option when eligible. |
| `/agent/queue` | Agent/admin | Shared searchable/filterable queue, status/category/priority/assignment indicators. |
| `/agent/tickets/:id` | Agent/admin | Detail, claim/assignment, status actions, priority, public reply and internal note tabs, complete internal timeline. |
| `/forbidden` | Signed-in wrong role | Neutral access-denied message with appropriate navigation. |
| `*` | Public | Styled 404 for unknown frontend route; do not fallback for `/api/*`. |

**Session bootstrap:** show short loading/skeleton while `/auth/session` resolves; avoid flashing protected pages before verification. After login, role directs to `/app/dashboard` or `/agent/queue`; safe internal return path allowed. A `401` from API clears client auth state and sends user to login with helpful message.

### 11.3 Component inventory

`AppShell`, `PublicNav`, `AuthenticatedNav`, `Sidebar`, `MobileNav`, `TicketList`, `TicketCard`, `TicketStatusBadge`, `PriorityBadge`, `FilterBar`, `Pagination`, `TicketForm`, `TextAreaCounter`, `TicketTimeline`, `TimelineEvent`, `ReplyComposer`, `InternalNoteComposer`, `AssigneeSelector`, `StatusTransitionMenu`, `EmptyState`, `Skeleton`, `ErrorPanel`, `ConfirmDialog`, `Toast`.

Prefer reusable components but don't build an abstract design-system framework. Use typed domain types generated from OpenAPI where practical, or hand-written types checked against schemas if generation adds excessive complexity.

### 11.4 Behavioral details

- Every networked UI area has loading, empty, success, validation error, permission error and retryable server-error states.
- Prevent accidental duplicate POST by disabling submit during pending request. Backend validation remains authoritative.
- Confirm before closing a ticket or logging out if an unsent reply exists.
- Ticket list retains filters in URL query params; browser Back should behave sensibly.
- Customer detail must not show agent-only action controls or internal note placeholders, and backend enforces the same boundary.
- Distinguish resolved vs closed with clear captions; show reopen window only when `resolved_at` allows.
- Accessibility: all forms keyboard-operable, buttons descriptively named, meaningful page titles and alert regions for errors.

---

## 12. Backend module responsibilities

Organize by bounded feature with shared infrastructure:

- `core/config.py`: Pydantic settings for `ENV`, `DATABASE_URL`, `DATABASE_URL_DIRECT`, allowed origin and cookie policy; fail fast if production critical config missing.
- `core/db.py`: SQLAlchemy engine/session; bounded pool (e.g., size 3, overflow 1); request-scope session; explicit rollback on exception.
- `core/security.py`: password hash/verify; opaque token/CSRF generation, hashing and constant-time checks.
- `core/errors.py`: typed domain errors and consistent exception handlers.
- `core/middleware.py`: request ID, security headers, Origin/CSRF checks and request size handling.
- `features/auth/`: schemas, service, router and session repository; no session value in logs.
- `features/tickets/`: ORM models, request/response schemas, query builder, service, router and lifecycle transition rules.
- `features/users/`: public user schemas, current user dependency and role guards.
- `features/demo/`: no backend P0 demo API necessary; frontend static fixture preferred.
- `scripts/`: admin provision, optional demo seed, cleanup expired sessions.

**Transactions:** Service functions use a single DB session/transaction per write; flush to obtain generated IDs/sequence, insert activity rows, then commit once. Handle unique violations for email and `FOR UPDATE` for claims. Return DTOs after commit, with deliberate `refresh` as needed. Lock ticket rows for competing status/assignment updates. Never send email or external network calls while holding row locks.

**Validation:** Pydantic enforces schema; service enforces ownership and transition policy; database enforces uniqueness/foreign keys/check constraints. These layers are complementary.

---

## 13. Recommended repository structure

```text
caseflow/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── .dockerignore
├── Dockerfile
├── compose.yaml
├── render.yaml
├── Makefile
├── docs/
│   ├── PRODUCT_TECHNICAL_SPEC.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── SECURITY.md
│   ├── DEPLOYMENT.md
│   ├── ADR-001-single-origin.md
│   ├── screenshots/
│   └── demo-script.md
├── .github/
│   ├── workflows/ci.yml
│   ├── workflows/deploy.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── backend/
│   ├── pyproject.toml
│   ├── requirements.lock (or uv.lock; choose one workflow)
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── core/{config,db,security,errors,middleware}.py
│   │   ├── features/
│   │   │   ├── auth/{models,schemas,service,router}.py
│   │   │   ├── users/{models,schemas,deps,admin_cli}.py
│   │   │   └── tickets/{models,schemas,queries,transitions,service,router}.py
│   │   └── scripts/{seed_demo,provision_staff,cleanup_sessions}.py
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/{client,auth,tickets}.ts
│   │   ├── auth/{AuthProvider,ProtectedRoute}.tsx
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/{public,customer,agent}/
│   │   ├── demo/demoData.ts
│   │   ├── hooks/
│   │   ├── types/
│   │   └── styles/
│   └── tests/
└── e2e/
    ├── playwright.config.ts
    └── tests/{customer-journey,agent-journey}.spec.ts
```

Keep module names case-sensitive, avoid circular imports, follow import formatting. `requirements.lock` denotes reproducible dependency pinning if chosen; the agent must ensure the install commands and files correspond exactly to the selected package manager rather than inventing incompatible combinations.

---

## 14. Work breakdown and exact implementation order

**Rule:** Deliver a working vertical slice at the end of every milestone. Never create decorative UI or half-built integrations before core validation/security.

### M0 — repository/bootstrap (deliverable: runnable skeleton)

- Set up backend package, basic FastAPI app, frontend Vite React TS, Ruff/TypeScript scripts, Git ignore and initial README.
- Configure local Postgres via Docker Compose; `/health/live`, `/health/ready` with explicit dev settings.
- Frontend displays initial shell/landing page, Vite proxy works for `/api` and `/health`.
- Multi-stage Docker build successfully serves SPA and backend from one port.
- Add CI skeleton for frontend and backend checks.
- **Gate:** `docker compose up --build` shows landing page and ready health status; no secrets committed.

### M1 — DB, authentication, authorization (deliverable: secure login)

- Create Alembic migration for users/sessions and ORM models.
- Add registration, login, logout, session bootstrap and `/users/me` with normalized email/Argon2id.
- Add production/dev cookie policies, trusted Origin and CSRF; strict Pydantic schemas.
- Implement role guards and script to provision agent/admin from secure terminal env (never through public registration).
- Build login/register React routes, session-aware protected route and role-based redirect.
- Test cookie properties, access control and CSRF. **Gate:** customer account cannot become agent via payload; logout invalidates cookie.

### M2 — customer ticket workflow (deliverable: usable customer app)

- Alembic migration for tickets/messages/events, FK/index/constraint verification.
- Ticket service: create, list own, get own, public messages, initial immutable event.
- Customer dashboard/list/create/detail/timeline + empty/loading/error states.
- SQL-side filter/pagination and 404 for cross-customer UUID.
- Automated integration tests. **Gate:** end-to-end create->list->detail->reply works; no cross-customer data leak.

### M3 — support queue and ticket lifecycle (deliverable: end-to-end two-role support)

- Support queue filter/list/detail, atomic claim, allowed status/priority changes, admin reassign.
- Public replies/internal notes with distinct response serializers and timeline filtering.
- Auto transition on reply from waiting_customer, resolution summary, customer 7-day reopen, terminal close.
- Staff UI controls and clear disabled states.
- Concurrency/visibility and transition tests. **Gate:** two simultaneous agents cannot both claim; internal note invisible to customer on all APIs.

### M4 — product polish and accessibility (deliverable: reviewer-ready UX)

- Public read-only fixed-fixture demo, responsive styling and meaningful product landing.
- Keyboard navigation, labelled forms, page metadata, confirmation dialogs, retry handling, useful empty/loading/error UI.
- Seed-script test with synthetic fixtures, screenshots and reusable README walkthrough.
- **Gate:** recruiter can inspect demo without sign-in, complete both live role journeys via private tester accounts, and understand architecture.

### M5 — quality and operational readiness (deliverable: reproducibly tested app)

- Backend unit/integration suite with ephemeral PostgreSQL; frontend unit tests; Playwright E2E.
- CI required checks for lint, typecheck, migration test and frontend production build.
- Tests prove 401/403/404/409/422 behavior, cookie/CSRF security, access boundaries, race handling and timeline atomicity.
- Security headers, rate limiter, structured logs + request ID, dependency/security scan (report severity and remediation; don't silently ignore).
- **Gate:** clean build/test run from fresh clone; no migration drift; no nonplaceholder secret in repo.

### M6 — production demo deployment (deliverable: verifiable live URL)

- Create separate Neon production DB; apply migrations with direct DB URL from trusted machine/CI.
- Configure Render single Docker web service with secrets and `/health/ready` check. Do not add temporary local SQLite or free Render Postgres that expires in 30 days.
- Public smoke test: landing, demo, HTTPS, `/docs`, `/health/ready`; private tester verifies customer create/reply and staff workflows.
- Set GitHub Actions deployment workflow to test, migrate then trigger Render deploy hook; preserve deploy URL as secret.
- Update repo `README.md` with **actual** verified public Render URL and screenshot/demo recording; never invent it.
- **Gate:** fresh visitor opens valid HTTPS URL; reload/nested SPA links work; DB data persists across restart/redeploy.

### M7 — optional refinements only after P0 gate

Analytics dashboard, rule-based AutoTriage, SMTP transactional notifications, password recovery/verification, advanced deployment monitoring. Keep each extension as a separate issue/PR.

---

## 15. Test strategy and mandatory cases

### 15.1 Backend unit tests

Test pure functions: email normalization, reference formatting, lifecycle transition validator, reopen-window boundary exactly at/around 7 days, role permission helpers, CSRF/session token hashing and CSRF HMAC generation/verification, pagination metadata, conversion of ORM state to customer/support DTOs. Use deterministic clock injection for time rules.

### 15.2 Backend PostgreSQL integration tests (mandatory)

Run migrations against a real PostgreSQL test service in CI. Each test transaction/fixture cleans state without bypassing DB constraints.

At minimum verify:

1. Registration stores hash not plaintext and always role customer.
2. Duplicate normalized email -> 409.
3. Login success sets session cookie; wrong/unknown credential gives same external response.
4. Session expired/revoked/disabled user -> unauthenticated.
5. Missing/wrong CSRF on authenticated POST -> 403; read still works.
6. Origin mismatch on login/mutation -> reject.
7. Customer creates valid ticket -> 201 + `CF-xxxxxx` + event.
8. Invalid subject/description/category -> 422 standard shape.
9. Customer A cannot list or get Customer B ticket; direct UUID -> 404.
10. Customer cannot inject `priority`, `assignee_id`, `customer_id`, `role` or internal visibility.
11. Customer only sees public timeline; serialization has no internal note/event leakage.
12. Agent queue returns all intended tickets and filters before pagination.
13. Agent can claim unassigned ticket.
14. Two concurrent claim requests -> one 200, one 409; assignee stable.
15. Agent cannot write/transition another agent's assigned ticket; admin can.
16. Agent cannot self-assign arbitrary ticket via admin endpoint.
17. Admin assignment rejects inactive/nonstaff users.
18. Invalid lifecycle transition -> 409 and no DB mutation/event.
19. Status update + event are atomic; induce event insert failure in a controlled test and assert rollback.
20. Resolve requires valid summary; creates public reply/event and sets `resolved_at` atomically.
21. Customer reopen within 7 days succeeds; after 7 days fails.
22. Customer reply to waiting_customer atomically creates message + moves to in_progress + events.
23. Customer cannot post internal note; support internal note never reaches customer endpoint.
24. Closed ticket mutation/comment fails.
25. Same-priority request does not create duplicate event.
26. Search cannot inject SQL; unusual characters are parameterized/safely handled.
27. Pagination total/count/order deterministic.
28. `/health/ready` fails cleanly when DB unavailable; `/health/live` remains process-only.
29. Generic unhandled exceptions return safe 500 + request ID; detailed stack trace not sent.
30. Log capture asserts session cookie/password/DB URL not logged.

### 15.3 Frontend tests

- Login/register validation and server errors.
- `AuthProvider` loading/authenticated/unauthenticated paths.
- Customer route cannot display agent controls.
- Ticket form counters/errors/duplicate-submit prevention.
- Ticket list filter URL persistence and pagination.
- Detail displays public timeline; internal support note is rendered only in agent support fixtures.
- Agent claim/status/priority UI handles 409 stale/race response and refreshes state.
- 401 global handling logs user out; 429 shows retry guidance; generic 500 includes request ID for support.
- Keyboard focus returns sensibly after dialogs/toasts.

### 15.4 Playwright E2E smoke journeys

**Customer:** register unique generated user -> create ticket -> see in list/detail -> reply -> log out -> log in -> ticket persists.  
**Agent:** seed/provision test agent -> log in -> locate customer ticket -> claim -> in progress -> public response -> waiting customer.  
**Cross-role:** customer reply auto-resumes in progress -> agent resolves with summary -> customer reopens within window -> agent resolves -> closes.  
**Anonymous demo:** `/demo` works logged out; mutation UI disabled.  
**Production smoke:** `/`, `/health/ready`, `/docs` and `/demo` HTTP statuses; no deep-link SPA 404 on `/app/...` after auth.

### 15.5 Quality targets

Do not chase arbitrary 100% coverage. Require high coverage of domain/security services and every permission/lifecycle path. CI must fail on test/lint/typecheck/build/migration errors. Document exact coverage percentage only if generated by CI and badge reflects latest main branch.

---

## 16. Logging, observability and error handling

Emit structured JSON logs in production: timestamp, level, environment, request_id, method, normalized route template, response status, duration_ms, authenticated user UUID if allowed/available, event/action code. Never log passwords, password hashes, raw cookies/session tokens, CSRF token, authorization headers, full DB URLs or entire arbitrary user message bodies. Email can be omitted/hashed in most request logs.

Report domain failures as INFO/WARN appropriate; unexpected exceptions with stack trace server-side only. Include request ID response header and safe `request_id` in error response. Health checks should have reduced log noise. Capture startup/build version via environment `GIT_COMMIT_SHA` if available.

For the portfolio database, document a manual export/restore plan (`pg_dump`/`pg_restore` through a trusted terminal with encrypted local storage) and periodically validate it if the data matters. Free-tier database backup/recovery guarantees vary; never claim that the external provider guarantees backups without verifying the active plan. Never commit production dumps or personally identifiable records.

P1: add Sentry/OTel only if configured to scrub sensitive fields and doesn't leak tokens. Do not add observability vendor merely for resume keywords.

---

## 17. Local development contract

### 17.1 Required software

Git, Docker Desktop/Engine with Compose, Python 3.12 if running backend outside Docker, Node LTS supported by selected Vite version. Keep `.tool-versions` or documented versions if using managers.

### 17.2 `.env.example` contract

```dotenv
ENV=development
APP_NAME=CaseFlow
PUBLIC_APP_URL=http://localhost:5173
ALLOWED_ORIGIN=http://localhost:5173
DATABASE_URL=postgresql+psycopg://caseflow:caseflow@localhost:5432/caseflow
DATABASE_URL_DIRECT=postgresql+psycopg://caseflow:caseflow@localhost:5432/caseflow
SESSION_TTL_HOURS=168
CSRF_SECRET=replace-with-random-dev-secret-only-never-use-in-production
COOKIE_SECURE=false
COOKIE_NAME=caseflow_dev_session
LOG_LEVEL=INFO
ALLOW_DEMO_SEED=false
```

Never put production values in this file. Production cookie name/security is set by environment-specific settings and must refuse `COOKIE_SECURE=false` when `ENV=production`.

### 17.3 Expected commands

Choose and implement exact package-manager commands consistently. Recommended Make targets:

```text
make setup          install backend/frontend dev dependencies
make db-up          start local PostgreSQL
make migrate        alembic upgrade head
make dev            run backend + frontend dev servers (or clearly document two terminals)
make test           backend + frontend tests
make lint           Ruff + ESLint
make typecheck      mypy + tsc
make e2e            Playwright local E2E
make docker-build   production image build
make docker-run     production-like container stack
```

A fresh contributor must be able to follow README without tribal knowledge. Migrations must run explicitly before backend expects schema. In Docker Compose, waiting for database health is distinct from applying migration.

---

## 18. Production Docker requirements

Use a multistage build: `node` stage runs reproducible `npm ci` and `npm run build`; Python stage installs reproducible backend dependencies, copies app/alembic + `frontend/dist`, runs as a non-root user, exposes runtime port, starts `uvicorn` bound `0.0.0.0:${PORT:-8000}`. Do not put secrets in `ARG` or image layers. Add `.dockerignore` for `.git`, `.env*`, local databases, node_modules, caches, screenshots that don't belong in runtime.

FastAPI must mount compiled assets after all API/docs/health routes. SPA fallback only for non-API GET paths; `/api/*`, `/docs`, `/openapi.json`, `/health/*` must never serve `index.html`. Missing static assets return real 404. Frontend fetches relative `/api/v1`, so no production API hostname needs embedding in Vite bundle and no secret is exposed at build time.

Container handles SIGTERM gracefully; no database data is stored on local filesystem. For free Render proof-of-concept use one process/worker and avoid in-process background work that needs durability.

---

## 19. Deployment architecture and exact runbook

### 19.1 Why Render + Neon

Render currently supports Git-linked Docker web-service deploys and free web services; its free services can spin down after inactivity and have ephemeral local files, so persistent DB data must live outside the container. Render's free Postgres currently expires after 30 days, therefore this plan uses Neon for persistent portfolio data instead. Render supports HTTP health checks and secret env configuration. Neon offers hosted PostgreSQL and a free plan appropriate for learning/early projects subject to current quotas. Verify pricing/limits at deployment time because plans can change.

Use geographically close regions where available (e.g., Frankfurt for both) to reduce database latency; exact region availability can change.

### 19.2 Neon setup

1. Create project `caseflow-prod` in a region near Render.
2. Create database/role; get **pooled application connection** and direct connection if your migration tooling needs it.
3. Convert URL scheme for psycopg/SQLAlchemy if necessary: `postgresql+psycopg://...`; preserve required SSL query settings.
4. Keep pooled URL in Render `DATABASE_URL`; keep migration URL in GitHub secret `PROD_DATABASE_URL_DIRECT`. Do not paste secrets into repository/issues/screenshots.
5. Before initial Render creation, execute `alembic upgrade head` from trusted local machine using production direct URL. Confirm `alembic current` reports head and required tables/indexes exist.
6. Do not run `seed_demo.py` against production unless you explicitly want synthetic interactive demo data and have set safety gate. The anonymous `/demo` uses static fixtures and needs no DB seed.

### 19.3 `render.yaml` target

Agent should create equivalent config:

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

Region value should be changed if account/Neon region differs. `sync:false` prompts only on initial Blueprint creation; existing services need new secrets entered in dashboard. Never define secrets as literal YAML values.

`PUBLIC_APP_URL` and `ALLOWED_ORIGIN` are the **exact final HTTPS origin** (e.g. `https://caseflow-portfolio.onrender.com`, no trailing slash). If Render hostname isn't known before first creation, create service, obtain host, set values, redeploy. Production startup must fail fast on an invalid `http://` external origin or insecure cookie config.

### 19.4 Initial Render deployment

1. Push repository to GitHub main with green CI.
2. Apply production database migration **before** service expects tables.
3. Render dashboard -> New Blueprint/Web Service -> link repo -> Docker/Blueprint -> choose free plan if available.
4. Configure secret `DATABASE_URL` and exact HTTPS public origin values; never use local hostname.
5. Deploy. Watch build logs; no secret values should appear.
6. Confirm `GET /health/live` and `/health/ready` 200.
7. Visit root, `/demo`, `/docs`; perform a new customer registration and ticket test. Provision a private tester agent through the CLI against production only from trusted environment, then verify agent workflow. Don't publish credentials.
8. Restart/redeploy service and verify ticket remains—proves DB persistence is external.

### 19.5 GitHub Actions deployment path after initial setup

Configure Render Auto Deploy **off**. Add secret `PROD_DATABASE_URL_DIRECT` and `RENDER_DEPLOY_HOOK_URL`. CI on PR runs tests only. Push to `main` runs tests; after all pass, `deploy` job applies Alembic migrations to production and then POSTs the secret Render deploy hook. Protect GitHub `production` environment if available. Never expose hook URL in output.

For stronger production safety, migrations should be backward compatible with currently running code: additive changes before removals, and destructive cleanup in a later deploy. Portfolio P0 has one instance, but preserve this discipline.

After triggering deployment, either poll Render deploy API using securely stored API token **or** have a documented manual verification step; never claim deployment success solely because deploy hook returned 200. Final pipeline/smoke step should call the public `/health/ready` with retries and fail if it never becomes healthy.

### 19.6 Free-tier operational limitations

Render free web services can spin down after 15 minutes of no inbound traffic and may take approximately a minute to wake. Their filesystem is ephemeral. These characteristics are acceptable for a portfolio but should be stated in README so reviewers aren't surprised. Do not implement "keep awake" artificial traffic. If dependable always-on demos matter, upgrade the web service rather than circumventing provider policies. Provider quotas/prices change; confirm current terms before deploying.

### 19.7 Custom domain (optional)

After default Render URL works, connect e.g. `caseflow.yourdomain.dev`; update `PUBLIC_APP_URL` and `ALLOWED_ORIGIN`, redeploy and retest cookie/CSRF/SPA deep links. Keep the stable onrender fallback link in troubleshooting notes. Render manages TLS for supported custom domains; check current docs/plan.

---

## 20. CI/CD requirements

Two workflows are acceptable (`ci.yml` PR checks and `deploy.yml` main deploy) or one gated workflow. Mandatory quality gates:

**Backend:** checkout; Python install/cache; dependency install; start PostgreSQL service container; `alembic upgrade head`; `alembic check` (if supported by pinned version/workflow); Ruff; mypy; pytest integration; optional coverage.  
**Frontend:** Node install/cache; `npm ci`; ESLint; `tsc --noEmit`; Vitest; production `npm run build`.  
**Container:** build Docker image after code tests; optional Trivy scan; fail on clearly actionable high/critical findings after review.  
**Deploy (main only):** production environment approval optional -> install minimal backend/migration deps -> Alembic upgrade using secret direct DB URL -> trigger Render hook -> smoke-test public health after deployment.  
**Concurrency:** cancel superseded PR CI; prevent two production deploy jobs running simultaneously.  
**Permissions:** set minimal GitHub Actions `permissions: contents: read` unless more are needed.

GitHub Actions can run a PostgreSQL service container on Ubuntu runners; use DB health checks before tests. Do not use SQLite as the only CI DB because locking, enum, JSONB and transaction behavior can differ.

---

## 21. README requirements for hiring review

README first viewport:

1. `CaseFlow` + one sentence.
2. **Live Demo** badge/link to actual working URL (only after verified).
3. Screenshot/GIF of customer + agent experience.
4. Stack badges limited to technologies actually used.
5. "Why I built this" explicitly maps to application development, API specification, testing, Agile engineering and web data collection.

Required sections: problem, features by role, architecture diagram, screenshots, data model, key API endpoints/OpenAPI link, auth/security design, local setup, test commands, CI/deployment, engineering decisions/trade-offs, known limitations/free-tier wake behavior, next steps, license, demo data disclaimer. Mention no affiliation with American Express; say it was built as a portfolio project inspired by generic software-engineering apprenticeship requirements only if desired.

Highlight **specific verified evidence**, such as test suites and status rules. Never invent user counts, latency, coverage, production scale or business impact. If you measure API performance, document environment/sample size and treat it as a local benchmark.

### 21.1 Recommended 2-minute demo video script

0:00 landing + architecture; 0:15 customer register/create ticket; 0:40 agent queue/claim/respond/waiting; 1:05 customer reply and automatic state transition; 1:20 agent private note + resolve; 1:35 customer-safe view proving note hidden + reopen; 1:50 show CI/OpenAPI/README and live URL. Use synthetic data, redact login credentials/secrets.

---

## 22. Coding standards and non-negotiable rules for the agent

1. Don't change stack/architecture without recording an ADR and updating this spec first.
2. Don't hard-code credentials, service URLs or production origins.
3. Don't add public endpoints exposing all users/customers.
4. Don't create a registration `role` field or let frontend choose staff role.
5. Don't return ORM objects directly from endpoints or rely on frontend to strip secrets.
6. Don't use SQLite as production or sole integration database.
7. Don't persist auth/session token in localStorage/sessionStorage.
8. Don't use CORS `*` with cookies.
9. Don't add ticket delete/edit endpoints P0.
10. Don't introduce attachment/HTML rendering P0.
11. Don't catch broad exceptions and return success/default data.
12. Don't suppress failed tests/types/security findings just to get green CI.
13. Don't expose raw exception traces to browser.
14. Don't use mock data in authenticated live ticket screens after backend is available; mock fixtures only `/demo` and tests.
15. Don't claim a deployment URL until an actual HTTP health and page smoke test succeeds.
16. Keep every DB mutation and its audit/activity event in one transaction.
17. Enforce role/ownership in DB query/service, not only route or UI guard.
18. Treat all client-provided IDs and hidden form fields as untrusted.
19. Prefer small reviewed commits/milestones and meaningful tests to massive generated code dumps.
20. After each milestone, update README/changelog and report exact tests run and unresolved limitations.

---

## 23. Definition of done / final acceptance checklist

### Product
- [ ] Public landing + anonymous fixed-fixture `/demo`.
- [ ] Registration/login/logout/session work over real database.
- [ ] Customer create/list/filter/detail/reply/reopen.
- [ ] Agent queue/claim/status/priority/replies/internal notes.
- [ ] Admin assign/reassign; staff provisioning CLI.
- [ ] Correct lifecycle, resolution/reopen rules and immutable events.
- [ ] Responsive, accessible empty/loading/error UX.

### Security
- [ ] Argon2id password hashing, no plaintext storage/logs.
- [ ] Secure `__Host-` production session cookie; opaque token stored hashed and per-session CSRF derived by server HMAC.
- [ ] CSRF + Origin checks on unsafe authenticated/credential operations.
- [ ] 404 cross-customer ticket protection and server RBAC.
- [ ] Customer API has zero internal note/event leakage.
- [ ] Validation limits, escaped plain-text messages, security headers and rate limits.
- [ ] Secrets absent from Git history and frontend bundle.

### Engineering
- [ ] Alembic migrations reproducible from empty PostgreSQL.
- [ ] Race-safe claim; state/event transaction atomicity.
- [ ] Backend PostgreSQL integration tests, frontend tests, Playwright journey.
- [ ] Ruff/mypy/ESLint/TypeScript and production build green.
- [ ] Docker production image runs as non-root, handles port and static SPA correctly.
- [ ] CI blocks merge/deploy on failure.

### Deployment
- [ ] Separate Neon prod DB with production migrations at head.
- [ ] Render Docker service uses external DB, HTTPS and `/health/ready`.
- [ ] App data survives web-service redeploy/restart.
- [ ] GitHub secrets hold production DB URL/deploy hook.
- [ ] Main deployment tests -> migrates -> deploys -> verified smoke test.
- [ ] README contains real verified live link, current screenshots and free-tier wake note.

### Interview-readiness
- [ ] Can explain one-origin architecture, modular monolith and trade-offs.
- [ ] Can explain session/cookie/CSRF vs localStorage token choice.
- [ ] Can explain row lock claim concurrency.
- [ ] Can explain difference between Pydantic, business and DB constraints.
- [ ] Can walk through one failed test/bug and how it was fixed.
- [ ] Can discuss what would need to change for real financial/customer data.

---

## 24. Recommended interview talking points

**Why modular monolith?** Scope is a portfolio support app; separate frontend/API/database boundaries are enough to show engineering rigor. Microservices would create deployment/network complexity without a demonstrated scaling or team-boundary need.

**Why same-origin?** It reduces CORS and cross-site cookie complexity, simplifies relative API calls and creates one recruiter-friendly URL. It still needs CSRF protections because cookies are automatically sent by browsers.

**Why opaque server sessions?** Easy revocation, no access token in JavaScript storage, clear session lifecycle. Trade-off: DB lookup on authenticated requests and server-side session cleanup.

**How is IDOR prevented?** Customer ticket queries constrain by both `id` and authenticated `customer_id`; not “load ticket then hide UI.” Unauthorized IDs return 404.

**How do you prevent two agents claiming one ticket?** Transaction locks target ticket row (`SELECT ... FOR UPDATE`), re-checks unassigned state under lock, writes assignee/event and commits. Competing transaction sees assigned state and receives 409.

**Why activity events?** Auditable product behavior and useful timeline without mutating historical messages. Event and state mutations share one transaction.

**Biggest production gaps?** Real account recovery/verification, object storage and scanning for uploads, distributed abuse controls, stronger observability/alerting, formal data retention/privacy processes, HA/scaling, backup/restore validation and security/compliance review.

---

## 25. External implementation references checked for this specification (2026-09-30)

The coding agent should re-check official documentation before changing provider/runtime-specific details.

- FastAPI security/JWT/password hashing background: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/  
- FastAPI static files: https://fastapi.tiangolo.com/tutorial/static-files/  
- Render free-service behavior/limits: https://render.com/docs/free  
- Render Docker deployment: https://render.com/docs/docker  
- Render first deploy / coding-agent deployment support: https://render.com/docs/your-first-deploy  
- Render health checks: https://render.com/docs/health-checks  
- Render Blueprint YAML: https://render.com/docs/blueprint-spec  
- Render deploy hooks: https://render.com/docs/deploy-hooks  
- GitHub Actions PostgreSQL service containers: https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers  
- Vite environment-variable security: https://vite.dev/guide/env-and-mode  
- Neon pricing/background (plan quotas change): https://neon.com/pricing  
- Neon docs: https://neon.com/docs

---

# End of build contract

Any implementation is incomplete until every P0 item in the Definition of Done is met, production migrations are current, CI is green and the final live URL is independently smoke-tested. The agent must report deviations rather than silently reducing scope.
