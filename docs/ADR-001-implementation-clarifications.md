# ADR-001: CaseFlow implementation clarifications

- **Status:** Accepted
- **Date:** 2026-09-30
- **Context:** The product specification and deployment runbook define the P0 contract. These clarifications resolve implementation details without changing the selected stack, routes, roles, or user-visible behavior.

## Decisions

### 1. Customer-visible activity is explicit

Only ticket creation, public status changes, customer reopen events, and public messages are customer-visible. Assignment, priority, and internal-note activity remain internal. Ticket messages and activity events are queried with visibility predicates at the database layer and then serialized through separate customer and support response schemas. Message bodies are never copied into event values; timeline assembly emits a message once and omits its corresponding message-added event to avoid duplicates.

### 2. Compound ticket operations are atomic

Each ticket mutation, any related message, and every corresponding activity event share one PostgreSQL transaction. Status transitions, assignment changes, and claims lock the ticket row before checking current state. Resolution and reopening create their required public message in the same transaction as the status change and event rows. Any failed insert rolls back the complete operation.

### 3. Schema changes remain an explicit migration step

The application never calls `create_all()` and does not run Alembic as a startup side effect. The local Compose stack has a one-shot migration service that must complete before the app service starts. This lets `docker compose up --build` provide a runnable local stack while keeping migration execution explicit and independently observable. Vite remains the local frontend development server and proxies API, docs, and health paths to FastAPI.

The Compose database publishes port `5433` on the host and listens on `5432` inside its network. This avoids collisions with a developer's existing local PostgreSQL server while keeping the documented container-to-container DSN unchanged.

The integrated app allows its own local origin and the Vite development-server origin for unsafe requests. The second origin is configurable only for nonproduction mode and defaults to disabled; production trusts the single configured HTTPS origin.

### 4. Local project documents are retained

The linked GitHub repository contained only its initial MIT license. The product specification, deployment runbook, and coding-agent prompt supplied in the local workspace are retained in the repository so a clean clone includes the implementation contract and operational guidance.

## Consequences

- Visibility policy is testable independently of the frontend and cannot be weakened by UI changes.
- Row locking plus transaction rollback gives deterministic claim and lifecycle behavior on PostgreSQL.
- Contributors must apply migrations before using DB-backed workflows; the Compose dependency performs that step for the local stack, while CI/deployment call Alembic explicitly.
- No production deployment is considered complete until authorized Render and Neon configuration is supplied and the hosted app is smoke-tested.
