"""Tests for the multi-agent shared context store (ADR-018)."""

import dataclasses

from laew.multiagent.context import SharedContext, SharedContextItem


class TestSharedContextItem:
    def test_item_is_frozen(self):
        """SharedContextItem is immutable."""
        item = SharedContextItem(key="k", content="c", source="s", created_at="t")
        assert dataclasses.is_dataclass(item)
        assert item.__dataclass_params__.frozen

    def test_str_format(self):
        """__str__ shows key, source, and content."""
        item = SharedContextItem(
            key="finding",
            content="the answer",
            source="researcher",
            created_at="now",
        )
        text = str(item)
        assert "finding" in text
        assert "researcher" in text
        assert "the answer" in text


class TestSharedContext:
    def test_post_and_get(self):
        """A posted item can be retrieved by key."""
        ctx = SharedContext()
        item = ctx.post("api_endpoints", "GET /v1/history", "researcher")
        assert ctx.get("api_endpoints") == item

    def test_get_missing_key_returns_none(self):
        """Getting an unknown key returns None."""
        ctx = SharedContext()
        assert ctx.get("missing") is None

    def test_post_strips_content(self):
        """Content is whitespace-trimmed on posting."""
        ctx = SharedContext()
        item = ctx.post("k", "  padded value  ", "researcher")
        assert item.content == "padded value"

    def test_all_for_returns_insertion_order(self):
        """Multiple posts for one key are returned oldest-first."""
        ctx = SharedContext()
        first = ctx.post("k", "one", "r1")
        second = ctx.post("k", "two", "r2")
        assert ctx.all_for("k") == [first, second]

    def test_get_returns_latest(self):
        """get() returns the most recent post for the key."""
        ctx = SharedContext()
        ctx.post("k", "one", "r1")
        latest = ctx.post("k", "two", "r2")
        assert ctx.get("k") == latest

    def test_keys_in_first_insertion_order(self):
        ctx = SharedContext()
        ctx.post("b", "1", "r")
        ctx.post("a", "2", "r")
        ctx.post("b", "3", "r")
        assert ctx.keys() == ["b", "a"]

    def test_len_counts_items(self):
        ctx = SharedContext()
        ctx.post("a", "1", "r")
        ctx.post("b", "2", "r")
        ctx.post("a", "3", "r")
        assert len(ctx) == 3

    def test_render_empty_returns_empty_string(self):
        """Rendering an empty context is blank (safe for prompt injection)."""
        ctx = SharedContext()
        assert ctx.render() == ""

    def test_render_includes_items(self):
        ctx = SharedContext()
        ctx.post("finding", "the answer", "researcher")
        rendered = ctx.render()
        assert "Shared context:" in rendered
        assert "[finding]" in rendered
        assert "researcher" in rendered
        assert "the answer" in rendered

    def test_render_custom_header(self):
        ctx = SharedContext()
        ctx.post("finding", "the answer", "researcher")
        rendered = ctx.render("Accumulated context:")
        assert rendered.startswith("Accumulated context:")

    def test_render_lists_all_items_in_order(self):
        ctx = SharedContext()
        ctx.post("a", "first", "r1")
        ctx.post("b", "second", "r2")
        rendered = ctx.render()
        first_idx = rendered.index("[a]")
        second_idx = rendered.index("[b]")
        assert first_idx < second_idx

    def test_clear_resets(self):
        ctx = SharedContext()
        ctx.post("a", "1", "r")
        ctx.clear()
        assert len(ctx) == 0
        assert ctx.keys() == []