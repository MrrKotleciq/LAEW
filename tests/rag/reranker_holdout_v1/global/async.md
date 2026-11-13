# Asynchronous acquisition deadlines
## Cancelling an overdue task
asyncio.wait_for schedules a timeout around an awaitable. On timeout it requests cancellation of that awaitable and waits for cancellation to finish. The elapsed wall time can therefore exceed the nominal timeout. Code must not interpret the timeout argument as an unconditional hard kill at precisely that instant.
## Preserving a separately managed task
If the task must continue beyond the caller's wait, shield can protect it from cancellation initiated by wait_for. The caller still receives a timeout and must retain responsibility for the task's eventual completion, exception or cleanup. Shielding does not make the work successful and does not remove the need to track it. For a measurement controller the deadline result and the task lifecycle are recorded separately, so the next operation cannot mistake an outstanding task for a free device.
```python
try:
    result = await asyncio.wait_for(asyncio.shield(task), timeout=2)
except TimeoutError:
    record_pending(task)
```
