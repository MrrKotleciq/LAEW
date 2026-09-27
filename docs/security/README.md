---
type: index
title: Security Reviews and Findings
scope: security audits, findings, and remediation
read_when:
  - before making a security-sensitive change
  - reviewing security posture
  - auditing a new feature
---

# Security Reviews

This directory contains security reviews, audits, and findings for LAEW.

## Documents

| Document | Purpose |
|----------|---------|
| [SECURITY_REVIEW.md](SECURITY_REVIEW.md) | Bandit SAST audit results (Milestone 11) |

## Security Principles

LAEW follows these security principles (from ADR-006):

1. **Security below the model layer** — programmatic security boundaries exist independent of the model.
2. **Deny-by-default** — destructive operations require explicit approval.
3. **Allowlists over blocklists** — only explicitly allowed operations are permitted.
4. **Fail closed** — on uncertain input, deny access rather than allow it.
5. **Principle of least privilege** — tools operate with minimal permissions.

## Audit Results

| Audit | Date | Findings |
|-------|------|----------|
| Bandit SAST (M11) | 2026-09-15 | 0 High, 0 Medium, 0 Critical |

## See Also

- [Architecture](../architecture/README.md)
- [Decisions](../decisions/ADR-006-security-below-model-layer.md)
