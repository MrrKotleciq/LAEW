# Platform
## Memory
### Recall
Automatic recall checks the local memory before invoking retrieval.

## Deployment
### Recall
Deployment recall restores the amber backup, not the local memory.

## Code
Run the verification command before promotion.
```python
def verify_release():
    return "VERIFIED-813"
```
