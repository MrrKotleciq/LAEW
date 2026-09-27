---
type: rule
title: Security
scope: security boundaries, validation, deny-by-default
read_when:
  - making security-sensitive changes
---

# Security 

Treat security boundaries as first-class requirements. 

## LAEW Priorities

Pay particular attention to: 
- path traversal and filesystem boundaries 
- command execution and command injection 
- unsafe tool parameters 
- privilege and permission boundaries 
- secret exposure 
- untrusted external input 
- unsafe network access 
- sensitive data in logs 

## Rules 

- Never hardcode secrets. 
- Validate untrusted input at boundaries. 
- Prefer allowlists for privileged operations. 
- Fail closed on security-sensitive validation. 
- Do not weaken existing security controls without explicit justification. 
- Avoid exposing sensitive data in errors, logs, or tool results. 

For security-sensitive changes, perform a dedicated security review.