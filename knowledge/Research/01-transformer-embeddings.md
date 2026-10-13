---
title: Transformer Embeddings for RAG
tags:
  - research
  - embeddings
  - transformers
backlinks:
  - 02-neural-networks
  - 01-REST-API-Design
---

# Transformer Embeddings for RAG

How transformer models turn text into vectors for retrieval. Builds on
[[02-neural-networks]] and powers the retrieval in [[01-REST-API-Design]].

## Overview

An embedding model maps a piece of text to a dense vector. Texts with similar
meaning land near each other in vector space, so similarity can rank retrieval
candidates. The LAEW pipeline embeds each chunk and the query, then retrieves
by cosine similarity and reranks.

## Applications

- **Retrieval** — find the most relevant chunks for a query.
- **Clustering** — group similar notes into collections.
- **Deduplication** — detect near-duplicate notes before indexing.

The embedding model is a replaceable component; the pipeline stays model-agnostic.
