# Secure Coding Standard

- Treat every request field, header, filename, object ID, SMTP value, environment value, and remote
  response as untrusted until validated for its specific sink.
- Use Pydantic request models with explicit fields and constraints. Never bind arbitrary dictionaries
  to ORM entities or accept actor, owner, role, audit, or workflow state from a normal user.
- Authenticate once through the standard dependency and authorize both the function and selected
  object before any response, signature, side effect, or sensitive error difference.
- Express workflow changes as named service commands. Lock the row, validate the current state, make
  the change and audit record in one transaction, and define compensation for external side effects.
- Use SQLAlchemy expressions and bound parameters. Raw SQL requires review, parameter binding, and a
  test proving attacker input cannot change query structure.
- Hash passwords only through the Argon2id helper. Generate tokens with `secrets`, store only token
  hashes, compare through maintained libraries, and never invent encryption or signature formats.
- Stream uploads with hard size bounds, inspect content rather than headers/extensions, generate
  object keys, store privately, and force attachment delivery. Never execute or render uploads.
- Return stable problem responses without stack traces, SQL details, paths, account-existence clues,
  or authorization-oracle differences. Log allowlisted fields, never raw credentials or tokens.
- Retrieve secrets from local ignored files or workload identity/Secrets Manager. Never pass secrets
  in CLI arguments, Docker build arguments, Terraform values, source, test fixtures, or artifacts.
- Pin dependencies, base images, actions, and deployment images; review update diffs and retain an
  SBOM. Suppressions require an owner, evidence, compensating control, and expiry.

