# Synchronizing the recorder
## Nested ownership
A primitive Lock does not track reentrant ownership in the way an RLock does. RLock permits the owning thread to acquire it repeatedly; each acquisition must be matched by a release before another thread can take ownership. This is useful when an outer operation calls a helper that needs the same protected state.
## Structured release
Use the lock as a context manager to release it when leaving the block, including exceptional exits. Reentrancy is not permission to forget release calls or to access shared state without synchronization. A timeout on acquisition describes whether the lock was obtained, not whether the protected operation finished. The recorder's diagnostic message should distinguish waiting for ownership from an error inside the protected section.
```python
with state_lock:
    update_state()
    persist_state()
```
