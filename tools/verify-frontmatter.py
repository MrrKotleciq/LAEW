"""Verify the frontmatter block of specific docs files. Read-only."""

import sys
import yaml


def parse_frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    if not lines or lines[0].strip() != "---":
        return None, "no frontmatter"
    start, end = 0, None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "no closing frontmatter"
    block = "\n".join(lines[start:end])
    try:
        return yaml.safe_load(block), "OK"
    except Exception as e:
        return None, f"PARSE FAIL: {e}"


def main():
    targets = sys.argv[1:]
    for path in targets:
        doc, status = parse_frontmatter(path)
        if status == "OK":
            print(f"{path}\n  -> {status}\n  type: {doc.get('type')}, id: {doc.get('id')}")
        else:
            print(f"{path}\n  -> {status}")
            print("  --- frontmatter block (first 20 lines) ---")
            block = "\n".join(
                open(path, encoding="utf-8").read().split("\n")[:20]
            )
            print(block)


if __name__ == "__main__":
    main()
