# LAEW Project Structure 

## Project 

LAEW is a local-first AI Engineering Workspace. 

### Source Code 

- `./laew/` — application source code. 
- `./tests/` — automated tests. 
- `./tools/` — development and utility tooling. 
- `./manifests/` — system and configuration manifests.

### Documentation 

- `./docs/README.md` — documentation index and navigation entry point. 
- `./docs/LAEW_CONTEXT.md` — concise project context and scope. 
- `./docs/PROJECT_STATUS.md` — current implementation status. 
- `./docs/architecture/` — current architectural principles and intent. 
- `./docs/decisions/` — Architecture Decision Records (ADRs). 
- `./docs/roadmap/` — roadmap, milestones, and planned work. 
- `./docs/history/` — chronological development history. 
- `./docs/performance/` — performance measurements and baselines. 
- `./docs/security/` — security reviews and findings. 
- `./docs/source/` — source/reference material used during project development. 

## Documentation Navigation 

Do not read the entire `docs/` directory by default. 

Before reading a document: 

1. Start with `./docs/README.md` when the relevant location is unknown. 
2. Use filenames, directory structure, and document metadata to identify relevant documents. 
3. Read only documents relevant to the current task. 
4. Prefer targeted search before opening large documents. 
5. Do not read historical material unless historical context is needed. 

## Documentation Semantics 

- `docs/decisions/` records architectural decisions. 
- `docs/architecture/` describes current architectural intent. 
- `docs/PROJECT_STATUS.md` summarizes the current implemented state. 
- `docs/roadmap/` describes planned work, not implemented functionality. 
- `docs/history/` records what happened in the past. 
- `docs/source/` contains reference material and is not itself project policy. 

When documentation conflicts with implemented behavior, inspect the current code and tests before deciding what is true. 

When changing architecture, interfaces, security boundaries, or other ADR-governed behavior, identify and read the relevant ADR before implementation. 

## Document Metadata 

Project documentation may use YAML frontmatter to describe: 

- document type 
- title or identifier 
- status 
- scope 
- purpose 
- when the document should be read 
- related documents 

Use metadata and indexes to decide which full documents need to be read. 
Do not open large documents merely because they exist.