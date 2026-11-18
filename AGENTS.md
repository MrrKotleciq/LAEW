# LAEW repository instructions

## Offline tests

Use the repository virtual environment. On Windows, run the full Python suite
with `.venv/Scripts/python.exe scripts/run_isolated.py pytest-offline`. Run the
JavaScript unit suite with `node --test tests/ui/*.test.js`.

The full Python suite needs TCP loopback access for its disposable HTTP
servers. If the runner's loopback check fails, rerun the same command with
the sandbox permission needed for local sockets. Keep the isolated runner
and the offline test selection. For focused runs, use the runner's `pytest`
subcommand with the target paths.
