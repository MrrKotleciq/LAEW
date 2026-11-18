"""Contract checks for offline, restriction-aware Markdown chunking."""

from laew.eval.final_rag_preflight import adaptive_chunks


def _assert_payloads(text, offset, chunks):
    for chunk in chunks:
        assert 0 < chunk["end"] - chunk["start"] <= 1600
        assert chunk["text"] == text[chunk["start"] - offset:chunk["end"] - offset]


def test_heading_paths_follow_real_sibling_ancestry():
    text = "# Root\n\n## First\nFirst content.\n\n## Second\nSecond content.\n\n### Detail\nDetail content.\n"
    chunks, withheld = adaptive_chunks(" " * 37 + text, 37, [])
    assert not withheld
    _assert_payloads(text, 37, chunks)
    second = next(chunk for chunk in chunks if "Second content." in chunk["text"])
    detail = next(chunk for chunk in chunks if "Detail content." in chunk["text"])
    assert any("Root" in heading for heading in second["path"])
    assert any("Second" in heading for heading in second["path"])
    assert all("First" not in heading for heading in second["path"])
    assert any("Detail" in heading for heading in detail["path"])
    assert all("First" not in heading for heading in detail["path"])


def test_restricted_line_removes_whole_table_and_chunks_never_bridge_gap():
    text = ("# Safe\nBefore text.\n\n| Name | Value |\n| --- | --- |\n"
            "| public | 1 |\n| secret | 2 |\n| public | 3 |\n\nAfter text.\n")
    offset = 100
    secret = text.index("secret")
    chunks, withheld = adaptive_chunks(" " * offset + text, offset, [(offset + secret, offset + secret + 2)])
    _assert_payloads(text, offset, chunks)
    table_start = offset + text.index("| Name")
    table_end = offset + text.index("\n\nAfter")
    assert any(row["kind"] == "table" and row["reason"] == "restricted" for row in withheld)
    assert all(chunk["end"] <= table_start or chunk["start"] >= table_end for chunk in chunks)
    assert any("Before text." in chunk["text"] for chunk in chunks)
    assert any("After text." in chunk["text"] for chunk in chunks)
    assert all(not (chunk["start"] < table_start and chunk["end"] > table_end) for chunk in chunks)


def test_long_unicode_narrative_has_bounded_exact_slices():
    text = "# Żółć\n\n" + ("Zażółć gęślą jaźń 🐈 — tekst. " * 350)
    offset = 211
    chunks, withheld = adaptive_chunks(" " * offset + text, offset, [])
    assert chunks
    assert not withheld
    _assert_payloads(text, offset, chunks)
    assert all(chunks[i]["end"] <= chunks[i + 1]["start"] for i in range(len(chunks) - 1))
    assert sum(len(chunk["text"]) for chunk in chunks) >= len(text) - 10


def test_oversized_code_and_table_are_withheld():
    code = "```python\n" + ("print('hello')\n" * 150) + "```\n"
    table = "| Key | Value |\n| --- | --- |\n" + ("| example | value |\n" * 100)
    text = "# Data\n\n" + code + "\n" + table + "\nDone.\n"
    offset = 13
    chunks, withheld = adaptive_chunks(" " * offset + text, offset, [])
    _assert_payloads(text, offset, chunks)
    for block in (code, table):
        start = offset + text.index(block)
        end = start + len(block.rstrip("\n"))
        assert any(row["start"] <= start and row["end"] >= end for row in withheld)
        assert all(chunk["end"] <= start or chunk["start"] >= end for chunk in chunks)


def test_small_table_and_list_remain_whole():
    table = "| A | B |\n| --- | --- |\n| one | two |\n"
    listing = "- first item\n- second item\n- third item\n"
    text = "# Example\n\n" + table + "\n" + listing
    chunks, withheld = adaptive_chunks(text, 0, [])
    assert not withheld
    _assert_payloads(text, 0, chunks)
    assert any(table.rstrip() in chunk["text"] for chunk in chunks)
    assert any(listing.rstrip() in chunk["text"] for chunk in chunks)
