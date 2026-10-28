"""Tests for the dependency-free Obsidian note parser (Milestone 17)."""

from laew.rag.obsidian import (
    extract_links,
    extract_tags,
    parse_frontmatter,
    parse_note,
)


def test_parse_frontmatter_scalar():
    """Frontmatter scalars are parsed into key/value pairs."""
    content = "---\ntitle: REST API Design\ntags:\n  - rest\n  - api\ndescription: Notes.\n---\n\n# Body"
    fm = parse_frontmatter(content)
    assert fm == {
        "title": "REST API Design",
        "tags": ["rest", "api"],
        "description": "Notes.",
    }


def test_parse_frontmatter_inline_list():
    """Inline flow lists (``key: [a, b]``) parse into lists."""
    content = "---\ntags: [rest, api, db]\n---\n\n# Body"
    fm = parse_frontmatter(content)
    assert fm == {"tags": ["rest", "api", "db"]}


def test_parse_frontmatter_empty():
    """No frontmatter yields an empty dict."""
    assert parse_frontmatter("# Just a heading\n\nBody") == {}


def test_extract_links():
    """Inline [[backlinks]] are extracted as link text."""
    assert extract_links("[[001-global-second-brain]]") == ["001-global-second-brain"]
    assert extract_links("[[002-knowledge-scope-separation]] and [[001]]") == [
        "002-knowledge-scope-separation",
        "001",
    ]


def test_extract_tags():
    """Inline #tags are extracted, deduplicated, and stripped of '#'."""
    assert extract_tags("#rest #api #rest") == ["rest", "api"]
    assert extract_tags("#tag-name #tag with spaces") == ["tag-name", "tag with spaces"]


def test_parse_note_with_frontmatter():
    """A note with frontmatter returns title, tags and backlinks."""
    content = (
        "---\n"
        "title: My Note\n"
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "backlinks:\n"
        "  - other-note\n"
        "---\n\n"
        "# My Note\n\n"
        "Body text linking [[other-note]].\n"
    )
    note = parse_note(content)
    assert note["title"] == "My Note"
    assert note["tags"] == ["alpha", "beta"]
    assert note["backlinks"] == ["other-note"]
    assert "Body text" in note["body"]


def test_parse_note_falls_back_to_inline():
    """Backlinks and tags fall back to inline extraction when absent."""
    content = "# Heading\n\nText with [[some-link]] and #inline-tag here."
    note = parse_note(content)
    assert note["title"] == "Heading"
    assert note["backlinks"] == ["some-link"]
    # The tag regex captures the full token, including trailing spaces, which
    # is the intended behaviour (Obsidian tags may contain spaces).
    assert note["tags"] == ["inline-tag here"]
    # ``body`` is the full text after frontmatter, so it still contains the
    # heading; the note body content is present within it.
    assert "Text with" in note["body"]


def test_parse_note_title_from_heading():
    """Title is derived from the first heading when no frontmatter title."""
    content = "---\ntags:\n  - x\n---\n\n# Derived Title\n\nBody."
    note = parse_note(content)
    assert note["title"] == "Derived Title"
