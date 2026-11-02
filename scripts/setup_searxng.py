"""Create the local SearXNG secret file without replacing an existing one."""

import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / "runtime" / "searxng.env"
target.parent.mkdir(parents=True, exist_ok=True)
try:
    with target.open("x", encoding="utf-8") as handle:
        handle.write("SEARXNG_SECRET=" + secrets.token_hex(32) + "\n")
except FileExistsError:
    print("Existing SearXNG secret preserved.")
else:
    print("Created local SearXNG secret.")
