# Threat Model

## Assets, Actors, And Entry Points

Assets are credentials, bearer/reset tokens, user profiles, expense records, receipts, audit
history, database credentials, container images, Terraform state, and AWS identities. Actors are an
anonymous user, authenticated expense owner, administrator, developer, CI workflow, ECS task, and
AWS operator. Entry points are the REST API, multipart upload, OpenAPI, SMTP adapter, container
image, GitHub workflow, Terraform inputs, ALB, and AWS control plane.

Trust boundaries are the client/API edge, application/data services, GitHub/AWS federation,
public/private/isolated subnets, and human administrator/service-role boundary.

## Primary Abuse Cases

1. User A enumerates UUIDs or reuses a receipt URL to access User B's expense or file.
2. A user supplies `state`, `owner_id`, or role fields to approve or transfer their own expense.
3. An attacker enumerates accounts, brute-forces passwords, replays resets, or uses a revoked token.
4. A malicious receipt bypasses type checks, exhausts memory, escapes a storage prefix, or executes
   inline in a reviewer browser.
5. An administrator approves an invalid state, deactivates themselves, or performs an action without
   attribution.
6. Compromised CI dependencies, actions, base images, or credentials alter the produced artifact.
7. SSRF or task compromise reaches AWS task credentials and abuses an overbroad IAM policy.
8. Public networking, S3 policy, RDS configuration, logs, or Terraform state exposes sensitive data.

## STRIDE And Threat Register

Risk is likelihood times impact on a 1–5 scale: critical 20–25, high 12–19, medium 6–11, low 1–5.

| ID | STRIDE | Threat | L | I | Risk | Required control | Verification |
|---|---|---|---:|---:|---:|---|---|
| T01 | Spoofing | Stolen or replayed bearer token | 3 | 4 | 12 | Hash-only, idle/absolute expiry, revoke on security events | Auth tests |
| T02 | Tampering/EoP | BOLA or mass assignment changes another expense | 4 | 5 | 20 | Owner-filtered queries and explicit command schemas | Policy matrix tests |
| T03 | EoP | User directly approves or races a transition | 3 | 5 | 15 | Admin dependency, row lock, state invariant | Workflow tests |
| T04 | Information disclosure | Reset endpoint reveals accounts | 3 | 3 | 9 | Generic status/body and throttling | Reset tests |
| T05 | DoS/Tampering | Oversized, spoofed, or path-based receipt | 4 | 4 | 16 | Streaming limit, magic check, random key | File tests and Semgrep |
| T06 | Repudiation | Sensitive action lacks reliable actor evidence | 3 | 4 | 12 | Transactional audit event and request ID | Audit API tests |
| T07 | Information disclosure | Public bucket, RDS, or log secret | 3 | 5 | 15 | Private policies, isolated RDS, log allowlist | Checkov and plan review |
| T08 | EoP | ECS role permits unrelated AWS access | 3 | 5 | 15 | Receipt-prefix S3 and specific secret permissions | IAM review |
| T09 | Tampering | Mutable/untrusted build dependency changes artifact | 3 | 5 | 15 | Locks, SHA/digest pins, scans, SBOM/provenance | CI evidence |
| T10 | Tampering | Malicious but valid PDF/image reaches reviewer | 2 | 4 | 8 | Private storage, attachment delivery, no rendering | Accepted residual risk |

T10 is accepted for this 30-day lab because a reliable malware pipeline requires an operational
scanner and quarantine lifecycle. Production release requires fail-closed malware scanning or a
managed S3 scanning workflow, quarantine state, EICAR tests, alerting, and cleanup procedures.

