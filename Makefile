# SecureRAG developer shortcuts.
# Windows note: install `make` (e.g. via Chocolatey/Git Bash) or run the underlying
# `docker compose` / `uv` commands directly.

.PHONY: up demo down logs test eval lint ingest seed

up:            ## Start only Qdrant (local dev)
	docker compose up -d qdrant

demo:          ## Build and start the full stack (qdrant + init + api + ui)
	docker compose --profile app up -d --build
	@echo "UI:  http://localhost:8501"
	@echo "API: http://localhost:8000/docs"

down:          ## Stop the full stack
	docker compose --profile app down

logs:          ## Tail the app logs
	docker compose --profile app logs -f

test:          ## Run the test suite
	uv run pytest

eval:          ## Run the golden-set evaluation
	uv run python eval/run_eval.py --config-name baseline

lint:          ## Lint and format-check
	uv run ruff check .

seed:          ## Seed demo users (local)
	uv run python scripts/seed_users.py

ingest:        ## Ingest the corpus (local)
	uv run python scripts/ingest.py --reset
