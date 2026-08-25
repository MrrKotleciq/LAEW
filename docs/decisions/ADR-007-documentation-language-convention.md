# ADR-007 — English Language for Repository Artifacts

## Status
Accepted

## Context
LAEW is designed to work with various local and cloud LLM providers, code parsers, and developer tools. Multi-language mixing in technical contracts, prompt files, and manifests introduces tokenization inefficiencies and parsing ambiguity.

## Decision
All in-repository documentation, manifests, tool contracts, test specifications, and prompt templates must be written in English. Interactive user communication remains flexible based on user preference.

## Consequences
- Maximizes token efficiency and prompt comprehension across diverse model providers.
- Maintains standard English engineering terminology across all repository components.
