# Contributing

1. Start from a ticket containing functional and security acceptance criteria.
2. Keep changes small enough for source-to-sink review and add negative tests for trust boundaries.
3. Update migrations, OpenAPI behavior, threat model, and requirements evidence when contracts move.
4. Complete `.github/pull_request_template.md`; do not suppress a scanner without an approved,
   expiring exception.
5. Never commit secrets, production data, Terraform state, unredacted scanner exports, or live
   presigned URLs.

