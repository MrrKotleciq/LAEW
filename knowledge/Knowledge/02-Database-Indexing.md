---
title: Database Indexing
tags:
  - database
  - performance
  - indexing
backlinks:
  - 01-REST-API-Design
---

# Database Indexing

Principles for keeping query performance predictable as tables grow. This
complements [[01-REST-API-Design]]: a well-indexed store backs a fast API.

## Index Types

A B-tree index accelerates equality and range lookups on a column. A composite
index orders rows by multiple columns, so its leading columns must match the
query's filter order. A covering index includes the columns a query selects,
letting the database answer it without touching the table itself.

Every index adds write cost and storage. Adding one should be a deliberate
trade-off, never an afterthought.

## When to Add

Index a column only when queries filter, sort, or join on it frequently.
Measure first: a slow query is often a symptom of a missing index, but it is
also often a missing query plan. Check the query plan before indexing blindly.
The right index for a read-heavy path differs from the right index for a
write-heavy one — optimize for the actual workload.
