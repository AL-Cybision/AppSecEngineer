# ExpenseGuard

ExpenseGuard is a security-focused FastAPI reference application for submitting expenses and
receipts, reviewing them as an administrator, and producing auditable security evidence. The
repository is the deliverable for a 30-day build-led Application Security Engineering sprint.

## What It Demonstrates

- Opaque, hash-only bearer sessions with idle/absolute expiry and immediate revocation
- Object-level authorization and explicit workflow-state policies
- Argon2id password hashing and one-time password-reset tokens
- Private S3-compatible receipt storage with content inspection and short-lived download URLs
- Structured audit events for authentication, administrative, expense, and receipt operations
- Security-focused tests, custom Semgrep, CI security gates, hardened containers, and AWS IaC
- Requirements, threat modeling, secure review, SSDLC, risk, and exception evidence under `docs/`

## Local Run

```bash
cp .env.example .env
docker compose up --build
```

OpenAPI is available at <http://localhost:8000/docs> and Mailpit at
<http://localhost:8025>. Create an administrator interactively after migrations complete:

```bash
docker compose exec app expenseguard create-admin admin@example.test
```

Run the local quality suite without Docker:

```bash
uv sync --frozen --extra dev
uv run pytest
uv run ruff check .
uv run mypy app
```

## Security Boundaries

The intentionally weak comparison image in `labs/docker/` must never be deployed. All data used
for learning and demonstrations must be synthetic. Receipt malware scanning is not implemented;
the accepted residual risk and compensating controls are recorded in the threat model.

See [architecture](docs/architecture.md), [threat model](docs/threat-model.md), [security
requirements](docs/security-requirements.md), [secure review](docs/secure-code-review.md), and
[delivery controls](docs/ssdlc.md).
