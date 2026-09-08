"""Documentation validation tests.

These tests ensure that documentation accurately reflects the repository state:
- README structure matches actual directories
- PROJECT_STATUS reflects current implementation state
- No stale references to removed/non-existent paths
"""

import os
from pathlib import Path

import pytest
import yaml

from laew.manifest import load_manifest, ManifestError


class TestReadmeStructure:
    """Test that README.md accurately describes repository structure."""

    def test_readme_lists_existing_directories_only(self):
        """README should not list non-existent directories as part of core structure."""
        readme_path = Path("README.md")
        assert readme_path.exists(), "README.md should exist"

        content = readme_path.read_text(encoding="utf-8")

        # Extract the repository structure section if it exists
        # Look for code blocks or lists describing structure
        lines = content.split('\n')
        in_structure_section = False
        structure_lines = []

        for line in lines:
            # Simple heuristic: look for structure indicators
            if "Repository Structure" in line or "## Repository Structure" in line:
                in_structure_section = True
                continue
            elif in_structure_section and line.startswith("## ") and "Repository Structure" not in line:
                # Next section started
                break
            elif in_structure_section:
                structure_lines.append(line)

        structure_content = '\n'.join(structure_lines)

        # Check that non-existent directories are NOT listed as core parts
        # These were mentioned in old README but don't exist
        nonexistent_dirs = ["configs/", "docker/", "scripts/"]
        for dir_name in nonexistent_dirs:
            # If the old structure format is present, it should not list these
            # But we allow them to be mentioned elsewhere in docs
            # The key is they shouldn't be in the main structure listing
            if f"├── {dir_name}" in structure_content or f"└── {dir_name}" in structure_content:
                # This would be an error - documenting non-existent dirs as core structure
                pytest.fail(f"README falsely lists {dir_name} as part of core repository structure")

    def test_readme_describes_correct_core_directories(self):
        """README should list the actual core directories that exist."""
        readme_path = Path("README.md")
        content = readme_path.read_text(encoding="utf-8")

        # These directories should exist and be referenced appropriately
        expected_dirs = ["laew/", "docs/", "manifests/", "prompts/", "tests/", "tools/"]

        # At least most of these should be mentioned somewhere in README
        found_count = 0
        for dir_name in expected_dirs:
            if dir_name in content:
                found_count += 1

        # Should find at least 4 of the 6 expected directories
        assert found_count >= 4, f"README should mention core directories, only found {found_count}/{len(expected_dirs)}"


class TestProjectStatusAccuracy:
    """Test that PROJECT_STATUS.md reflects current state accurately."""

    def test_project_status_mentions_correct_test_count(self):
        """PROJECT_STATUS should mention the current test count (266)."""
        status_path = Path("docs/PROJECT_STATUS.md")
        assert status_path.exists(), "docs/PROJECT_STATUS.md should exist"

        content = status_path.read_text(encoding="utf-8")

        # Should mention 266 tests (current count after our fixes)
        assert "266" in content, "PROJECT_STATUS should mention 266 unit tests"
        assert "264" not in content or content.count("264") < content.count("266"), \
            "PROJECT_STATUS should primarily reference 266 tests, not outdated 264"

    def test_project_status_mentions_correct_test_suites(self):
        """PROJECT_STATUS should mention current test suite count (14)."""
        status_path = Path("docs/PROJECT_STATUS.md")
        content = status_path.read_text(encoding="utf-8")

        # Should mention 14 test suites (current count)
        assert "14 test suites" in content or "14 test files" in content, \
            "PROJECT_STATUS should mention 14 test suites/files"

    def test_project_status_shows_correct_current_focus(self):
        """PROJECT_STATUS should show current focus is Milestone 5, not planning M4."""
        status_path = Path("docs/PROJECT_STATUS.md")
        content = status_path.read_text(encoding="utf-8")

        # Should NOT say immediate objective is to plan M4 (that's outdated)
        assert "immediate objective" not in content.lower() or \
               "plan and implement milestone 4" not in content.lower(), \
            "PROJECT_STATUS should not state that immediate objective is to plan M4"

        # Should mention current focus or completed milestones
        assert ("milestone 5" in content.lower() or
                "documentation & health consolidation" in content.lower() or
                "current focus" in content.lower()), \
            "PROJECT_STATUS should indicate current work focus"


class TestManifestConsistency:
    """Test that manifest is internally consistent and valid."""

    def test_manifest_loads_without_errors(self):
        """The system manifest should be valid YAML and load successfully."""
        manifest_path = Path("manifests/SYSTEM_MANIFEST.yaml")
        assert manifest_path.exists(), "manifests/SYSTEM_MANIFEST.yaml should exist"

        # Should load without throwing exception
        manifest_dict = load_manifest(str(manifest_path))
        assert manifest_dict is not None
        assert manifest_dict["version"] == "1.0"
        assert manifest_dict["system_name"] == "LAEW"

    def test_manifest_has_required_sections(self):
        """Manifest should have all required sections for LAEW operation."""
        manifest_dict = load_manifest("manifests/SYSTEM_MANIFEST.yaml")

        # Check required sections exist
        assert manifest_dict["workspace"] is not None
        assert manifest_dict["models"] is not None
        assert manifest_dict["tools"] is not None
        assert manifest_dict["memory"] is not None
        assert manifest_dict["rag"] is not None

        # Check model roles
        roles = manifest_dict["models"]["roles"]
        assert "primary" in roles
        assert "embedding" in roles
        assert "reviewer" in roles

        # Check tool categories
        categories = manifest_dict["tools"]["categories"]
        assert "filesystem" in categories
        assert "git" in categories
        assert "terminal" in categories
        assert "web" in categories

        # Check memory layers
        memory = manifest_dict["memory"]
        assert memory["session"] is not None
        assert memory["second_brain"] is not None

        # Check RAG pipeline
        assert manifest_dict["rag"]["pipeline"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])