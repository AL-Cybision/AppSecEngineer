# Security Requirements And Evidence

This project targets applicable OWASP ASVS 5.0 Level 2 controls rather than claiming full
certification. Exact ASVS identifiers must be checked against the versioned source when the matrix
is updated.

| Requirement | Control | Evidence |
|---|---|---|
| Identity is unique and normalized | Lowercase unique email; generic conflicts | Registration tests |
| Passwords resist offline attack | Argon2id, 12–128 characters, no truncation | `app/security.py`, tests |
| Sessions are unpredictable and revocable | 256-bit random opaque value, SHA-256 at rest, idle and absolute expiry | Auth tests |
| Reset tokens are private and single-use | Hash-only 30-minute token; sessions revoked on use | Reset tests |
| Every object operation authorizes ownership | Queries filter by owner unless administrator | BOLA tests |
| Workflow fields cannot be mass assigned | Dedicated create/update/decision schemas | Mass-assignment tests |
| Sensitive state changes are concurrency-safe | `SELECT FOR UPDATE` plus explicit transition rules | Transition tests |
| Inputs and errors do not expose internals | Strict Pydantic schemas and problem responses | API tests/OpenAPI |
| Files are bounded and isolated | 10 MiB streaming limit, magic checks, random key, private S3 | File tests/Semgrep |
| Security events are attributable | Request ID, actor, target, outcome; secrets excluded | Audit tests/log review |
| Components are inventoried and scanned | Lock, SCA, SBOM, image/IaC scans | CI artifacts |
| Cloud data is private and encrypted | S3 public block/TLS, encrypted RDS, private subnets | Terraform/Checkov |

OWASP Top 10:2025 and API Top 10:2023 are used as awareness and coverage indexes. WSTG 4.2 cases
for configuration, authentication, authorization, session management, input validation, business
logic, API testing, and file handling form the manual test checklist.

