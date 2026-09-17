"""Tests for laew.console.session_store (Milestone 13).

Covers:
- name validation (path traversal, empty, invalid chars)
- CRUD: save / load / list / delete
- atomic writes (temp file + os.replace)
- corrupt / missing-file handling
- file permission hardening (best-effort)
- session isolation (names stay in their directory)
- make_chat_payload / validate_conversation helpers
- lifecycle timestamps (created_at preserved, updated_at refreshed)
"""

import json
import os
import time
from pathlib import Path

import pytest

from laew.console.session_store import (
    PAYLOAD_SCHEMA,
    PAYLOAD_VERSION,
    InvalidSessionName,
    SessionRecord,
    SessionStore,
    SessionStoreError,
    make_chat_payload,
    validate_conversation,
    validate_payload,
    validate_session_name,
)

from laew.console.session_store import utc_now


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #
@pytest.fixture
def store(tmp_path):
    """A SessionStore rooted in a temporary directory."""
    return SessionStore(tmp_path / "sessions")


@pytest.fixture
def sample_chat_payload():
    """A minimal, valid chat payload."""
    return {
        "schema": PAYLOAD_SCHEMA,
        "version": PAYLOAD_VERSION,
        "kind": "chat",
        "manifest_path": "manifests/SYSTEM_MANIFEST.yaml",
        "conversation": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ],
    }


@pytest.fixture
def sample_console_payload():
    """A minimal, valid console payload."""
    return {
        "schema": PAYLOAD_SCHEMA,
        "version": PAYLOAD_VERSION,
        "kind": "console",
        "manifest_path": "manifests/SYSTEM_MANIFEST.yaml",
        "overrides": {"model": "llama3.1"},
        "approval": "ask",
        "trace": True,
        "history": ["check", "info"],
        "conversation": [
            {"role": "user", "content": "hi"},
        ],
    }


# ------------------------------------------------------------------ #
# Name validation
# ------------------------------------------------------------------ #
class TestValidateSessionName:
    """Path traversal and malformed name rejection."""

    def test_valid_names(self):
        """Simple, dot-, dash-, underscore-containing names pass."""
        for name in ("research", "my.session", "my-session", "my_session", "a1"):
            assert validate_session_name(name) == name

    def test_empty_name(self):
        """Empty string is rejected."""
        with pytest.raises(InvalidSessionName):
            validate_session_name("")

    def test_dot_traversal(self):
        """'..' and '.' are rejected."""
        for name in (".", ".."):
            with pytest.raises(InvalidSessionName):
                validate_session_name(name)

    def test_slash_traversal(self):
        """Forward and backslashes are rejected."""
        for name in ("foo/bar", "foo\\bar", "../etc/passwd"):
            with pytest.raises(InvalidSessionName):
                validate_session_name(name)

    def test_leading_dot(self):
        """Names starting with a dot are rejected."""
        with pytest.raises(InvalidSessionName):
            validate_session_name(".hidden")

    def test_whitespace(self):
        """Whitespace-containing names are rejected."""
        with pytest.raises(InvalidSessionName):
            validate_session_name("my session")

    def test_none_raises(self):
        """Non-string input is rejected."""
        with pytest.raises(InvalidSessionName):
            validate_session_name(None)  # type: ignore[arg-type]


# ------------------------------------------------------------------ #
# make_chat_payload
# ------------------------------------------------------------------ #
class TestMakeChatPayload:
    """Chat payload construction and validation."""

    def test_chat_payload_structure(self, sample_chat_payload):
        """Produces a validated chat payload."""
        payload = make_chat_payload(
            sample_chat_payload["manifest_path"],
            sample_chat_payload["conversation"],
        )
        assert payload["schema"] == PAYLOAD_SCHEMA
        assert payload["version"] == PAYLOAD_VERSION
        assert payload["kind"] == "chat"
        assert payload["manifest_path"] == sample_chat_payload["manifest_path"]
        assert payload["conversation"] == sample_chat_payload["conversation"]

    def test_chat_payload_has_no_console_fields(self, sample_chat_payload):
        """Chat payloads never carry console-only fields."""
        payload = make_chat_payload(
            sample_chat_payload["manifest_path"],
            sample_chat_payload["conversation"],
        )
        assert "overrides" not in payload
        assert "approval" not in payload
        assert "trace" not in payload
        assert "history" not in payload

    def test_invalid_conversation_role(self):
        """Non-user/assistant roles are rejected."""
        with pytest.raises(SessionStoreError):
            make_chat_payload(
                "m.yaml",
                [{"role": "system", "content": "hi"}],
            )

    def test_invalid_conversation_content_type(self):
        """Non-string content is rejected."""
        with pytest.raises(SessionStoreError):
            make_chat_payload(
                "m.yaml",
                [{"role": "user", "content": 42}],
            )


# ------------------------------------------------------------------ #
# validate_conversation
# ------------------------------------------------------------------ #
class TestValidateConversation:
    """Conversation normalization and validation."""

    def test_valid_conversation(self):
        """Valid conversation passes through unchanged."""
        conv = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        result = validate_conversation(conv)
        assert result == conv

    def test_empty_conversation(self):
        """Empty list is valid."""
        assert validate_conversation([]) == []

    def test_non_list(self):
        """Non-list input is rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation("not a list")  # type: ignore[arg-type]

    def test_non_dict_entry(self):
        """Non-dict entries are rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation([42])  # type: ignore[list-item]

    def test_missing_role(self):
        """Entry missing 'role' is rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation([{"content": "hi"}])  # type: ignore[dict-item]

    def test_missing_content(self):
        """Entry missing 'content' is rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation([{"role": "user"}])  # type: ignore[dict-item]

    def test_invalid_role(self):
        """Roles other than user/assistant are rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation([{"role": "system", "content": "hi"}])

    def test_non_string_content(self):
        """Non-string content values are rejected."""
        with pytest.raises(SessionStoreError):
            validate_conversation([{"role": "user", "content": 42}])


# ------------------------------------------------------------------ #
# CRUD
# ------------------------------------------------------------------ #
class TestSessionStoreCRUD:
    """Save / load / list / delete lifecycle."""

    def test_save_creates_file(self, store, sample_console_payload):
        """save() writes a .json file and returns a SessionRecord."""
        record = store.save("research", sample_console_payload)
        assert isinstance(record, SessionRecord)
        assert record.name == "research"
        assert record.kind == "console"
        assert (store.path_for("research")).is_file()

    def test_load_round_trip(self, store, sample_console_payload):
        """save() followed by load() returns the same envelope."""
        store.save("research", sample_console_payload)
        loaded = store.load("research")
        assert loaded["kind"] == "console"
        assert loaded["manifest_path"] == sample_console_payload["manifest_path"]
        assert len(loaded["conversation"]) == 1

    def test_load_missing_raises(self, store):
        """load() for a nonexistent name raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            store.load("nonexistent")

    def test_list_empty(self, store):
        """list_sessions() returns [] when the directory is empty."""
        assert store.list_sessions() == []

    def test_list_sorted_newest_first(self, store, sample_console_payload):
        """list_sessions() returns sessions ordered by updated_at desc."""
        payload1 = dict(sample_console_payload, conversation=[{"role": "user", "content": "a"}])
        payload2 = dict(sample_console_payload, conversation=[{"role": "user", "content": "b"}])
        store.save("alpha", payload1)
        store.save("beta", payload2)
        records = store.list_sessions()
        assert len(records) == 2
        assert records[0].name == "beta"  # newer first
        assert records[1].name == "alpha"

    def test_list_returns_metadata_only(self, store, sample_console_payload):
        """list_sessions() records do not include conversation content."""
        store.save("research", sample_console_payload)
        records = store.list_sessions()
        assert len(records) == 1
        record = records[0]
        assert isinstance(record, SessionRecord)
        assert hasattr(record, "history_count")
        assert hasattr(record, "conversation_count")

    def test_delete_existing(self, store, sample_console_payload):
        """delete() removes the file and returns True."""
        store.save("research", sample_console_payload)
        assert store.delete("research") is True
        assert not (store.path_for("research")).is_file()

    def test_delete_missing_returns_false(self, store):
        """delete() for a nonexistent name returns False."""
        assert store.delete("missing") is False

    def test_exists(self, store, sample_console_payload):
        """exists() reflects whether a session is stored."""
        assert not store.exists("research")
        store.save("research", sample_console_payload)
        assert store.exists("research")

    def test_save_overwrite_preserves_created_at(self, store, sample_console_payload):
        """save() on an existing name preserves the original created_at."""
        store.save("research", sample_console_payload)
        record1 = store.list_sessions()[0]
        time.sleep(0.01)  # ensure updated_at differs
        store.save("research", sample_console_payload)
        record2 = store.list_sessions()[0]
        assert record1.created_at == record2.created_at
        assert record1.updated_at != record2.updated_at


# ------------------------------------------------------------------ #
# Atomic writes
# ------------------------------------------------------------------ #
class TestAtomicWrites:
    """Crash-safety via temp file + os.replace."""

    def test_atomic_write_no_partial_file(self, store, sample_console_payload):
        """After a successful save, only the final .json file exists —
        no leftover .tmp files."""
        store.save("research", sample_console_payload)
        tmp_files = list(store.directory.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_write_fully_readable(self, store, sample_console_payload):
        """The saved file is valid JSON immediately after save."""
        store.save("research", sample_console_payload)
        loaded = store.load("research")
        assert loaded["kind"] == "console"


# ------------------------------------------------------------------ #
# Corrupt / missing files
# ------------------------------------------------------------------ #
class TestCorruptHandling:
    """Corrupt or missing files fail gracefully."""

    def test_load_corrupt_json(self, store):
        """A file with invalid JSON raises SessionStoreError on load."""
        path = store.path_for("bad")
        store.directory.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        with pytest.raises(SessionStoreError):
            store.load("bad")

    def test_load_corrupt_no_schema(self, store):
        """A file with valid JSON but wrong schema is rejected."""
        path = store.path_for("bad")
        store.directory.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"wrong": "schema"}, f)
        with pytest.raises(SessionStoreError):
            store.load("bad")

    def test_list_skips_corrupt(self, store, sample_console_payload):
        """list_sessions() skips corrupt files instead of crashing."""
        store.save("good", sample_console_payload)
        corrupt_path = store.directory / "corrupt.json"
        corrupt_path.write_text("{bad json")
        records = store.list_sessions()
        assert len(records) == 1
        assert records[0].name == "good"


# ------------------------------------------------------------------ #
# Permission hardening (best-effort)
# ------------------------------------------------------------------ #
class TestPermissionHardening:
    """File permissions are restricted where the platform allows.

    Windows (NTFS) does not map Unix-style mode bits via chmod, so the
    hardened-mode assertions are POSIX-only; the calls themselves are still
    verified to be best-effort no-ops everywhere via test_harden_file_*.
    """

    @pytest.mark.skipif(os.name == "nt", reason="chmod mode bits are POSIX-only")
    def test_directory_hardened(self, store, sample_console_payload):
        """The session directory gets 0o700 permissions (best-effort)."""
        store.save("research", sample_console_payload)
        mode = store.directory.stat().st_mode & 0o777
        assert mode <= 0o700

    @pytest.mark.skipif(os.name == "nt", reason="chmod mode bits are POSIX-only")
    def test_file_hardened(self, store, sample_console_payload):
        """Saved session files get 0o600 permissions (best-effort)."""
        store.save("research", sample_console_payload)
        path = store.path_for("research")
        mode = path.stat().st_mode & 0o777
        assert mode <= 0o600

    def test_harden_file_not_critical_on_failure(self):
        """_harden_file never raises; it swallows OSError."""
        from laew.console.session_store import _harden_file
        # Should not raise even for a nonexistent path.
        _harden_file(Path("/nonexistent/path/file.json"))


# ------------------------------------------------------------------ #
# Isolation
# ------------------------------------------------------------------ #
class TestSessionIsolation:
    """Session names stay within their store directory."""

    def test_path_for_never_escapes(self, store):
        """path_for() always returns a path inside the store directory."""
        path = store.path_for("a")
        assert str(path).startswith(str(store.directory))

    def test_different_stores_are_isolated(self, tmp_path):
        """Two SessionStores with different directories don't share files."""
        store_a = SessionStore(tmp_path / "a")
        store_b = SessionStore(tmp_path / "b")
        payload = {
            "schema": PAYLOAD_SCHEMA,
            "version": PAYLOAD_VERSION,
            "kind": "console",
            "manifest_path": "m.yaml",
            "conversation": [],
        }
        store_a.save("session", payload)
        assert not store_b.exists("session")
        assert store_a.exists("session")


# ------------------------------------------------------------------ #
# Validate payload
# ------------------------------------------------------------------ #
class TestValidatePayload:
    """Payload envelope validation."""

    def test_validate_payload_valid(self, sample_console_payload):
        """Valid payload passes."""
        result = validate_payload(sample_console_payload)
        assert result["schema"] == PAYLOAD_SCHEMA

    def test_validate_payload_wrong_schema(self):
        """Wrong schema marker is rejected."""
        with pytest.raises(SessionStoreError):
            validate_payload({"schema": "wrong", "version": 1})

    def test_validate_payload_wrong_version(self):
        """Wrong version is rejected."""
        with pytest.raises(SessionStoreError):
            validate_payload({"schema": PAYLOAD_SCHEMA, "version": 99})

    def test_validate_payload_missing_manifest_path(self):
        """Missing manifest_path is rejected."""
        with pytest.raises(SessionStoreError):
            validate_payload({
                "schema": PAYLOAD_SCHEMA,
                "version": PAYLOAD_VERSION,
                "kind": "chat",
            })

    def test_validate_payload_invalid_kind(self):
        """Unknown kind is rejected."""
        with pytest.raises(SessionStoreError):
            validate_payload({
                "schema": PAYLOAD_SCHEMA,
                "version": PAYLOAD_VERSION,
                "kind": "unknown",
                "manifest_path": "m.yaml",
                "conversation": [],
            })


# ------------------------------------------------------------------ #
# Lifecycle timestamps
# ------------------------------------------------------------------ #
class TestLifecycleTimestamps:
    """created_at is preserved on overwrite; updated_at is always refreshed."""

    def test_created_at_set_on_new(self, store, sample_console_payload):
        """A new session gets a created_at timestamp."""
        record = store.save("research", sample_console_payload)
        assert record.created_at
        assert len(record.created_at) > 0

    def test_updated_at_refreshed(self, store, sample_console_payload):
        """updated_at is set on every save."""
        store.save("research", sample_console_payload)
        record1 = store.list_sessions()[0]
        time.sleep(0.01)
        store.save("research", sample_console_payload)
        record2 = store.list_sessions()[0]
        assert record2.updated_at >= record1.updated_at


# ------------------------------------------------------------------ #
# SessionRecord
# ------------------------------------------------------------------ #
class TestSessionRecord:
    """SessionRecord is a frozen dataclass with the right fields."""

    def test_record_fields(self, store, sample_console_payload):
        """record has all expected attributes."""
        record = store.save("research", sample_console_payload)
        assert record.name == "research"
        assert record.kind == "console"
        assert record.history_count >= 0
        assert record.conversation_count >= 0
        assert record.size_bytes >= 0
        assert isinstance(record.created_at, str)
        assert isinstance(record.updated_at, str)