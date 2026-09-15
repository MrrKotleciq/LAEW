"""Tests for application-level logging configuration (Milestone 11: Phase 3)."""

import logging

import pytest

from laew.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _reset_laew_logger():
    """Ensure each test starts from (and ends with) a clean 'laew' logger."""
    logger = logging.getLogger("laew")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


class TestConfigureLogging:
    """Tests for the app-level logging setup."""

    def test_returns_laew_logger(self):
        logger = configure_logging(level=logging.INFO)
        assert logger.name == "laew"

    def test_sets_level(self):
        configure_logging(level=logging.DEBUG)
        assert logging.getLogger("laew").level == logging.DEBUG

    def test_console_handler_added(self):
        configure_logging(level=logging.INFO)
        logger = logging.getLogger("laew")
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        assert stream_handlers, "a console handler should be attached"

    def test_idempotent_no_duplicate_handlers(self):
        configure_logging(level=logging.INFO)
        configure_logging(level=logging.INFO)
        assert len(logging.getLogger("laew").handlers) == 1

    def test_file_handler_creates_file(self, tmp_path):
        log_file = tmp_path / "laew.log"
        configure_logging(level=logging.INFO, log_file=str(log_file))
        logger = logging.getLogger("laew")
        rotating = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert rotating, "a rotating file handler should be attached"
        # Rotation sizing configured, not default no-limit values.
        assert rotating[0].maxBytes > 0
        assert rotating[0].backupCount >= 1

        logger.info("hello app log")
        for handler in logger.handlers:
            handler.flush()
        assert log_file.exists()
        assert "hello app log" in log_file.read_text(encoding="utf-8")

    def test_file_handler_idempotent(self, tmp_path):
        log_file = tmp_path / "laew.log"
        configure_logging(level=logging.INFO, log_file=str(log_file))
        configure_logging(level=logging.INFO, log_file=str(log_file))
        logger = logging.getLogger("laew")
        rotating = [
            h for h in logger.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating) == 1

    def test_does_not_clobber_tool_logger(self):
        """configure_logging must leave the 'laew.tools' logger handlers intact."""
        from laew.tools import get_tool_logger  # noqa: F401 - side effect only

        tool_logger = logging.getLogger("laew.tools")
        before = list(tool_logger.handlers)

        configure_logging(level=logging.INFO)

        assert list(tool_logger.handlers) == before