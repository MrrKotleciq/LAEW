---
type: rule
title: Development Workflow
scope: inspect → plan → implement → test → review
read_when:
  - starting a non-trivial development task
---

# Development Workflow 
For non-trivial changes, follow: 
1. Understand the requirement and current implementation. 
2. Inspect existing code and reuse proven patterns. 
3. Create a concise implementation plan before coding. 
4. Add or update tests for the intended behavior. 
5. Implement the smallest correct change. 
6. Run relevant tests and static checks. 
7. Review the resulting diff. 
8. Update documentation when behavior or architecture changes. 
Use dedicated skills for detailed research, architecture review, project synchronization, or other specialized workflows. 
Do not perform broad rewrites when a focused change is sufficient.