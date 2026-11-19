import hashlib
import io
import json
import os
import stat
from uuid import uuid4
import zipfile

import pytest

from laew.backup import archive
from laew.backup.archive import ArchiveError, ArchiveLimits, seal_archive, validate_member_name, verify_archive


@pytest.fixture
def fixture(tmp_path):
    media = tmp_path / "sealed"
    media.mkdir(mode=0o700)
    staged = tmp_path / "note.md"
    staged.write_bytes("Zażółć\n".encode())
    identity = dict(backup_id=str(uuid4()), cut_id=str(uuid4()), profile_id="fixture", host_id="single")
    return media, {"vault/Figures/Łódź.md": staged}, identity


def test_receipt_and_verified_members(fixture):
    media, members, identity = fixture
    receipt = seal_archive(media, members, **identity)
    assert receipt == verify_archive(media, identity["backup_id"])
    path = media / (identity["backup_id"] + ".zip")
    with zipfile.ZipFile(path) as container:
        raw = container.read("manifest.json")
        name, source = next(iter(members.items()))
        assert json.loads(raw)["members"] == [dict(name=name, size=source.stat().st_size,
            mtime_ns=source.stat().st_mtime_ns, sha256=hashlib.sha256(source.read_bytes()).hexdigest())]
        assert container.read("data/" + name) == source.read_bytes()
        assert str(source.parent).encode() not in raw
    assert receipt["archive_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert receipt["manifest_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["archive_bytes"] == path.stat().st_size
    assert receipt["member_count"] == 1
    with pytest.raises(FileExistsError):
        seal_archive(media, members, **identity)


@pytest.mark.parametrize(("has_db", "digest"), [(False, "a" * 64), (True, None), (True, "A" * 64),
                                              (True, "private/path"), (True, 17)])
def test_only_canonical_memory_namespace_evidence_is_accepted(fixture, has_db, digest):
    media, members, identity = fixture
    payload = next(iter(members.values()))
    capture = dict(directories=["conversations", "vault"], shared_session_root=True,
                   manifest_sha256="1" * 64, package_python_sha256="2" * 64, memory_namespace_sha256=digest)
    with pytest.raises(ArchiveError, match="namespace"):
        seal_archive(media, {"memory_db/memory.db": payload} if has_db else {}, capture=capture, **identity)


@pytest.mark.parametrize("name", ["file", "vault/", "vault/../x", "/root/a", "c:/file", "vault/C:foo",
    "vault/x:stream", "vault/a\\b", "vault/CON.txt", "vault/lpt¹", "vault/com1 .ext", "vault/x. ",
    "vault/a\x00b", "vault/a//b", "vault/./b", "vault/De\u0301", "vault/\u202etest"])
def test_reject_unsafe_names(name):
    with pytest.raises(ArchiveError):
        validate_member_name(name)


@pytest.mark.parametrize("other", ["vault/figures/x", "vault/Figures", "vault/Figures/łódź.md"])
def test_reject_portable_collisions(fixture, other):
    media, members, identity = fixture
    members[other] = next(iter(members.values()))
    with pytest.raises(ArchiveError):
        seal_archive(media, members, **identity)
    assert not list(media.iterdir())


def test_byte_limit_before_publication_and_during_verify(fixture):
    media, members, identity = fixture
    limits = ArchiveLimits(max_member_bytes=1)
    with pytest.raises(ArchiveError):
        seal_archive(media, members, **identity, limits=limits)
    assert not list(media.iterdir())
    seal_archive(media, members, **identity)
    with pytest.raises(ArchiveError):
        verify_archive(media, identity["backup_id"], limits=limits)


def test_corrupt_payload_and_receipt(fixture):
    media, members, identity = fixture
    receipt = seal_archive(media, members, **identity)
    path = media / (identity["backup_id"] + ".zip")
    original = path.read_bytes()
    source = next(iter(members.values())).read_bytes()
    path.write_bytes(original.replace(source, b"?" * len(source), 1))
    with pytest.raises(ArchiveError):
        verify_archive(media, identity["backup_id"])
    path.write_bytes(original)
    receipt["member_count"] = True
    (media / (identity["backup_id"] + ".receipt.json")).write_bytes(archive._json(receipt))
    with pytest.raises(ArchiveError):
        verify_archive(media, identity["backup_id"])


@pytest.mark.parametrize("fault", ["duplicate", "link", "traversal"])
def test_malformed_container_even_when_receipt_hash_matches(fixture, fault):
    media, members, identity = fixture
    receipt = seal_archive(media, members, **identity)
    path = media / (identity["backup_id"] + ".zip")
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as old, zipfile.ZipFile(path, "w") as new:
        item, metadata = old.infolist()
        payload = old.read(item)
        raw = old.read(metadata)
        if fault == "link":
            item.external_attr = (stat.S_IFLNK | 0o600) << 16
        elif fault == "traversal":
            item.filename = "data/vault/../escape"
            manifest = json.loads(raw)
            manifest["members"][0]["name"] = "vault/../escape"
            raw = archive._json(manifest)
        new.writestr(item, payload)
        if fault == "duplicate":
            with pytest.warns(UserWarning):
                new.writestr(item, payload)
        new.writestr(metadata, raw)
    receipt.update(archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   archive_bytes=path.stat().st_size, manifest_sha256=hashlib.sha256(raw).hexdigest())
    (media / (identity["backup_id"] + ".receipt.json")).write_bytes(archive._json(receipt))
    with pytest.raises(ArchiveError):
        verify_archive(media, identity["backup_id"])


@pytest.mark.parametrize("failure_at", ["archive", "receipt"])
def test_interrupted_publication(fixture, monkeypatch, failure_at):
    media, members, identity = fixture
    prior = seal_archive(media, members, **dict(identity, backup_id=str(uuid4()), cut_id=str(uuid4())))
    publish = archive._publish

    def interrupted(stage, target):
        if (target.suffix == ".zip") == (failure_at == "archive"):
            raise OSError("fixture interruption")
        publish(stage, target)

    monkeypatch.setattr(archive, "_publish", interrupted)
    with pytest.raises(OSError):
        seal_archive(media, members, **identity)
    assert not list(media.glob("*.partial"))
    assert verify_archive(media, prior["backup_id"]) == prior
    assert not (media / (identity["backup_id"] + ".receipt.json")).exists()
    assert (media / (identity["backup_id"] + ".zip")).exists() == (failure_at == "receipt")
    with pytest.raises(FileNotFoundError):
        verify_archive(media, identity["backup_id"])
    if failure_at == "receipt":
        with pytest.raises(FileExistsError):
            seal_archive(media, members, **identity)


@pytest.mark.parametrize("bad", ["vault/../escape", "vault/figures", "vault/Figures/Łódź.md",
                                 "vault/absent/child", "vault/Figures", "sessions_named"])
def test_reject_invalid_capture_directory(fixture, bad):
    media, members, identity = fixture
    capture = dict(directories=sorted(["conversations", "vault", "vault/Figures", bad]),
                   shared_session_root=True, manifest_sha256="1" * 64, package_python_sha256="2" * 64)
    with pytest.raises(ArchiveError):
        seal_archive(media, members, capture=capture, **identity)
    assert not list(media.iterdir())


def test_staged_hardlink_rejected(fixture):
    media, members, identity = fixture
    source = next(iter(members.values()))
    os.link(source, source.with_suffix(".alias"))
    with pytest.raises(ArchiveError):
        seal_archive(media, members, **identity)


def test_zip64_central_footer_and_checked_streaming(fixture, monkeypatch):
    media, members, identity = fixture
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 1)
    seal_archive(media, members, **identity)
    assert verify_archive(media, identity["backup_id"])["member_count"] == 1
    with zipfile.ZipFile(media / (identity["backup_id"] + ".zip")) as container:
        row, = json.loads(container.read("manifest.json"))["members"]
        result = io.BytesIO()
        archive.copy_verified_member(container, row, result)
        assert result.getvalue() == next(iter(members.values())).read_bytes()


def test_empty_generation_and_forged_central_count(fixture):
    media, _, identity = fixture
    seal_archive(media, {}, **identity)
    assert verify_archive(media, identity["backup_id"])["member_count"] == 0
    path = media / (identity["backup_id"] + ".zip")
    data = bytearray(path.read_bytes())
    data[-14:-10] = b"\xff\xff\xff\xff"
    path.write_bytes(data)
    with pytest.raises(ArchiveError):
        verify_archive(media, identity["backup_id"])
