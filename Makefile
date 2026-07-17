.PHONY: install lint typecheck test audit compose-up compose-down terraform-check

install:
	uv sync --frozen --extra dev

lint:
	uv run ruff check .

typecheck:
	uv run mypy app

test:
	uv run pytest --cov=app --cov-report=term-missing

audit:
	uv run pip-audit

compose-up:
	cp .env.example .env
	docker compose up --build --detach --wait

compose-down:
	docker compose down --volumes

terraform-check:
	terraform -chdir=infra/terraform fmt -check -recursive
	terraform -chdir=infra/terraform validate
