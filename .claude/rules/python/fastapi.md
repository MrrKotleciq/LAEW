---
paths:
  - "**/app/**/*.py"
  - "**/fastapi/**/*.py"
  - "**/*_api.py"
---

# FastAPI Rules

- Keep route handlers thin.
- Put business logic in services or focused domain components.
- Use dependency injection for shared resources.
- Use `async def` for endpoints performing asynchronous I/O.
- Never perform blocking I/O directly in async routes.
- Keep request and response schemas explicit.
- Use `response_model` for application responses where appropriate.
- Keep authentication and database access in dependencies or dedicated services.
- Never expose passwords, tokens, hashes, or internal authentication state.
- Validate input with Pydantic constraints where possible.
- Keep CORS configuration environment-specific.
- Redact credentials and authorization data from logs.