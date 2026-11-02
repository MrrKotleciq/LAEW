"""Opt-in live smoke test using a disposable workspace and in-memory retrieval.

Run with --provider and --model. --serve opens an isolated Workbench boundary for
manual/browser approval validation. No scheduler or production vector client starts.
"""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from http.server import ThreadingHTTPServer

import yaml

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.cloud_chat import CloudChatService
from laew.rag.sync import synchronize_scope
from laew.runtime import build_shared_tools
from laew.security.permissions import PermissionBroker
from laew.web import WorkspaceService, make_handler


class FixtureEmbedding:
    model, dimensions = "isolated-live-smoke", 3
    def embed(self, text): return [1., 0., 0.]
    def embed_batch(self, texts): return [self.embed(text) for text in texts]


def resource_digest(roots):
    digest = hashlib.sha256()
    count = 0
    for root in roots:
        for path in sorted(root.rglob("*.md")) if root.exists() else []:
            digest.update(str(path).encode())
            digest.update(path.read_bytes())
            count += 1
    return count, digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=["chatgpt", "openai-api", "gemini"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    app = Path(__file__).resolve().parents[1]
    root = app / "runtime" / "cloud-validation"
    root.mkdir(parents=True, exist_ok=True)
    protected = [Path("C:/ROOT/Knowledge"), Path("C:/ROOT/Projects/Studia")]
    before = resource_digest(protected)
    with tempfile.TemporaryDirectory(prefix="live-", dir=root) as temporary:
        workspace = Path(temporary)
        projects, vault = workspace / "Projects", workspace / "Knowledge"
        project = projects / "CloudIntegrationFixture"
        project.mkdir(parents=True); vault.mkdir()
        (project / "README.md").write_text("# Isolated fixture\nThe integration code is LAEW-CLOUD-7319.\n", encoding="utf-8")
        (project / "file.txt").write_text("FILE-READ-4826 Zażółć 🧬", encoding="utf-8")
        manifest = {"version": "1.0", "system_name": "isolated-smoke", "stage": "test",
            "workspace": {"root": str(project), "allowed_paths": [str(project)], "restricted_paths": [], "ignored_patterns": []},
            "models": {"roles": {"primary": {}, "embedding": {}, "reviewer": {}}},
            "memory": {"session": {}, "second_brain": {}},
            "tools": {"categories": {"filesystem": {"policy": "read_only_by_default"},
                "git": {"enabled": False, "policy": "inspection_first"},
                "terminal": {"enabled": False, "policy": "safe_command_allowlist", "allowlist": []},
                "web": {"enabled": False, "policy": "read_only"}}},
            "rag": {"pipeline": {}, "vector_store": {"enabled": False}},
            "agent": {"llm": {"providers": [{"name": "smoke", "type": args.provider, "model": args.model}],
                              "roles": {"primary": ["smoke"]}, "retry": {}}}}
        tools = build_shared_tools(project_root=project, projects_root=projects, knowledge_root=vault,
                                   manifest=manifest, rag_embedding_service=FixtureEmbedding())
        rag = next(t for t in tools if t.name == "RagTool")
        synchronize_scope(rag._pipeline.knowledge_base, "project")
        cloud = CloudChatService()
        account = None
        if args.provider == "chatgpt":
            accounts = [a for a in cloud.auth.status().get("accounts", []) if a["authenticated"]]
            if len(accounts) != 1:
                raise RuntimeError("The smoke test requires exactly one authenticated ChatGPT account.")
            account = accounts[0]["id"]
        provider = cloud.provider(args.provider, account)
        agent = Agent(AgentConfig(model=args.model, max_iterations=4), provider=provider, tools=tools)
        executor = AgentExecutor(agent)
        broker = PermissionBroker(project, "manual")
        if args.serve:
            manifest_path = workspace / "manifest.yaml"
            manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
            # Inject the already composed isolated runtime. The provider switch
            # path keeps exactly these tools, history and broker.
            service = WorkspaceService(manifest_path, project, projects, workspace)
            service._cloud, service._agent = cloud, agent
            service._executor, service._permissions = executor, broker
            service._provider_name, service._model, service._selection = args.provider, args.model, "manifest"
            service.sync_status = lambda: {"project": {"state": "ready"}, "global": {"state": "disabled"}}
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
            print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "workspace": str(workspace)}), flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close(); service.close()
        else:
            cases = [("text", "Reply exactly: LIVE-TEXT-OK", None, "LIVE-TEXT-OK"),
                     ("rag", "Use RagTool query with scope project to find the integration code in README.md. Reply with the code and source path.", "RagTool", "LAEW-CLOUD-7319"),
                     ("filesystem", "Use FilesystemTool view_file to read file.txt. Reply with the exact contents.", "FilesystemTool", "FILE-READ-4826")]
            results = []
            for name, prompt, required, expected in cases:
                result = executor.run(prompt, stream=True,
                    on_tool_call=lambda t, op, kw: broker.call(t, op, kw, None, "live-smoke"))
                passed = result.success and expected in result.final_response
                if required:
                    passed = passed and any(s.tool_name == required and s.tool_result.success for s in result.steps if s.tool_result)
                results.append({"case": name, "passed": passed, "error": result.error,
                                "response": result.final_response,
                                "tools": [s.tool_name for s in result.steps if s.tool_result]})
                print(json.dumps(results[-1]), flush=True)
                if not passed:
                    break
            cloud.close()
            if not all(r["passed"] for r in results):
                raise SystemExit(1)
    after = resource_digest(protected)
    print(json.dumps({"protected_markdown_files": before[0], "unchanged": before == after}), flush=True)
    assert before == after, "Protected resources changed during validation."


if __name__ == "__main__":
    main()
