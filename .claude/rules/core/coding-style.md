# Coding Style 
## Core Principles 
- Prefer simple solutions over clever ones. 
- Follow KISS, DRY, and YAGNI. 
- Prefer small, focused functions and cohesive modules. 
- Avoid speculative abstractions. 
- Reuse existing project patterns before introducing new ones. 
## Immutability 
Prefer creating new values over mutating shared state. 
Mutation is acceptable when it is local, explicit, and clearly simpler or required by the API. 
## Error Handling 
- Handle errors explicitly. 
- Preserve useful error context. 
- Never silently swallow failures. 
- Keep user-facing errors clear and implementation details out of them. 
## Validation 
Validate untrusted input at system boundaries. 
## Maintainability 
- Avoid deep nesting. 
- Avoid magic numbers and unexplained constants. 
- Keep files reasonably sized and split modules when cohesion suffers. 
- Follow the language and framework conventions of the project.