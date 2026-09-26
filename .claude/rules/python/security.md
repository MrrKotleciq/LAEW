--- 
paths: 
  - "**/*.py" 
  - "**/*.pyi" 
--- 

# Python Security 

- Never hardcode secrets or credentials. 
- Read required secrets from the configured environment/secret mechanism. 
- Validate filesystem paths before sensitive operations. 
- Treat subprocess arguments and external input as untrusted. 
- Prefer argument lists over shell command construction. 
- Avoid `shell=True` unless explicitly required and safely constrained. 
- Redact tokens, credentials, cookies, and authorization headers from logs. 
- Use the project's configured security/static-analysis tooling when available.