"""Start a disposable Workbench for browser verification, with restart control.

Pass the workspace left by validate_m17.py. The manifest must point to the
workspace's isolated Chroma port, never a production service port. Commands
on stdin: restart, stop.
"""
import os
import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import yaml

from validate_m17 import free_port, wait_http
from laew.web import WorkspaceService, make_handler
from laew.llm.llamacpp import LlamaCppProvider

base = Path(sys.argv[1]).resolve()
root = (Path(__file__).resolve().parents[1] / "runtime").resolve()
base.relative_to(root)
if not base.name.startswith("m17-validation-"):
    raise ValueError("Expected an isolated M17 validation workspace")
manifest_path = base / "test-manifest.yaml"
manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
cfg = manifest["rag"]["vector_store"]
port = cfg["port"]
if cfg["host"] != "127.0.0.1" or port in (8000, 8080, 8081, 8765) or cfg["global_collection"] != "m17_global_test":
    raise ValueError("Unsafe Chroma configuration")
for key in ("TEMP", "TMP", "TMPDIR"):
    os.environ[key] = str(base / "locks")
tempfile.tempdir = str(base / "locks")
original_request = LlamaCppProvider._request
def capture_request(provider, *args, **kwargs):
    response = original_request(provider, *args, **kwargs)
    if kwargs.get("stream"):
        original_lines = response.iter_lines
        def capture_lines(*line_args, **line_kwargs):
            with (base / "browser-provider-sse.bin").open("ab") as output:
                for line in original_lines(*line_args, **line_kwargs):
                    output.write((line if isinstance(line, bytes) else line.encode("utf-8")) + b"\n")
                    yield line
        response.iter_lines = capture_lines
    return response
LlamaCppProvider._request = capture_request
original_stream_chat = WorkspaceService.stream_chat
def capture_stream_chat(service, message, selection, expected_project_id, emit, session_id=None):
    with (base / "browser-workbench-ndjson.bin").open("wb") as output:
        def capture(event):
            output.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")
            output.flush()
            emit(event)
        return original_stream_chat(service, message, selection, expected_project_id, capture, session_id)
WorkspaceService.stream_chat = capture_stream_chat
import subprocess
chroma = Path(sys.executable).with_name("chroma.exe" if os.name == "nt" else "chroma")
child = subprocess.Popen([str(chroma), "run", "--host", "127.0.0.1", "--port", str(port),
                          "--path", str(base / "chroma-data")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
service = server = None
web_port = free_port()
try:
    wait_http(f"http://127.0.0.1:{port}/api/v2/heartbeat", child)
    while True:
        service = WorkspaceService(manifest_path, base / "Projects" / "Project-A", base / "Projects", base,
                                   registered_projects=[base / "External" / "Project-B"])
        server = ThreadingHTTPServer(("127.0.0.1", web_port), make_handler(service))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        service.start_sync()
        print(f"WORKBENCH=http://127.0.0.1:{web_port} CHROMA={port}", flush=True)
        command = sys.stdin.readline().strip()
        server.shutdown(); server.server_close(); server = None
        service.close(); service = None
        if command != "restart":
            break
finally:
    if server:
        server.shutdown(); server.server_close()
    if service:
        service.close()
    child.terminate()
    try: child.wait(timeout=10)
    except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=10)
