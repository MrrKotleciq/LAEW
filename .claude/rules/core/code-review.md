# Code Review 
Review meaningful code changes before declaring them complete. 
## Review Checklist 
Check: 
- Correctness and behavior 
- Readability and cohesion 
- Error handling 
- Security boundaries 
- Test coverage 
- Unnecessary complexity or duplication 
- Compatibility with existing architecture 
## Required Follow-up 
- Fix CRITICAL issues before completion. 
- Fix HIGH issues before merge unless explicitly accepted. 
- Record MEDIUM/LOW issues when they are intentionally left unresolved. 
## Review Process 
1. Inspect the diff. 
2. Run relevant tests and checks. 
3. Review security-sensitive behavior. 
4. Verify the implementation matches the intended design. 
5. Report concrete findings with file/line references when possible. 
Use a dedicated review agent when available.