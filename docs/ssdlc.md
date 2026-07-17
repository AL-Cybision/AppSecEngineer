# Secure SDLC, Governance, And Product Security

## Lifecycle

- **Requirements:** define assets, misuse cases, security requirements, evidence, and risk owner.
- **Design:** update DFDs, STRIDE, architecture decisions, privacy/file impact, and cloud boundaries.
- **Development:** follow the coding standard, use frozen dependencies, and add negative tests.
- **Review:** complete the PR checklist and source-to-sink review for changed trust boundaries.
- **Verification:** run tests, SAST, SCA, secrets, image, IaC, SBOM, and DAST gates.
- **Release:** review exceptions, image digest, migrations, backup/rollback, and signed evidence.
- **Production:** monitor auth/admin/file events, CloudTrail changes, secret access, and health.
- **Response:** contain exposure, preserve evidence, fix root cause, regress, disclose, and learn.

## Ownership And SLAs

The product owner accepts business risk; engineering owns fixes and operational controls; the
security owner validates exploitability, requirements, exceptions, and closure; the cloud owner
owns IAM, logging, backup, and teardown. One learner may perform every role but records each decision
from the role's perspective.

| Severity | Remediation target | Release policy |
|---|---:|---|
| Critical | 24 hours | Always blocks |
| High | 7 days | Blocks unless explicitly accepted |
| Medium | 30 days | Tracked with owner |
| Low | 90 days | Prioritized with backlog |

## Exceptions And Risk Acceptance

Every exception records an ID, affected asset/control, scanner fingerprint where applicable,
likelihood, impact, owner, rationale, compensating controls, approval date, expiry, and review date.
Critical findings cannot be accepted for release. High exceptions expire within 30 days. Blanket
paths, severity-wide suppressions, and permanent “false positive” comments are prohibited.

## Release Checklist

- [ ] Functional, authorization, migration, and rollback tests pass.
- [ ] Threat model, OpenAPI inventory, requirements matrix, and architecture match the release.
- [ ] No unaccepted secret, high/critical code, dependency, image, DAST, or IaC finding remains.
- [ ] Image is referenced by digest and has an SBOM/provenance record.
- [ ] IAM and network diffs are reviewed; backups, logs, alarms, and incident contacts are ready.
- [ ] Database migration and administrator bootstrap use controlled one-off procedures.
- [ ] Costed deployment approval exists and teardown or retention ownership is explicit.

## Developer Enablement

When adding an endpoint, first identify its actor, object owner, valid states, sensitive fields,
side effects, failure behavior, and audit event. Put authorization in a reusable policy/query rather
than relying on hidden buttons or UUID entropy. Add one permitted test, one wrong-user test, one
wrong-role test, and one invalid-state test. Security feedback should name the root cause and give a
runnable test, not only a policy reference.

