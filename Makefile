.PHONY: install env run db-up db-down db-reset test lint format typecheck check

install: env
	uv sync

env:
	@test -f .env || cp .env.example .env

run:
	uv run uvicorn app.main:app --reload

db-up:
	docker compose up -d --wait

db-down:
	docker compose down

db-reset:
	docker compose down -v && docker compose up -d --wait

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run ty check

check: lint typecheck test
