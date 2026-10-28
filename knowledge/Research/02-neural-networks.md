---
title: Neural Network Foundations
tags:
  - research
  - neural-networks
  - deep-learning
backlinks:
  - 01-transformer-embeddings
---

# Neural Network Foundations

The building blocks behind embedding models and other LAEW components. See
[[01-transformer-embeddings]] for the retrieval application.

## Foundations

A neural network is many layers of weighted, differentiable transformations.
Training adjusts the weights to minimize error on labeled examples.

- **Perceptron** — the single weighted-sum unit.
- **Hidden layers** — compose features so the network learns abstractions.
- **Loss and gradients** — measure error and steer the weights.

Understanding these fundamentals makes the embedding and agent components less
mysterious and easier to reason about when they misbehave.
