--- 
paths: 
    - "**/*.py" 
    - "**/*.pyi" 
--- 

# Python Testing 

- Use `pytest`. 
- Add regression tests for bug fixes. 
- Prefer focused unit tests for pure logic. 
- Use integration tests for filesystem, database, API, and external-service boundaries. 
- Keep tests isolated and deterministic. 
- Use `pytest.mark` categories when the project defines them. 
- Reuse project fixtures instead of duplicating setup. 
- Verify coverage using the project's configured coverage command.