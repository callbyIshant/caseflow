.PHONY: db-up db-down migrate test lint typecheck build

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

test:
	cd backend && uv run pytest
	cd frontend && npm test

lint:
	cd backend && uv run ruff check app tests alembic
	cd frontend && npm run lint

typecheck:
	cd backend && uv run mypy app
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build
	docker compose build
