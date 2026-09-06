"""Layered prompt loader for LAEW prompt templates."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from laew.prompts.context_budget import TokenEstimator


@dataclass
class PromptSection:
    """
    A section of a prompt template.

    Attributes:
        name: Section identifier (e.g., 'identity', 'principles', 'examples')
        content: Section text content
        priority: Loading priority (lower numbers loaded first)
        required: Whether this section is required
    """

    name: str
    content: str
    priority: int = 0
    required: bool = True


@dataclass
class LayeredPrompt:
    """
    A layered prompt composed of multiple sections.

    Attributes:
        name: Prompt identifier
        sections: Dictionary of section name to PromptSection
        context_budget: Context budget allocation for this prompt
    """

    name: str
    sections: Dict[str, PromptSection] = field(default_factory=dict)
    context_budget: Optional[ContextBudget] = None

    def add_section(self, section: PromptSection) -> None:
        """Add a section to the prompt."""
        self.sections[section.name] = section

    def get_section(self, name: str) -> Optional[PromptSection]:
        """Get a section by name."""
        return self.sections.get(name)

    def remove_section(self, name: str) -> bool:
        """Remove a section by name. Returns True if removed."""
        if name in self.sections:
            del self.sections[name]
            return True
        return False

    def get_ordered_sections(self) -> List[PromptSection]:
        """
        Get sections ordered by priority.

        Returns:
            List of sections sorted by priority (ascending)
        """
        return sorted(self.sections.values(), key=lambda s: s.priority)

    def render(self) -> str:
        """
        Render the full prompt by concatenating sections in priority order.

        Returns:
            Complete prompt text
        """
        sections = self.get_ordered_sections()
        return "\n\n".join(section.content for section in sections)

    def estimate_tokens(self) -> int:
        """
        Estimate token count for the rendered prompt.

        Returns:
            Estimated token count
        """
        return TokenEstimator.estimate_prompt_sections(
            [section.content for section in self.get_ordered_sections()]
        )

    def is_within_budget(self) -> bool:
        """
        Check if prompt fits within context budget.

        Returns:
            True if prompt fits within budget
        """
        if not self.context_budget:
            return True  # No budget constraint

        estimated = self.estimate_tokens()
        return not self.context_budget.is_over_budget(estimated)


class PromptLoader:
    """
    Loads prompt templates from files and directories.

    Supports:
    - Individual prompt files (.md)
    - Directory-based prompts with section files
    - Layered composition from multiple sources
    """

    def __init__(self, base_paths: List[Path | str]):
        """
        Initialize prompt loader.

        Args:
            base_paths: List of directories to search for prompts
        """
        self.base_paths = [Path(p) for p in base_paths]
        self._prompt_cache: Dict[str, LayeredPrompt] = {}

    def load_prompt(self, name: str) -> LayeredPrompt:
        """
        Load a prompt by name.

        Searches for:
        - {name}.md (single file prompt)
        - {name}/ (directory with section files)
        - {name}.txt (legacy format)

        Args:
            name: Prompt name to load

        Returns:
            LayeredPrompt instance

        Raises:
            FileNotFoundError: If prompt not found
        """
        # Check cache first
        if name in self._prompt_cache:
            return self._prompt_cache[name]

        prompt = self._load_prompt_from_filesystem(name)
        self._prompt_cache[name] = prompt
        return prompt

    def _load_prompt_from_filesystem(self, name: str) -> LayeredPrompt:
        """Load prompt from filesystem."""
        prompt = LayeredPrompt(name=name)

        # Try to load as directory-based prompt first
        dir_prompt = self._load_directory_prompt(name)
        if dir_prompt:
            return dir_prompt

        # Fall back to single file prompt
        file_prompt = self._load_single_file_prompt(name)
        if file_prompt:
            return file_prompt

        raise FileNotFoundError(f"Prompt '{name}' not found in {self.base_paths}")

    def _load_directory_prompt(self, name: str) -> Optional[LayeredPrompt]:
        """Load prompt from directory with section files."""
        for base_path in self.base_paths:
            prompt_dir = base_path / name
            if prompt_dir.is_dir():
                prompt = LayeredPrompt(name=name)

                # Load all .md files in the directory as sections
                section_files = sorted(prompt_dir.glob("*.md"))
                for i, section_file in enumerate(section_files):
                    try:
                        content = section_file.read_text(encoding="utf-8")
                        section_name = section_file.stem
                        section = PromptSection(
                            name=section_name,
                            content=content.strip(),
                            priority=i,  # File order determines priority
                        )
                        prompt.add_section(section)
                    except Exception:
                        # Skip unreadable files
                        continue

                if prompt.sections:
                    return prompt

        return None

    def _load_single_file_prompt(self, name: str) -> Optional[LayeredPrompt]:
        """Load prompt from single file."""
        for base_path in self.base_paths:
            # Try .md extension first
            prompt_file = base_path / f"{name}.md"
            if prompt_file.is_file():
                try:
                    content = prompt_file.read_text(encoding="utf-8")
                    prompt = LayeredPrompt(name=name)
                    # Single file becomes one section
                    section = PromptSection(
                        name="main",
                        content=content.strip(),
                        priority=0,
                    )
                    prompt.add_section(section)
                    return prompt
                except Exception:
                    continue

            # Try without extension
            prompt_file = base_path / name
            if prompt_file.is_file():
                try:
                    content = prompt_file.read_text(encoding="utf-8")
                    prompt = LayeredPrompt(name=name)
                    section = PromptSection(
                        name="main",
                        content=content.strip(),
                        priority=0,
                    )
                    prompt.add_section(section)
                    return prompt
                except Exception:
                    continue

        return None

    def clear_cache(self) -> None:
        """Clear prompt cache."""
        self._prompt_cache.clear()

    def reload_prompt(self, name: str) -> LayeredPrompt:
        """Reload a prompt, bypassing cache."""
        self._prompt_cache.pop(name, None)
        return self.load_prompt(name)


# Global prompt loader instance
_default_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get the default prompt loader instance."""
    global _default_loader
    if _default_loader is None:
        # Default to LAEW prompts directory
        _default_loader = PromptLoader([Path("prompts")])
    return _default_loader


def set_prompt_loader(loader: PromptLoader) -> None:
    """Set the default prompt loader."""
    global _default_loader
    _default_loader = loader


def load_prompt(name: str) -> LayeredPrompt:
    """Convenience function to load a prompt."""
    return get_prompt_loader().load_prompt(name)