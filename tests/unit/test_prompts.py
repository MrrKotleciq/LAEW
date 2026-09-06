"""Tests for LAEW prompt management and context budgeting system."""

import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from laew.prompts import (
    ContextBudget,
    LayeredPrompt,
    PromptLoader,
    PromptSection,
    PromptTemplate,
    PromptTemplateRegistry,
    TokenEstimator,
)
from laew.prompts.context_budget import TokenEstimator


class TestContextBudget:
    """Tests for ContextBudget class."""

    def test_default_budget(self):
        """Test default context budget values."""
        budget = ContextBudget()
        assert budget.system == 2000
        assert budget.conversation == 4000
        assert budget.rag == 8000
        assert budget.tools == 4000
        assert budget.total == 18000
        assert budget.reserved == 2000

    def test_custom_budget(self):
        """Test custom context budget values."""
        budget = ContextBudget(
            system=1000,
            conversation=2000,
            rag=4000,
            tools=2000,
            total=10000,
            reserved=1000,
        )
        assert budget.system == 1000
        assert budget.conversation == 2000
        assert budget.rag == 4000
        assert budget.tools == 2000
        assert budget.total == 10000
        assert budget.reserved == 1000

    def test_budget_validation(self):
        """Test budget validation on initialization."""
        # Valid budget
        budget = ContextBudget(
            system=1000,
            conversation=2000,
            rag=3000,
            tools=2000,
            total=10000,
            reserved=2000
        )
        assert budget.available_for_prompt() == 8000

        # Invalid budget should raise ValueError (allocated > total)
        with pytest.raises(ValueError):
            ContextBudget(
                system=5000,
                conversation=5000,
                rag=5000,
                tools=5000,
                total=10000,
                reserved=2000
            )

    def test_available_for_prompt(self):
        """Test available tokens for prompt content."""
        budget = ContextBudget(
            system=2000,
            conversation=4000,
            rag=8000,
            tools=2000,
            total=18000,
            reserved=2000
        )
        assert budget.available_for_prompt() == 16000

    def test_used_percentage(self):
        """Test context usage percentage calculation."""
        budget = ContextBudget(
            system=2000,
            conversation=4000,
            rag=8000,
            tools=4000,
            total=20000,
            reserved=0,
        )
        # Used: 2000+4000+8000+4000 = 18000 out of 20000 = 0.9
        assert budget.used_percentage() == 0.9

    def test_is_over_budget(self):
        """Test over-budget detection."""
        budget = ContextBudget(
            system=1000,
            conversation=2000,
            rag=3000,
            tools=2000,
            total=10000,
            reserved=2000
        )  # 8000 available
        assert budget.is_over_budget(9000) is True
        assert budget.is_over_budget(8000) is False
        assert budget.is_over_budget(7000) is False


class TestTokenEstimator:
    """Tests for TokenEstimator class."""

    def test_estimate_empty(self):
        """Test estimation for empty string."""
        assert TokenEstimator.estimate("") == 0

    def test_estimate_short_text(self):
        """Test estimation for short text."""
        # "Hello" = 5 chars, ~1 token (5/4 = 1.25 -> 1)
        assert TokenEstimator.estimate("Hello") == 1

    def test_estimate_medium_text(self):
        """Test estimation for medium text."""
        # "Hello world" = 11 chars, ~2 tokens (11/4 = 2.75 -> 2)
        assert TokenEstimator.estimate("Hello world") == 2

    def test_estimate_long_text(self):
        """Test estimation for long text."""
        text = "x" * 100  # 100 chars
        # 100/4 = 25 tokens
        assert TokenEstimator.estimate(text) == 25

    def test_estimate_messages(self):
        """Test estimation for message list."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        # "Hello Hi there!" = 13 chars -> ~3 tokens
        assert TokenEstimator.estimate_messages(messages) == 3

    def test_estimate_prompt_sections(self):
        """Test estimation for prompt sections."""
        sections = ["Section one", "Section two", "Section three"]
        # "Section one\n\nSection two\n\nSection three" = 37 chars -> ~9 tokens (37 // 4 = 9)
        assert TokenEstimator.estimate_prompt_sections(sections) == 9


class TestPromptSection:
    """Tests for PromptSection class."""

    def test_section_creation(self):
        """Test creating a prompt section."""
        section = PromptSection(
            name="identity",
            content="You are a helpful assistant.",
            priority=10,
            required=True,
        )
        assert section.name == "identity"
        assert section.content == "You are a helpful assistant."
        assert section.priority == 10
        assert section.required is True

    def test_section_defaults(self):
        """Test section with default values."""
        section = PromptSection(name="test", content="test content")
        assert section.priority == 0
        assert section.required is True


class TestLayeredPrompt:
    """Tests for LayeredPrompt class."""

    def test_prompt_creation(self):
        """Test creating a layered prompt."""
        prompt = LayeredPrompt(name="test-prompt")
        assert prompt.name == "test-prompt"
        assert len(prompt.sections) == 0

    def test_add_section(self):
        """Test adding sections to prompt."""
        prompt = LayeredPrompt(name="test")
        section1 = PromptSection(name="first", content="First", priority=1)
        section2 = PromptSection(name="second", content="Second", priority=0)

        prompt.add_section(section1)
        prompt.add_section(section2)

        assert len(prompt.sections) == 2
        assert "first" in prompt.sections
        assert "second" in prompt.sections

    def test_get_section(self):
        """Test retrieving a section."""
        prompt = LayeredPrompt(name="test")
        section = PromptSection(name="test-section", content="content")
        prompt.add_section(section)

        retrieved = prompt.get_section("test-section")
        assert retrieved is not None
        assert retrieved.content == "content"

        # Non-existent section
        assert prompt.get_section("nonexistent") is None

    def test_remove_section(self):
        """Test removing sections."""
        prompt = LayeredPrompt(name="test")
        section = PromptSection(name="remove-me", content="content")
        prompt.add_section(section)

        # Remove existing section
        result = prompt.remove_section("remove-me")
        assert result is True
        assert len(prompt.sections) == 0

        # Remove non-existent section
        result = prompt.remove_section("nonexistent")
        assert result is False

    def test_get_ordered_sections(self):
        """Test section ordering by priority."""
        prompt = LayeredPrompt(name="test")
        prompt.add_section(PromptSection(name="low", content="Low", priority=10))
        prompt.add_section(PromptSection(name="high", content="High", priority=0))
        prompt.add_section(PromptSection(name="medium", content="Medium", priority=5))

        ordered = prompt.get_ordered_sections()
        assert len(ordered) == 3
        assert ordered[0].name == "high"   # priority 0
        assert ordered[1].name == "medium" # priority 5
        assert ordered[2].name == "low"    # priority 10

    def test_render_empty(self):
        """Test rendering empty prompt."""
        prompt = LayeredPrompt(name="empty")
        assert prompt.render() == ""

    def test_render_single_section(self):
        """Test rendering prompt with single section."""
        prompt = LayeredPrompt(name="single")
        section = PromptSection(name="only", content="Single section content")
        prompt.add_section(section)

        rendered = prompt.render()
        assert rendered == "Single section content"

    def test_render_multiple_sections(self):
        """Test rendering prompt with multiple sections."""
        prompt = LayeredPrompt(name="multiple")
        prompt.add_section(PromptSection(name="first", content="First", priority=1))
        prompt.add_section(PromptSection(name="second", content="Second", priority=0))
        prompt.add_section(PromptSection(name="third", content="Third", priority=2))

        rendered = prompt.render()
        # Should be ordered by priority: second, first, third
        expected = "Second\n\nFirst\n\nThird"
        assert rendered == expected

    def test_estimate_tokens(self):
        """Test token estimation for prompt."""
        prompt = LayeredPrompt(name="test")
        prompt.add_section(PromptSection(name="sec1", content="Hello world"))
        prompt.add_section(PromptSection(name="sec2", content="Foo bar"))

        # "Hello world\n\nFoo bar" = 21 chars -> ~5 tokens (21 // 4 = 5)
        assert prompt.estimate_tokens() == 5

    def test_is_within_budget(self):
        """Test budget checking."""
        prompt = LayeredPrompt(name="test-budget")
        prompt.add_section(PromptSection(name="content", content="Short content"))
        budget = ContextBudget(
            system=100,
            conversation=200,
            rag=300,
            tools=200,
            total=1000,
            reserved=200
        )  # 800 available
        prompt.context_budget = budget

        # Short content should be within budget
        assert prompt.is_within_budget() is True

        # Mock oversized estimation
        with patch.object(TokenEstimator, "estimate_prompt_sections", return_value=1000):
            assert prompt.is_within_budget() is False


class TestPromptLoader:
    """Tests for PromptLoader class."""

    def test_loader_initialization(self):
        """Test prompt loader initialization."""
        paths = [Path("/tmp/prompts")]
        loader = PromptLoader(paths)
        assert len(loader.base_paths) == 1
        assert loader.base_paths[0] == Path("/tmp/prompts")

    def test_load_single_file_prompt(self):
        """Test loading prompt from single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir()
            prompt_file = prompts_dir / "test.md"
            prompt_file.write_text("# Test Prompt\n\nThis is a test.", encoding="utf-8")

            loader = PromptLoader([prompts_dir])
            prompt = loader.load_prompt("test")

            assert prompt.name == "test"
            assert len(prompt.sections) == 1
            assert prompt.sections["main"].content == "# Test Prompt\n\nThis is a test."

    def test_load_directory_prompt(self):
        """Test loading prompt from directory with sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir()
            prompt_dir = prompts_dir / "test"
            prompt_dir.mkdir()

            # Create section files
            (prompt_dir / "00-identity.md").write_text("You are helpful.", encoding="utf-8")
            (prompt_dir / "01-task.md").write_text("Perform the task.", encoding="utf-8")
            (prompt_dir / "02-examples.md").write_text("Example: do X.", encoding="utf-8")

            loader = PromptLoader([prompts_dir])
            prompt = loader.load_prompt("test")

            assert prompt.name == "test"
            assert len(prompt.sections) == 3
            assert prompt.sections["00-identity"].content == "You are helpful."
            assert prompt.sections["01-task"].content == "Perform the task."
            assert prompt.sections["02-examples"].content == "Example: do X."

            # Check ordering (by filename, which should reflect priority)
            ordered = prompt.get_ordered_sections()
            assert ordered[0].name == "00-identity"
            assert ordered[1].name == "01-task"
            assert ordered[2].name == "02-examples"

    def test_load_prompt_not_found(self):
        """Test loading non-existent prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir()

            loader = PromptLoader([prompts_dir])

            with pytest.raises(FileNotFoundError, match="Prompt 'nonexistent' not found"):
                loader.load_prompt("nonexistent")

    def test_loader_cache(self):
        """Test prompt caching."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts_dir = Path(tmpdir) / "prompts"
            prompts_dir.mkdir()
            prompt_file = prompts_dir / "cached.md"
            prompt_file.write_text("Cached content", encoding="utf-8")

            loader = PromptLoader([prompts_dir])

            # First load
            prompt1 = loader.load_prompt("cached")
            # Second load (should come from cache)
            prompt2 = loader.load_prompt("cached")

            # Should be the same object from cache
            assert prompt1 is prompt2

            # Clear cache and load again
            loader.clear_cache()
            prompt3 = loader.load_prompt("cached")
            assert prompt3 is not prompt1  # Different object after cache clear

    def test_get_prompt_loader_singleton(self):
        """Test global prompt loader singleton."""
        from laew.prompts.loader import get_prompt_loader, set_prompt_loader

        # Get default loader
        loader1 = get_prompt_loader()
        loader2 = get_prompt_loader()
        assert loader1 is loader2  # Same instance

        # Set custom loader
        custom_loader = PromptLoader([Path("/custom")])
        set_prompt_loader(custom_loader)
        loader3 = get_prompt_loader()
        assert loader3 is custom_loader


class TestPromptTemplate:
    """Tests for PromptTemplate class."""

    def test_template_creation(self):
        """Test creating a prompt template."""
        template = PromptTemplate(
            name="greeting",
            template="Hello {{name}}, you are {{age}} years old.",
        )
        assert template.name == "greeting"
        assert template.template == "Hello {{name}}, you are {{age}} years old."
        assert template.variables == {"name", "age"}

    def test_template_no_variables(self):
        """Test template with no variables."""
        template = PromptTemplate(
            name="static",
            template="This is static content.",
        )
        assert template.variables == set()

    def test_template_render(self):
        """Test template rendering."""
        template = PromptTemplate(
            name="greeting",
            template="Hello {{name}}, you are {{age}} years old.",
        )

        result = template.render({"name": "Alice", "age": "30"})
        assert result == "Hello Alice, you are 30 years old."

    def test_template_render_with_extra_context(self):
        """Test template rendering with extra context variables."""
        template = PromptTemplate(
            name="greeting",
            template="Hello {{name}}!",
        )

        # Extra variables should be ignored
        result = template.render({"name": "Alice", "age": "30", "unused": "value"})
        assert result == "Hello Alice!"

    def test_template_render_missing_variable(self):
        """Test template rendering with missing variable."""
        template = PromptTemplate(
            name="greeting",
            template="Hello {{name}}!",
        )

        with pytest.raises(KeyError, match="Missing required template variables: \\['name'\\]"):
            template.render({})  # Missing 'name'

    def test_template_render_multiple_missing(self):
        """Test template rendering with multiple missing variables."""
        template = PromptTemplate(
            name="greeting",
            template="Hello {{name}}, you are {{age}} years old from {{city}}.",
        )

        with pytest.raises(KeyError) as exc_info:
            template.render({"name": "Alice"})  # Missing age and city

        assert "Missing required template variables" in str(exc_info.value)
        assert "age" in str(exc_info.value)
        assert "city" in str(exc_info.value)

    def test_template_validate_context(self):
        """Test context validation."""
        template = PromptTemplate(
            name="test",
            template="Hello {{name}}!",
        )

        # Valid context
        errors = template.validate_context({"name": "World"})
        assert errors == []

        # Missing variable
        errors = template.validate_context({})
        assert len(errors) == 1
        assert "Missing required variables" in errors[0]

        # Extra variables (should be ok, just warning)
        errors = template.validate_context({"name": "World", "extra": "value"})
        assert errors == []  # Extra variables are allowed

    def test_template_complex_variables(self):
        """Test template with complex variable names."""
        template = PromptTemplate(
            name="complex",
            template="The {{user_id}} processed {{item_count}} items in {{processing_time}} seconds.",
        )
        assert template.variables == {"user_id", "item_count", "processing_time"}

        result = template.render(
            {
                "user_id": "user123",
                "item_count": "42",
                "processing_time": "1.5",
            }
        )
        assert result == "The user123 processed 42 items in 1.5 seconds."


class TestPromptTemplateRegistry:
    """Tests for PromptTemplateRegistry class."""

    def test_registry_creation(self):
        """Test creating template registry."""
        registry = PromptTemplateRegistry()
        assert len(registry.list_templates()) == 0

    def test_register_and_get_template(self):
        """Test registering and retrieving templates."""
        registry = PromptTemplateRegistry()
        template = PromptTemplate(name="test", template="Hello {{name}}")

        registry.register(template)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"
        assert retrieved.template == "Hello {{name}}"

        # Non-existent template
        assert registry.get("nonexistent") is None

    def test_render_from_registry(self):
        """Test rendering template from registry."""
        registry = PromptTemplateRegistry()
        template = PromptTemplate(name="greeting", template="Hello {{name}}!")
        registry.register(template)

        result = registry.render("greeting", {"name": "Alice"})
        assert result == "Hello Alice!"

    def test_render_nonexistent_template(self):
        """Test rendering non-existent template."""
        registry = PromptTemplateRegistry()
        with pytest.raises(KeyError, match="Template 'nonexistent' not found"):
            registry.render("nonexistent", {})

    def test_list_templates(self):
        """Test listing registered templates."""
        registry = PromptTemplateRegistry()
        t1 = PromptTemplate(name="first", template="First")
        t2 = PromptTemplate(name="second", template="Second")
        t3 = PromptTemplate(name="third", template="Third")

        registry.register(t1)
        registry.register(t2)
        registry.register(t3)

        templates = registry.list_templates()
        assert len(templates) == 3
        assert "first" in templates
        assert "second" in templates
        assert "third" in templates

    def test_clear_registry(self):
        """Test clearing template registry."""
        registry = PromptTemplateRegistry()
        template = PromptTemplate(name="test", template="Test")
        registry.register(template)

        assert len(registry.list_templates()) == 1
        registry.clear()
        assert len(registry.list_templates()) == 0

    def test_global_registry_functions(self):
        """Test global template registry functions."""
        from laew.prompts.templates import (
            get_template_registry,
            register_template,
            get_template,
            render_template,
            clear_registry,
        )

        # Start with clean registry
        clear_registry()

        # Register template
        template = PromptTemplate(name="global-test", template="Value: {{value}}")
        register_template(template)

        # Get template
        retrieved = get_template("global-test")
        assert retrieved is not None
        assert retrieved.name == "global-test"

        # Render template
        result = render_template("global-test", {"value": "42"})
        assert result == "Value: 42"

        # Non-existent template
        assert get_template("nonexistent") is None
        with pytest.raises(KeyError):
            render_template("nonexistent", {})

        # Clean up
        clear_registry()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])