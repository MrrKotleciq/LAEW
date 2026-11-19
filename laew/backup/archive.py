"""V1 immutable single-host archives of already-staged files.

Callers own the maintenance fence, source validation, and provisioning of a
trusted local destination and staging tree. A receipt is the commit record.
An archive without one is an orphan; retry with a fresh generation ID.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
import unicodedata
from uuid import UUID
import zipfile


class ArchiveError(ValueError):
    """Malformed, unsafe or unverifiable backup generation."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_members: int = 20_000
    max_member_bytes: int = 2 << 30
    max_total_bytes: int = 8 << 30
    max_archive_bytes: int = 9 << 30
    max_manifest_bytes: int = 8 << 20

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in vars(self).values()):
            raise ValueError("Archive limits must be positive integers.")


_CHUNK = 1 << 20
_ID = re.compile(r"[a-z][a-z0-9_-]{0,70}")
_HASH = re.compile(r"[a-f0-9]{64}")
_DEVICES = re.compile(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³]", re.I)
_IDENTITY = {"schema_version", "backup_id", "cut_id", "profile_id", "host_id"}
_RECEIPT = _IDENTITY | {"archive_sha256", "manifest_sha256", "verified_at", "archive_bytes", "member_count"}


def _check(condition, message):
    if not condition:
        raise ArchiveError(message)


def _uuid(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        valid = False
    _check(valid, "Invalid generation identifier.")
    return value


def _identifier(value):
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def validate_member_name(name):
    """Validate an NFC portable logical-root/relative-file name and return it."""
    _check(isinstance(name, str) and unicodedata.normalize("NFC", name) == name,
           "Invalid logical member name.")
    parts = name.split("/")
    _check(2 <= len(parts) <= 64 and _identifier(parts[0]) and len(name.encode("utf-8")) <= 1024,
           "Invalid logical root or member length.")
    for part in parts:
        _check(part and not part.endswith((" ", ".")) and len(part.encode("utf-8")) <= 255
               and not _DEVICES.fullmatch(part.partition(".")[0].rstrip(" "))
               and all(ch not in '<>:"\\|?*' and unicodedata.category(ch) not in {"Cc", "Cf", "Cs"}
                       for ch in part), "Unsafe portable file name.")
    return name


def _validate_names(names, directories=()):
    seen = {}
    for name, is_dir in [(name, True) for name in directories] + [(name, False) for name in names]:
        if is_dir and isinstance(name, str) and "/" not in name:
            validate_member_name(name + "/entry")
        else:
            validate_member_name(name)
        parts = name.split("/")
        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            key = prefix.casefold()
            directory = index < len(parts) or is_dir
            if key in seen:
                _check(directory and seen[key] == (prefix, True), "Member paths collide.")
            else:
                seen[key] = (prefix, directory)


def _validate_capture(metadata, names, limits):
    _check(type(metadata) is dict and set(metadata) == {
        "directories", "shared_session_root", "manifest_sha256", "package_python_sha256"
    }, "Invalid capture metadata.")
    dirs = metadata["directories"]
    _check(type(dirs) is list and len(dirs) + len(names) <= limits.max_members
           and all(type(name) is str for name in dirs) and dirs == sorted(set(dirs))
           and type(metadata["shared_session_root"]) is bool
           and _digest(metadata["manifest_sha256"]) and _digest(metadata["package_python_sha256"]),
           "Invalid capture inventory or provenance.")
    directory_set = set(dirs)
    _check({"vault", "conversations"} <= directory_set and
           (("sessions_named" in directory_set) != metadata["shared_session_root"]),
           "Invalid session root mapping.")
    for name in dirs:
        _check(name.split("/")[0] in {"sessions_named", "conversations", "vault"} and
               ("/" not in name or name.rpartition("/")[0] in directory_set), "Unknown capture directory.")
    for name in names:
        if name.split("/")[0] in {"sessions_named", "conversations", "vault"}:
            _check(name.rpartition("/")[0] in directory_set, "Missing capture directory.")
    _validate_names(names, dirs)


def _identity(backup_id, cut_id, profile_id, host_id):
    _check(_identifier(profile_id) and len(profile_id) <= 64 and _identifier(host_id) and len(host_id) <= 64,
           "Invalid profile or host identifier.")
    return dict(schema_version=1, backup_id=_uuid(backup_id), cut_id=_uuid(cut_id),
                profile_id=profile_id, host_id=host_id)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _parse(raw):
    try:
        value = json.loads(raw)
        _check(isinstance(value, dict) and _json(value) == raw, "Non-canonical archive JSON.")
        return value
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ArchiveError("Invalid archive JSON.") from exc


def _file(path, directory=False):
    path = Path(path)
    _check(path.is_absolute() and ".." not in path.parts, "An absolute normalized path is required.")
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        _check(not stat.S_ISLNK(info.st_mode) and
               not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
               "Linked archive path.")
    if directory:
        _check(stat.S_ISDIR(info.st_mode), "Missing archive directory.")
    else:
        _check(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Unsafe input file.")
    return info


def _stream(source, maximum, output=None):
    digest = hashlib.sha256()
    count = 0
    while data := source.read(min(_CHUNK, maximum - count + 1)):
        count += len(data)
        _check(count <= maximum, "Archive byte limit exceeded.")
        digest.update(data)
        if output is not None:
            output.write(data)
    return count, digest.hexdigest()


def _number(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def _digest(value):
    return isinstance(value, str) and bool(_HASH.fullmatch(value))


def _preflight(stream, size, limits):
    """Bound the central directory before ZipFile allocates its member list."""
    _check(22 <= size <= limits.max_archive_bytes, "Invalid archive length.")
    stream.seek(size - 22)
    sig, disk, central_disk, local_count, count, length, offset, comment = struct.unpack(
        "<4s4H2IH", stream.read(22))
    end = size - 22
    _check(sig == b"PK\x05\x06" and disk == central_disk == comment == 0 and local_count == count,
           "Invalid ZIP footer.")
    if end >= 76:
        stream.seek(end - 20)
        locator = stream.read(20)
        if locator.startswith(b"PK\x06\x07"):
            _, disk, position, disks = struct.unpack("<4sIQI", locator)
            _check(disk == 0 and disks == 1 and position == end - 76, "Invalid ZIP64 locator.")
            stream.seek(position)
            sig, record_size, _, _, disk, central_disk, local64, count64, length64, offset64 = (
                struct.unpack("<4sQ2H2I4Q", stream.read(56)))
            _check(sig == b"PK\x06\x06" and record_size == 44 and disk == central_disk == 0
                   and local64 == count64 and count in (count64, 65535)
                   and length in (length64, 0xffffffff) and offset in (offset64, 0xffffffff),
                   "Invalid ZIP64 footer.")
            count, length, offset, end = count64, length64, offset64, position
    _check(1 <= count <= limits.max_members + 1 and length <= count * 1200 and offset + length == end,
           "Invalid central directory limits.")
    stream.seek(offset)
    for _ in range(count):
        header = stream.read(46)
        _check(len(header) == 46 and header[:4] == b"PK\x01\x02", "Invalid central member.")
        name, extra, comment = struct.unpack_from("<3H", header, 28)
        _check(0 < name <= 1030 and extra <= 64 and comment == 0, "Invalid central member fields.")
        stream.seek(name + extra, os.SEEK_CUR)
    _check(stream.tell() == end, "Incorrect central directory count.")
    return offset


def _zip_info(name):
    item = zipfile.ZipInfo(name)
    item.create_system = 3
    item.external_attr = (stat.S_IFREG | 0o600) << 16
    return item


def _check_zip_item(item):
    _check(item.orig_filename == item.filename and item.create_system == 3 and
           item.external_attr == (stat.S_IFREG | 0o600) << 16 and
           item.compress_type == zipfile.ZIP_STORED and item.compress_size == item.file_size and
           item.flag_bits in (0, 0x800) and not item.comment, "Unsupported ZIP member.")
    if item.extra:
        _check(len(item.extra) in (12, 20, 28) and
               item.extra[:4] == struct.pack("<HH", 1, len(item.extra) - 4), "Unexpected central ZIP metadata.")


def _check_local_headers(stream, items, central_offset):
    """Accept only contiguous regular-file records and known ZIP64 metadata."""
    offset = 0
    for item in items:
        _check(item.header_offset == offset, "Unexpected bytes between archive members.")
        stream.seek(offset)
        header = stream.read(30)
        _check(len(header) == 30, "Incomplete local header.")
        sig, _, flags, method, _, _, crc, compressed, size, name_size, extra = struct.unpack(
            "<4s5H3I2H", header)
        encoded = item.filename.encode("utf-8")
        _check(sig == b"PK\x03\x04" and flags == item.flag_bits and method == zipfile.ZIP_STORED and
               crc == item.CRC and name_size == len(encoded) and stream.read(name_size) == encoded,
               "Inconsistent local ZIP entry.")
        if extra:
            _check(size == compressed == 0xffffffff and extra == 20 and stream.read(extra) ==
                   struct.pack("<HHQQ", 1, 16, item.file_size, item.compress_size), "Unexpected local ZIP metadata.")
        else:
            _check(size == item.file_size and compressed == item.compress_size, "Invalid local ZIP size.")
        offset = stream.tell() + item.file_size
    _check(offset == central_offset, "Unexpected bytes before central directory.")


def copy_verified_member(container, row, output):
    """Copy one previously validated manifest row, checking size, digest and ZIP CRC.

    Restore callers supply an already-open private staging file. On failure
    they discard the staged output. Passing None performs a verification pass.
    """
    name = "data/" + validate_member_name(row["name"])
    with container.open(name) as source:
        _check(_stream(source, row["size"], output) == (row["size"], row["sha256"]),
               "Archive member digest mismatch.")


def _verify_container(path, identity, limits, *, expected=None, on_verified=None):
    before = _file(path)
    with open(path, "rb") as stream:
        _check(os.path.samestat(before, os.fstat(stream.fileno())), "Archive was replaced.")
        central_offset = _preflight(stream, before.st_size, limits)
        stream.seek(0)
        size, archive_hash = _stream(stream, limits.max_archive_bytes)
        try:
            with zipfile.ZipFile(stream) as archive:
                items = archive.infolist()
                for item in items:
                    _check_zip_item(item)
                _check_local_headers(stream, items, central_offset)
                header = items[-1]
                _check(header.filename == "manifest.json" and header.file_size <= limits.max_manifest_bytes,
                       "Invalid or oversized manifest.")
                raw = archive.read(header)
                manifest = _parse(raw)
                _check(set(manifest) in (_IDENTITY | {"members"}, _IDENTITY | {"members", "capture"})
                       and type(manifest["schema_version"]) is int
                       and all(manifest[key] == value for key, value in identity.items()),
                       "Archive identity mismatch.")
                rows = manifest["members"]
                _check(isinstance(rows, list) and len(rows) == len(items) - 1, "Invalid manifest count.")
                names = []
                total = 0
                for row, item in zip(rows, items):
                    _check(isinstance(row, dict) and set(row) == {"name", "size", "mtime_ns", "sha256"}
                           and isinstance(row["name"], str) and item.filename == "data/" + row["name"]
                           and _number(row["size"], limits.max_member_bytes) and row["size"] == item.file_size
                           and _number(row["mtime_ns"], 2**63 - 1) and _digest(row["sha256"]),
                           "Invalid manifest member.")
                    names.append(row["name"])
                    total += item.file_size
                _check(total <= limits.max_total_bytes and names == sorted(names), "Invalid manifest order or size.")
                if "capture" in manifest:
                    _validate_capture(manifest["capture"], names, limits)
                else:
                    _validate_names(names)
                for row in rows:
                    copy_verified_member(archive, row, None)
                metrics = dict(archive_bytes=size, archive_sha256=archive_hash,
                               manifest_sha256=hashlib.sha256(raw).hexdigest(), member_count=len(rows))
                if expected is not None:
                    _check(all(expected[key] == value for key, value in metrics.items()), "Receipt verification failed.")
                if on_verified is not None:
                    on_verified(archive, manifest)
        except (zipfile.BadZipFile, EOFError, UnicodeError, NotImplementedError) as exc:
            raise ArchiveError("Corrupt archive container.") from exc
        after = os.fstat(stream.fileno())
        _check(after.st_size == before.st_size and after.st_mtime_ns == before.st_mtime_ns and
               os.path.samestat(after, path.lstat()), "Archive changed during verification.")
    return metrics


def _sync_dir(directory):
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def _stage(directory):
    fd, filename = tempfile.mkstemp(prefix=".m18-", suffix=".partial", dir=directory)
    path = Path(filename)
    try:
        with os.fdopen(fd, "w+b") as stream:
            yield path, stream
    finally:
        path.unlink(missing_ok=True)


def _publish(stage, target):
    # Both paths share the destination filesystem. Neither primitive overwrites.
    if os.name == "nt":
        os.rename(stage, target)
    else:
        os.link(stage, target)
        stage.unlink()
    _sync_dir(target.parent)


def seal_archive(destination, members, *, backup_id, cut_id, profile_id, host_id, limits=ArchiveLimits(),
                 before_publish=None, capture=None):
    """Seal staged sources under an externally held exclusive installation fence."""
    directory = Path(destination)
    _file(directory, directory=True)
    identity = _identity(backup_id, cut_id, profile_id, host_id)
    target = directory / (backup_id + ".zip")
    receipt_path = directory / (backup_id + ".receipt.json")
    if os.path.lexists(target) or os.path.lexists(receipt_path):
        raise FileExistsError("Backup generation already exists.")
    _check(len(members) <= limits.max_members, "Too many archive members.")
    _validate_names(members)
    if capture is not None:
        _validate_capture(capture, members, limits)
    with _stage(directory) as (stage, stream):
        total = 0
        rows = []
        with zipfile.ZipFile(stream, "w", allowZip64=True) as archive:
            for name in sorted(members):
                source = Path(members[name])
                before = _file(source)
                budget = min(limits.max_member_bytes, limits.max_total_bytes - total,
                             limits.max_archive_bytes - stream.tell() - 1100)
                _check(before.st_size <= budget, "Staged source exceeds byte limits.")
                with source.open("rb") as reader, archive.open(_zip_info("data/" + name), "w",
                                                               force_zip64=True) as writer:
                    _check(os.path.samestat(before, os.fstat(reader.fileno())), "Staged file was replaced.")
                    size, digest = _stream(reader, before.st_size, writer)
                after = source.lstat()
                _check(size == before.st_size and before.st_mtime_ns == after.st_mtime_ns
                       and os.path.samestat(before, after), "Staged source changed.")
                total += size
                rows.append(dict(name=name, mtime_ns=before.st_mtime_ns, size=size, sha256=digest))
            manifest = dict(identity, members=rows)
            if capture is not None:
                manifest["capture"] = capture
            raw = _json(manifest)
            _check(len(raw) <= limits.max_manifest_bytes, "Manifest exceeds byte limit.")
            _check(stream.tell() + len(raw) + sum(100 + len(row["name"].encode()) for row in rows)
                   + 256 <= limits.max_archive_bytes, "Archive exceeds byte limit.")
            archive.writestr(_zip_info("manifest.json"), raw)
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        metrics = _verify_container(stage, identity, limits)
        if before_publish is not None:
            before_publish()
        _publish(stage, target)
    receipt = dict(identity, **metrics, verified_at=datetime.now(timezone.utc).isoformat())
    with _stage(directory) as (stage, stream):
        stream.write(_json(receipt))
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        _publish(stage, receipt_path)
    return receipt


def read_receipt(destination, backup_id, *, limits=ArchiveLimits()):
    """Read cached verification evidence and check that its paired ZIP exists.

    This metadata-only inspection does not establish current byte integrity.
    """
    directory = Path(destination)
    path = directory / (_uuid(backup_id) + ".receipt.json")
    info = _file(path)
    _check(info.st_size <= 4096, "Oversized receipt.")
    with path.open("rb") as stream:
        _check(os.path.samestat(info, os.fstat(stream.fileno())), "Receipt was replaced.")
        raw = stream.read(4097)
    _check(len(raw) == info.st_size, "Receipt changed during verification.")
    receipt = _parse(raw)
    _check(set(receipt) == _RECEIPT and type(receipt["schema_version"]) is int and receipt["schema_version"] == 1
           and receipt["backup_id"] == backup_id and _number(receipt["member_count"], limits.max_members)
           and _number(receipt["archive_bytes"], limits.max_archive_bytes) and _digest(receipt["archive_sha256"])
           and _digest(receipt["manifest_sha256"]), "Invalid backup receipt.")
    _identity(backup_id, receipt["cut_id"], receipt["profile_id"], receipt["host_id"])
    try:
        stamp = datetime.fromisoformat(receipt["verified_at"])
        _check(stamp.tzinfo == timezone.utc and stamp.isoformat() == receipt["verified_at"], "Invalid receipt time.")
    except (ValueError, TypeError) as exc:
        raise ArchiveError("Invalid receipt time.") from exc
    _check(_file(directory / (backup_id + ".zip")).st_size == receipt["archive_bytes"], "Archive size mismatch.")
    return receipt


def verify_archive(destination, backup_id, *, limits=ArchiveLimits(), on_verified=None):
    """Verify receipt, full container and all member bytes without extraction."""
    receipt = read_receipt(destination, backup_id, limits=limits)
    identity = {key: receipt[key] for key in _IDENTITY}
    _verify_container(Path(destination) / (backup_id + ".zip"), identity, limits, expected=receipt,
                      on_verified=on_verified)
    return receipt
