---
type: rule
title: Performance
scope: evidence-based optimization, avoid premature optimization
read_when:
  - optimizing code
---

# Performance 

Optimize based on evidence, not assumptions. 

## Principles 

- Prefer simple efficient designs. 
- Do not optimize before identifying a real bottleneck. 
- Avoid unnecessary allocations, copies, I/O, and repeated work. 
- Consider memory usage as well as CPU/GPU time. 
- Preserve correctness and maintainability while optimizing. 

## Context 

For AI-assisted development: 
- Do not load large files or unrelated project areas unnecessarily. 
- Reuse retrieved information within the current task. 
- Prefer targeted inspection over broad repeated scans. 
- Keep long-running or expensive operations explicit. 

Measure before and after significant optimizations.