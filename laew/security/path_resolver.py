"""Path resolver for LAEW multi-root workspace (ADR-010)."""

from pathlib import Path
from typing import Optional


class PathResolverError(Exception):
    """Raised when path resolution fails due to security violations."""


class PathResolver:
    """
    Resolves logical path aliases to absolute filesystem paths.

    Implements ADR-010 multi-root workspace boundaries and logical path aliasing.

    Aliases:
        - @project -> PROJECT_ROOT (current project repository)
        - @projects -> PROJECTS_ROOT (parent directory containing projects)
        - @knowledge -> GLOBAL_KNOWLEDGE_ROOT (Obsidian vault)

    Security:
        - Path traversal prevention (../ escaping root boundary)
        - Deny-by-default for unmapped paths
        - Restricted paths enforcement (.git, secrets, .env*)
    """

    ALIAS_PROJECT = "@project"
    ALIAS_PROJECTS = "@projects"
    ALIAS_KNOWLEDGE = "@knowledge"

    def __init__(
        self,
        project_root: Optional[Path | str] = None,
        projects_root: Optional[Path | str] = None,
        knowledge_root: Optional[Path | str] = None,
    ):
        """
        Initialize path resolver with logical root mappings.

        Args:
            project_root: PROJECT_ROOT path (defaults to cwd)
            projects_root: PROJECTS_ROOT path (defaults to ../)
            knowledge_root: GLOBAL_KNOWLEDGE_ROOT path (defaults to ../../KNOWLEDGE)
        """
        if project_root is None:
            self._project_root = Path.cwd().resolve()
        else:
            self._project_root = Path(project_root).resolve()

        if projects_root is None:
            self._projects_root = self._project_root.parent.resolve()
        else:
            self._projects_root = Path(projects_root).resolve()

        if knowledge_root is None:
            self._knowledge_root = self._projects_root.parent / "KNOWLEDGE"
        else:
            self._knowledge_root = Path(knowledge_root).resolve()

        self._alias_map = {
            self.ALIAS_PROJECT: self._project_root,
            self.ALIAS_PROJECTS: self._projects_root,
            self.ALIAS_KNOWLEDGE: self._knowledge_root,
        }

        self._restricted_paths = {".git", "secrets"}
        self._ignored_patterns = {".env", ".gguf", ".safetensors"}

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def projects_root(self) -> Path:
        return self._projects_root

    @property
    def knowledge_root(self) -> Path:
        return self._knowledge_root

    def resolve(self, aliased_path: str) -> Path:
        """
        Resolve an aliased path to an absolute filesystem path.

        Args:
            aliased_path: Path with optional alias prefix (e.g., "@project/docs/README.md")

        Returns:
            Absolute resolved path

        Raises:
            PathResolverError: If path violates security boundaries
        """
        # Determine alias and relative path
        if aliased_path == self.ALIAS_PROJECT:
            alias = self.ALIAS_PROJECT
            relative = "."
        elif aliased_path == self.ALIAS_PROJECTS:
            alias = self.ALIAS_PROJECTS
            relative = "."
        elif aliased_path == self.ALIAS_KNOWLEDGE:
            alias = self.ALIAS_KNOWLEDGE
            relative = "."
        elif aliased_path.startswith(self.ALIAS_PROJECT + "/"):
            alias = self.ALIAS_PROJECT
            relative = aliased_path[len(self.ALIAS_PROJECT) + 1 :]
        elif aliased_path.startswith(self.ALIAS_PROJECTS + "/"):
            alias = self.ALIAS_PROJECTS
            relative = aliased_path[len(self.ALIAS_PROJECTS) + 1 :]
        elif aliased_path.startswith(self.ALIAS_KNOWLEDGE + "/"):
            alias = self.ALIAS_KNOWLEDGE
            relative = aliased_path[len(self.ALIAS_KNOWLEDGE) + 1 :]
        elif aliased_path.startswith("@"):
            raise PathResolverError(f"Unknown path alias: {aliased_path}")
        else:
            # Default to @project for unprefixed paths
            alias = self.ALIAS_PROJECT
            relative = aliased_path

        # Get root for this alias
        root = self._alias_map[alias]

        # Resolve the path
        resolved = (root / relative).resolve()

        # Check path traversal (must be within root)
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathResolverError(
                f"Path traversal violation: {aliased_path} escapes {alias} boundary"
            )

        # Check restricted paths
        for part in resolved.parts:
            if part in self._restricted_paths:
                raise PathResolverError(
                    f"Access to restricted path denied: {part}"
                )

        # Check ignored patterns
        name = resolved.name
        for pattern in self._ignored_patterns:
            if pattern in name:
                raise PathResolverError(
                    f"Access to ignored pattern denied: {name}"
                )

        return resolved

    def is_within_root(self, path: Path, alias: str) -> bool:
        """
        Check if a path is within the specified logical root.

        Args:
            path: Absolute path to check
            alias: Logical root alias (@project, @knowledge, @projects)

        Returns:
            True if path is within the root, False otherwise
        """
        if alias not in self._alias_map:
            return False

        root = self._alias_map[alias]
        try:
            path.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    def get_alias_for_path(self, path: Path) -> Optional[str]:
        """
        Determine which logical root a path belongs to.

        Args:
            path: Absolute or relative path

        Returns:
            Alias string if path is within a known root, None otherwise
        """
        resolved = Path(path).resolve()

        for alias, root in self._alias_map.items():
            try:
                resolved.relative_to(root)
                return alias
            except ValueError:
                continue

        return None
