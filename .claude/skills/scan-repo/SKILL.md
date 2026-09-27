--Importers/Callers: Self (the AI agent will read this prompt when context is cleared)
--Affected API: File system read/write operations for markdown files
--Data Schemas: Plain text markdown format
--User Verbatim Instruction: write a prompt for yourself to scan repo in order to find bugs, duplicated code, etc, after I clear your context

---
type: skill
title: Scan Repo
scope: repository-wide code quality, security, and architecture scanning
read_when:
  - requested via /scan command
---

# Repository Scan Prompt (Post-Context-Clear)

## Objective
Perform a thorough scan of the LAEW repository to identify bugs, duplicated code, security issues, code quality problems, and architectural inconsistencies.

## Prerequisites (Run First)
```bash
# 1. Verify test suite passes
cd C:\ROOT\Projects\LAEW && python -m pytest tests/unit -q

# 2. Run security audit
python -m bandit -r laew -lll

# 3. Check for type errors (if mypy configured)
python -m mypy laew --ignore-missing-imports
```

## Scan Checklist

### 1. Code Duplication
- **Tool**: Use `jscpd` or manual grep for repeated blocks ≥10 lines
- **Focus areas**: 
  - Tool implementations (`laew/tools/`)
  - Agent executor patterns
  - CLI/Console command handlers
  - Test fixtures and setup code

### 2. Security Issues (Bandit + Manual)
- Hardcoded secrets (API keys, passwords, tokens)
- SQL injection risks (string concatenation in queries)
- Path traversal (unsanitized file paths)
- XSS vulnerabilities (unescaped user input in web tools)
- Insecure defaults (e.g., `ssl_verify=False`)

### 3. Common Code Smells
- **Large functions** (>50 lines) — candidates for splitting
- **Large files** (>800 lines) — candidates for module extraction
- **Deep nesting** (>4 levels) — use early returns
- **Magic numbers** — replace with named constants
- **Long parameter lists** — consider dataclasses/config objects
- **Commented-out code** — remove or document why it's kept

### 4. Technical Debt Markers
Search for:
```bash
grep -r "TODO\|FIXME\|HACK\|XXX\|BUG" --include="*.py" laew/
grep -r "print(" --include="*.py" laew/  # Should use logging
grep -r "except:" --include="*.py" laew/  # Bare except
grep -r "except Exception:" --include="*.py" laew/  # Too broad
```

### 5. Architecture & Design Issues
- **Circular imports** — check `laew/__init__.py` and module imports
- **God classes** — classes doing too much
- **Violated abstractions** — e.g., concrete classes imported where protocols expected
- **Missing error handling** — especially in I/O, network, external calls
- **Inconsistent patterns** — e.g., some tools use `ToolResult`, others return tuples

### 6. Test Quality
- Tests that don't actually assert anything
- Flaky tests (order-dependent, time-dependent)
- Missing edge case coverage
- Mocks that don't match real interfaces
- Tests modifying global state without cleanup

### 7. Documentation Drift
- Docstrings that don't match function signatures
- Outdated comments
- Missing module-level docstrings
- Architecture docs (`docs/architecture/`) vs actual code

### 8. Performance Concerns
- N+1 patterns in loops
- Unbounded collections/growth
- Missing pagination/limits
- Repeated expensive computations (should cache)

### 9. Configuration & Secrets
- Hardcoded URLs, ports, timeouts
- Missing validation of config values
- Environment variable handling inconsistencies

### 10. Python-Specific Issues
- Missing type hints on public APIs
- Mutable default arguments
- Incorrect use of `async`/`await`
- Resource leaks (unclosed files, connections)
- Incorrect exception handling (catching too broad)

## Output Format
Report findings as a structured list:

```
## Critical (Blockers)
- [File:line] Description

## High (Should Fix)
- [File:line] Description

## Medium (Consider Fixing)
- [File:line] Description

## Low (Nice to Have)
- [File:line] Description
```

## Post-Scan Actions
1. Create GitHub issues for Critical/High findings
2. Fix Low/Medium items in a dedicated refactoring PR
3. Update this scan prompt based on what was found
4. Schedule next scan (recommended: every 2-3 milestones)

---

**Note**: This prompt should be used with a fresh context. Start by running the prerequisites, then work through each checklist item systematically.