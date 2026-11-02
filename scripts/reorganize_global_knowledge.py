"""Apply an audited vault path migration, preserving bytes except link targets.

This maintenance script requires a verified external backup/plan. It stops on
unexpected file changes and records each step; it never performs blind rollback.
"""

import argparse
import hashlib
import json
import os
import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote

import yaml


WIKI = re.compile(r"(!?\[\[)([^\]\n]+)(\]\])")
MARKDOWN = re.compile(r"(!?\[[^\]\n]*\]\()([^\n)]*)(\))")


def rewrite_links(text: str, old_note: str, new_note: str, moves: dict[str, str]) -> str:
    """Rewrite qualified wikilinks and moved-note-relative Markdown targets.

    Unqualified note names, aliases, headings, block IDs and embed markers are
    retained. External URLs and absolute source paths are left untouched.
    """
    stems = {old.removesuffix(".md"): new.removesuffix(".md") for old, new in moves.items()}

    def wiki(match):
        target, *suffix = re.split(r"(?=[#|])", match.group(2), maxsplit=1)
        rooted = target.startswith("/")
        key = target.lstrip("/")
        if key in moves:
            target = moves[key]
        elif key in stems:
            target = stems[key]
        else:
            return match.group(0)
        return match.group(1) + ("/" if rooted else "") + target + "".join(suffix) + match.group(3)

    def markdown(match):
        raw = match.group(2)
        wrapped = raw.startswith("<") and ">" in raw
        if wrapped:
            end = raw.index(">")
            url, title = raw[1:end], raw[end + 1:]
        else:
            parts = re.split(r"(?=\s+[\"'])", raw, maxsplit=1)
            url, title = parts[0], parts[1] if len(parts) > 1 else ""
        if not url or url.startswith(("#", "/", "\\")) or re.match(r"^[a-zA-Z][\w+.-]*:", url):
            return match.group(0)
        path, separator, fragment = url.partition("#")
        decoded = unquote(path)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(old_note), decoded))
        destination = moves.get(resolved, resolved)
        if old_note == new_note and destination == resolved:
            return match.group(0)
        relative = posixpath.relpath(destination, posixpath.dirname(new_note) or ".")
        if "%" in path:
            relative = quote(relative, safe="/.-_~")
        value = relative + (separator + fragment if separator else "")
        value = ("<" + value + ">" if wrapped else value) + title
        return match.group(1) + value + match.group(3)

    return MARKDOWN.sub(markdown, WIKI.sub(wiki, text))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_plan(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    vault = Path("C:/ROOT/Knowledge")
    assert vault.resolve(strict=True) == vault
    backup = Path(plan["backup"])
    before = json.loads((backup / "files.json").read_text(encoding="utf-8"))
    assert plan["verified"] and (backup / "vault-before.zip").is_file()
    actual = {p.relative_to(vault).as_posix(): digest(p) for p in vault.rglob("*") if p.is_file()}
    assert actual == {p: info["sha256"] for p, info in before.items()}, "Vault changed since verified backup"
    moves = plan["moves"]
    original = {old: (vault / old).read_bytes() for old in moves}
    staged = plan_path.parent / "new-files"
    additions = {"README.md": staged / "README.md", "templates/inbox.md": staged / "inbox.md"}
    for target, source in additions.items():
        assert source.is_file() and not (vault / target).exists(), target
    templates_config = vault / ".obsidian/templates.json"
    assert not templates_config.exists(), "Unexpected Templates settings; re-audit before changing"
    for old, new in moves.items():
        if old.casefold() != new.casefold():
            assert not (vault / new).exists(), f"Destination conflict: {new}"

    journal = {"id": plan["id"], "backup": str(backup), "moves": moves, "steps": [], "files": []}
    def save():
        (plan_path.parent / "migration-journal.json").write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
    def safe(path):
        path.resolve().relative_to(vault)
        return path
    def move_folder(old, new):
        source, target = safe(vault / old), safe(vault / new)
        assert source.is_dir()
        target.parent.mkdir(parents=True, exist_ok=True)
        if old.casefold() == new.casefold():
            assert os.path.samefile(source, target)
            temporary = safe(vault / (".laew-case-" + plan["id"] + "-" + target.name))
            assert not temporary.exists()
            source.rename(temporary)
            journal["steps"].append({"from": old, "to": temporary.name})
            save()
            temporary.rename(target)
        else:
            assert not target.exists()
            source.rename(target)
        journal["steps"].append({"from": temporary.name if old.casefold() == new.casefold() else old,
                                  "to": new, "logical_from": old})
        save()
    save()
    try:
        for old, new in (("Knowledge/ai", "topics/ai"), ("Knowledge/security", "topics/security"),
                         ("Research", "research"), ("Decisions", "decisions"), ("Templates", "templates")):
            move_folder(old, new)
        safe(vault / "Knowledge").rmdir()  # only an empty redundant container
        safe(vault / "inbox").mkdir(exist_ok=False)
        for old, new in moves.items():
            path = safe(vault / new)
            assert path.read_bytes() == original[old]
            old_text = original[old].decode("utf-8")
            updated = rewrite_links(old_text, old, new, moves)
            # There are no path-valued frontmatter relations in this audited vault.
            assert yaml.safe_load(old_text.split("---", 2)[1]) == yaml.safe_load(updated.split("---", 2)[1])
            if updated != old_text:
                path.write_bytes(updated.encode("utf-8"))
            journal["files"].append({"old": old, "new": new, "before": hashlib.sha256(original[old]).hexdigest(),
                                     "after": digest(path), "links_changed": updated != old_text})
            save()
        for relative, source in additions.items():
            target = safe(vault / relative)
            with target.open("xb") as handle:
                handle.write(source.read_bytes())
        with templates_config.open("x", encoding="utf-8") as handle:
            json.dump({"folder": "templates"}, handle, indent=2)
            handle.write("\n")
        for name, info in before.items():
            if name.startswith("."):
                assert digest(vault / name) == info["sha256"], name
        assert len(list(vault.glob("**/*.md"))) == len(moves) + len(additions)
        journal["result"] = "migrated"
    except Exception as exc:
        journal["result"] = "stopped"
        journal["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        save()
    print(f"Migrated {len(moves)} notes; original frontmatter and existing plugin/cache files preserved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-plan", required=True, type=Path)
    apply_plan(parser.parse_args().apply_plan)
