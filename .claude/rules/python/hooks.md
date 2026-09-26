--- 
paths: 
  - "**/*.py" 
  - "**/*.pyi" 
--- 
# Python Hooks 

When project hooks are configured: 

- Run formatting/linting after Python edits when appropriate. 
- Run type checking for changes affecting typed interfaces. 
- Prefer `logging` over `print()` in application code. 
- Keep hooks fast and targeted; avoid running the entire test suite after every small edit unless required.