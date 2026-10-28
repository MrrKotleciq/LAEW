---
title: REST API Design
tags:
  - rest
  - api-design
  - backend
backlinks:
  - 02-Database-Indexing
  - 002-knowledge-scope-separation
---

# REST API Design

Guidance for building stable, RESTful HTTP APIs. See [[02-Database-Indexing]] for
the storage side and [[002-knowledge-scope-separation]] for where API contracts
belong.

## Core Principles

A good REST API is a resource-oriented interface. Every endpoint maps to a
noun — a resource — identified by a URL. The HTTP method describes the
operation: GET reads, POST creates, PUT replaces, PATCH partially updates,
DELETE removes.

Keep resources plural and hierarchical. List resources under `/users`, and
nest sub-resources under `/users/{id}/orders`. Use a consistent resource
naming style throughout the vault so clients can predict URLs.

## Resource Naming

Name resources by their type, never by an implementation detail. Use `/products`
instead of `/catalog/items`. Prefer stable, human-readable identifiers over
opaque database IDs in URLs, and expose any internal identifier through an
explicit field rather than embedding it in a path.

## Error Handling

Return structured errors with a stable shape: a status code, a machine-readable
`code`, and a human-readable `message`. Never return stack traces or internal
paths to clients. Distinguish "not found" (404) from "malformed request" (400)
and "too many requests" (429) so callers can react automatically.
