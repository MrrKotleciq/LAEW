"""Prompt template system with variable substitution."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern


@dataclass
class PromptTemplate:
    """
    A prompt template with variable substitution capabilities.

    Attributes:
        name: Template name
        template: Template string with {{variable}} placeholders
        variables: Set of required variable names
        compiled_pattern: Compiled regex for variable extraction
    """

    name: str
    template: str
    variables: Set[str] = field(default_factory=set)
    compiled_pattern: Optional[Pattern] = field(default=None, init=False)

    def __post_init__(self):
        """Extract variable names from template and compile pattern."""
        # Find all {{variable}} patterns
        variable_pattern = r"\{\{([^}]+)\}\}"
        matches = re.findall(variable_pattern, self.template)
        self.variables = set(matches)
        self.compiled_pattern = re.compile(variable_pattern)

    def render(self, context: Dict[str, Any]) -> str:
        """
        Render template with variable substitution.

        Args:
            context: Dictionary mapping variable names to values

        Returns:
            Rendered template string

        Raises:
            KeyError: If required variable is missing
        """
        # Check for missing required variables
        missing = self.variables - set(context.keys())
        if missing:
            raise KeyError(f"Missing required template variables: {sorted(missing)}")

        def replace_match(match):
            var_name = match.group(1).strip()
            return str(context.get(var_name, match.group(0)))  # fallback to original

        return self.compiled_pattern.sub(replace_match, self.template)

    def validate_context(self, context: Dict[str, Any]) -> List[str]:
        """
        Validate context against template requirements.

        Args:
            context: Dictionary to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for missing required variables
        missing = self.variables - set(context.keys())
        if missing:
            errors.append(f"Missing required variables: {sorted(missing)}")

        # Check for unknown variables (warning, not error)
        unknown = set(context.keys()) - self.variables
        if unknown:
            # This is just informational - extra variables are ignored
            pass

        return errors


class PromptTemplateRegistry:
    """
    Registry for managing prompt templates.

    Provides template caching, loading, and retrieval.
    """

    def __init__(self):
        """Initialize empty template registry."""
        self._templates: Dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        """
        Register a template.

        Args:
            template: PromptTemplate to register
        """
        self._templates[template.name] = template

    def get(self, name: str) -> Optional[PromptTemplate]:
        """
        Get a template by name.

        Args:
            name: Template name

        Returns:
            PromptTemplate or None if not found
        """
        return self._templates.get(name)

    def render(self, name: str, context: Dict[str, Any]) -> str:
        """
        Render a template by name.

        Args:
            name: Template name
            context: Variable substitution context

        Returns:
            Rendered template string

        Raises:
            KeyError: If template not found or missing variables
        """
        template = self.get(name)
        if template is None:
            raise KeyError(f"Template '{name}' not found")
        return template.render(context)

    def list_templates(self) -> List[str]:
        """
        List all registered template names.

        Returns:
            List of template names
        """
        return list(self._templates.keys())

    def clear(self) -> None:
        """Clear all registered templates."""
        self._templates.clear()


# Global template registry instance
_template_registry: Optional[PromptTemplateRegistry] = None


def get_template_registry() -> PromptTemplateRegistry:
    """Get the global template registry instance."""
    global _template_registry
    if _template_registry is None:
        _template_registry = PromptTemplateRegistry()
    return _template_registry


def register_template(template: PromptTemplate) -> None:
    """Register a template with the global registry."""
    get_template_registry().register(template)


def get_template(name: str) -> Optional[PromptTemplate]:
    """Get a template from the global registry."""
    return get_template_registry().get(name)


def render_template(name: str, context: Dict[str, Any]) -> str:
    """Render a template from the global registry."""
    return get_template_registry().render(name, context)


def clear_registry() -> None:
    """Clear the global template registry."""
    get_template_registry().clear()