# Secure Code Review

## Method

1. Inventory routes, background tasks, CLI commands, migrations, workflows, Terraform, and external
   adapters. Record authentication and expected actors for each entry point.
2. Trace attacker-controlled sources through parsing, normalization, policy guards, transactions,
   ORM queries, logs, SMTP, and object storage sinks.
3. Review authentication, object and function authorization, workflow invariants, file boundaries,
   cryptography, secrets, errors, auditability, dependency trust, and concurrency.
4. Prove exploitability with synthetic local data, rate likelihood and impact, fix the root cause,
   and add a negative regression test before closure.

## Controlled Baseline Findings

| ID | Finding | Root cause | Secure implementation | Regression evidence |
|---|---|---|---|---|
| EG-001 | Cross-user expense/receipt access | Fetch-by-ID without ownership predicate | Owner-filtered query; admin bypass is explicit | BOLA test returns 404 |
| EG-002 | Expense workflow mass assignment | ORM fields populated from arbitrary request data | Dedicated schemas exclude owner/state/role | State and owner remain unchanged |
| EG-003 | Recoverable stolen sessions | Raw bearer token persisted | Only SHA-256 token digest is stored | Token hash unit test |
| EG-004 | Unsafe receipt path and MIME trust | Client filename/type used as storage authority | Magic bytes, random key, bounded stream | Spoof/path tests and Semgrep |
| EG-005 | Account enumeration and reset replay | Distinct responses and reusable reset state | Generic response, expiry, row lock, one use | Reset equality/replay tests |

The controlled baseline is documentation-driven and must use only synthetic data. It is never an
AWS deployment target. Findings are considered closed only when the secure behavior and regression
test are both present.

## Review Checklist

- Confirm every route has the intended authentication dependency and that authorization occurs
  before data is returned, signed, logged, emailed, or mutated.
- Confirm request models expose only caller-controlled fields and ORM queries remain parameterized.
- Inspect filesystem/object keys, subprocess/deserialization/template use, outbound URLs, exception
  paths, transaction compensation, audit fields, and secrets in telemetry.
- Inspect dependency locks, installer behavior, base images, build context, workflow permissions,
  action pins, artifacts, IAM resources/actions/conditions, networking, encryption, and logging.

