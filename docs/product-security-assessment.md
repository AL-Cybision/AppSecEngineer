# Product Security Assessment

## Assessment Summary

ExpenseGuard's highest inherent risks are object authorization, privileged workflow transitions,
bearer-token theft, untrusted receipt handling, and AWS workload identity. The implemented design
addresses the critical/high logical risks through owner-filtered queries, command schemas, row
locks, revocable sessions, private object storage, and narrow task permissions.

## Architecture Review Findings

| Decision | Assessment | Follow-up |
|---|---|---|
| Opaque server sessions | Appropriate for immediate revocation; adds a DB read per request | Measure DB load before scale-out |
| API-mediated upload | Provides enforceable content/size checks | Add malware quarantine before production |
| Presigned downloads | Limits application data transfer | Monitor issuance/access and keep expiry at 60 seconds |
| Transactional audit table | Couples successful action and evidence | Restrict DB role and export to immutable retention |
| PostgreSQL rate limits | Consistent across tasks but grows an event table | Add cleanup job and load-test contention |
| RDS master user at runtime | Acceptable only for short lab; privileges exceed runtime need | Split migration owner/runtime principal in production |
| Single NAT and RDS AZ | Explicit lab cost compromise | Use per-AZ egress and Multi-AZ RDS in production |
| No malware scanner | Medium accepted residual risk | Quarantine, scan, alert, and EICAR-test before real users |
| SMTP adapter only | Reset logic is complete but production delivery is not operated | Select provider and validate anti-abuse/delivery controls |

## Final Gate

The application is suitable for synthetic local learning and a short, explicitly approved AWS
demonstration after all automated checks pass. It is not approved for production users or sensitive
receipts until the malware, runtime DB privilege, backup-restore, alert routing, SMTP, availability,
privacy/retention, and operational incident-response follow-ups are closed.

