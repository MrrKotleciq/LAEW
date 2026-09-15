"""Security-audit configuration tests (Milestone 11: Phase 4).

Verifies the bandit SAST gate and security-review documentation stay
consistent with the repo:
- pyproject.toml declares a [tool.bandit] config
- CI runs bandit over laew/
- docs/security/SECURITY_REVIEW.md records the audit
"""

from pathlib import Path


class TestSecurityAuditConfig:
    """Tests for the security audit tooling + documentation."""

    def test_pyproject_has_bandit_config(self):
        pyproject = Path("pyproject.toml")
        assert pyproject.exists(), "pyproject.toml should exist"
        content = pyproject.read_text(encoding="utf-8")
        assert "[tool.bandit]" in content

    def test_pyproject_bandit_excludes_tests(self):
        pyproject = Path("pyproject.toml")
        content = pyproject.read_text(encoding="utf-8")
        # Bandit should not be required to pass on tests.
        assert "tests" in content
        assert "exclude" in content

    def test_pyproject_bandit_sets_skip_profile(self):
        pyproject = Path("pyproject.toml")
        content = pyproject.read_text(encoding="utf-8")
        # CI gate should not fail on low-severity findings by default.
        assert "skips" in content

    def test_ci_runs_bandit(self):
        ci = Path(".github/workflows/ci.yml")
        assert ci.exists(), "CI workflow should exist"
        content = ci.read_text(encoding="utf-8")
        assert "bandit" in content.lower()
        # Bandit must scan the package source, not just be installed.
        assert "bandit -r laew" in content or "bandit --recursive laew" in content

    def test_security_review_doc_exists(self):
        review = Path("docs/security/SECURITY_REVIEW.md")
        assert review.exists(), "docs/security/SECURITY_REVIEW.md should exist"
        content = review.read_text(encoding="utf-8")
        assert content.strip(), "SECURITY_REVIEW.md should not be empty"
        assert "bandit" in content.lower()

    def test_security_review_records_milestone(self):
        review = Path("docs/security/SECURITY_REVIEW.md")
        content = review.read_text(encoding="utf-8")
        assert "Milestone 11" in content or "m11" in content.lower()