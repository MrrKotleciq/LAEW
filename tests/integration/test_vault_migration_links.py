"""Obsidian syntax survives the path-only migration helper."""

from scripts.reorganize_global_knowledge import rewrite_links
from scripts.validate_knowledge_preparation import layout_prefixes


def test_preserves_aliases_headings_blocks_embeds_and_qualified_extension():
    moves = {"Knowledge/ai/Note.md": "topics/ai/Note.md"}
    text = "[[Note]] [[Note|Alias]] [[Note#Heading]] [[Note#^block-id]] "
    assert rewrite_links(text, "profile/a.md", "profile/a.md", moves) == text
    qualified = "[[Knowledge/ai/Note]] [[Knowledge/ai/Note|Alias]] [[Knowledge/ai/Note#Heading|Alias]] ![[Knowledge/ai/Note#^block-id]] [[Knowledge/ai/Note.md]]"
    expected = "[[topics/ai/Note]] [[topics/ai/Note|Alias]] [[topics/ai/Note#Heading|Alias]] ![[topics/ai/Note#^block-id]] [[topics/ai/Note.md]]"
    assert rewrite_links(qualified, "profile/a.md", "profile/a.md", moves) == expected


def test_relative_links_in_unmoved_and_moved_notes_keep_targets():
    moves = {"Knowledge/ai/Note.md": "topics/ai/Note.md", "Research/Note Two.md": "research/Note Two.md"}
    text = '[link](../Knowledge/ai/Note.md#Heading "title") ![image](../assets/image.png)'
    assert rewrite_links(text, "profile/a.md", "profile/a.md", moves) == '[link](../topics/ai/Note.md#Heading "title") ![image](../assets/image.png)'
    text = '[link](../../Research/Note%20Two.md#heading) ![image](../../assets/image.png)'
    assert rewrite_links(text, "Knowledge/ai/Note.md", "topics/ai/Note.md", moves) == '[link](../../research/Note%20Two.md#heading) ![image](../../assets/image.png)'
    external = '[source](C:/ROOT/Projects/LAEW/docs/README.md) [web](https://example.com/Knowledge/a) [local](#heading)'
    assert rewrite_links(external, "Knowledge/ai/Note.md", "topics/ai/Note.md", moves) == external


def test_frontmatter_wikilink_relation_preserves_yaml_and_breadcrumbs_field():
    moves = {"Decisions/policy.md": "decisions/policy.md"}
    text = '---\nup: "[[Decisions/policy#^block|Policy]]"\ntags: [existing]\n---\nBody\n'
    expected = '---\nup: "[[decisions/policy#^block|Policy]]"\ntags: [existing]\n---\nBody\n'
    assert rewrite_links(text, "profile/a.md", "profile/a.md", moves) == expected


def test_validation_script_supports_both_layouts_without_case_guessing(tmp_path):
    for name in ("Knowledge", "Research", "Decisions"):
        (tmp_path / name).mkdir()
    assert layout_prefixes(tmp_path) == ("Knowledge", "Research", "Decisions")
    for old, new in (("Knowledge", "topics"), ("Research", "research"), ("Decisions", "decisions")):
        temporary = tmp_path / ("temporary-" + old)
        (tmp_path / old).rename(temporary)
        temporary.rename(tmp_path / new)
    assert layout_prefixes(tmp_path) == ("topics", "research", "decisions")
