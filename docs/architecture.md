# Architecture

## Application Context

```mermaid
flowchart LR
    User[Expense user] -->|Bearer token / HTTPS| API[FastAPI API]
    Admin[Administrator] -->|Bearer token / HTTPS| API
    API -->|SQL / TLS| DB[(PostgreSQL)]
    API -->|Private object API| Objects[(MinIO or S3)]
    API -->|SMTP| Mail[Mailpit or configured SMTP]
    API -->|Structured events| Logs[CloudWatch Logs]
```

The API is the sole public application entry point. It authenticates a hash-only opaque session,
loads an active user, applies centralized role and ownership policies, executes a transaction, and
records the sensitive action. Public UUIDs are identifiers, not authorization controls.

## Local Data Flow And Trust Boundaries

```mermaid
flowchart TB
    subgraph Untrusted[Untrusted client boundary]
      Client[OpenAPI client]
      File[Receipt bytes]
    end
    subgraph App[Application task boundary]
      Router[Strict request schema]
      Auth[Session and policy checks]
      Service[Workflow service]
      Inspect[Size and magic-byte validation]
    end
    subgraph Data[Private data boundary]
      PG[(PostgreSQL)]
      S3[(Private object bucket)]
    end
    Client --> Router --> Auth --> Service --> PG
    File --> Inspect --> S3
    Auth -->|authorize before signing| S3
```

Receipt uploads are streamed to bounded temporary storage. The application ignores claimed MIME
type, detects supported content, hashes it, assigns an unpredictable key, uploads it privately, and
persists metadata. On database failure it deletes the new object. Downloads require a fresh object
authorization check before issuing a 60-second attachment URL.

## AWS Deployment

```mermaid
flowchart LR
    Internet -->|443| ALB[ALB / ACM]
    subgraph VPC
      subgraph Public[Public subnets, two AZs]
        ALB
        NAT[NAT gateway]
      end
      subgraph Private[Private application subnets]
        ECS[ECS Fargate task]
      end
      subgraph Isolated[Isolated database subnets]
        RDS[(Encrypted RDS PostgreSQL)]
      end
    end
    ALB -->|8000, ALB SG only| ECS
    ECS -->|5432, task SG only| RDS
    ECS --> S3[(Private encrypted S3)]
    ECS --> SM[Secrets Manager]
    ECS --> CW[CloudWatch]
    CT[CloudTrail] --> Trail[(Protected log bucket)]
    ECR[ECR immutable image] --> ECS
```

The lab profile intentionally uses one NAT gateway, one task, and single-AZ RDS to constrain cost.
A production profile requires one NAT per AZ or approved endpoints, at least two tasks, Multi-AZ
RDS, deletion protection, tested backup restoration, alert routing, and operational SMTP.

## Architecture Decisions

- Opaque sessions were selected over JWTs so logout, deactivation, and password-reset revocation are
  immediate and authorization state never becomes a stale client claim.
- Uploads pass through the API rather than direct presigned upload so size and content checks happen
  before an object becomes available.
- User-controlled schemas cannot contain `owner_id`, `role`, or `state`; workflow transitions are
  commands with database row locks.
- CORS is disabled because this sprint has no browser SPA. Introducing one requires an explicit
  origin, browser token-storage design, and CSRF analysis.

