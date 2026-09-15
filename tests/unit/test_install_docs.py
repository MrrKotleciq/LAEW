"""Installation guide documentation tests (Milestone 11: Phase 2).

These tests ensure the packaging guides stay accurate:
- docs/INSTALL.md exists and covers pip install, venv, Ollama, env vars
- README.md has an Installation entry point
- README env-var docs stay consistent with INSTALL.md
"""

from pathlib import Path


class TestInstallationDocs:
    """Tests that installation guides exist and are self-consistent."""

    def test_install_doc_exists(self):
        install_path = Path("docs/INSTALL.md")
        assert install_path.exists(), "docs/INSTALL.md should exist"
        content = install_path.read_text(encoding="utf-8")
        assert content.strip(), "docs/INSTALL.md should not be empty"

    def test_install_doc_mentions_pip_install(self):
        content = Path("docs/INSTALL.md").read_text(encoding="utf-8")
        assert "pip install" in content.lower()

    def test_install_doc_mentions_virtualenv(self):
        content = Path("docs/INSTALL.md").read_text(encoding="utf-8")
        assert "venv" in content.lower() or "virtualenv" in content.lower()

    def test_install_doc_mentions_ollama(self):
        content = Path("docs/INSTALL.md").read_text(encoding="utf-8")
        assert "ollama" in content.lower()

    def test_install_doc_mentions_provider_config(self):
        """INSTALL.md should document env-var overrides for provider config."""
        content = Path("docs/INSTALL.md").read_text(encoding="utf-8")
        for var in ("LAEW_TIMEOUT", "LAEW_BASE_URL"):
            assert var in content, f"INSTALL.md should document {var}"

    def test_readme_mentions_installation(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        assert "installation" in readme.lower()

    def test_readme_env_vars_match_install_doc(self):
        """Any LAEW_* env var named in README must also appear in INSTALL.md."""
        readme = Path("README.md").read_text(encoding="utf-8")
        install = Path("docs/INSTALL.md").read_text(encoding="utf-8")
        # Extract well-formed env-var tokens (backticks/commas stripped).
        readme_vars = {
            w.strip("`,;.")
            for w in readme.split()
            if w.strip("`,;.").startswith("LAEW_")
        }
        assert readme_vars, "README should document at least one LAEW_* env var"
        for var in readme_vars:
            assert var in install, f"INSTALL.md should document {var}"

    def test_pyproject_exists_and_declares_script(self):
        """pyproject.toml must exist and expose the 'laew' console script."""
        pyproject = Path("pyproject.toml")
        assert pyproject.exists(), "pyproject.toml should exist"
        content = pyproject.read_text(encoding="utf-8")
        assert "laew = " in content  # [project.scripts] entry
        assert "[project]" in content
        assert 'name = "laew"' in content