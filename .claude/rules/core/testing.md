---
type: rule
title: Testing
scope: pytest usage, test quality, coverage goals
read_when:
  - writing or modifying tests
---

# Testing 

Maintain a meaningful automated test suite. 

## Requirements 

- New behavior should have tests. 
- Bug fixes should include a regression test when practical. 
- Prefer tests that verify behavior rather than implementation details. 
- Keep tests deterministic and isolated. 
- Use unit tests for focused logic and integration tests for component boundaries. 
- Use end-to-end tests for important cross-component workflows. 

## Test Quality 

Prefer Arrange → Act → Assert. 

Test: 

- expected behavior 
- important edge cases 
- failure handling 
- security-sensitive boundaries 

Maintain project coverage goals; target at least 80% unless a justified project-specific exception exists.