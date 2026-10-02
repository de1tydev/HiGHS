"""Bounded, complete pair-worst evidence, without numerical/source imports.

The caller alone selects the first strict worst hour. This module never ranks,
rounds, truncates, or recomputes a witness. A bounded SQLite B-tree changes only
pair order, from the separator's outage-major traversal to canonical (i, k).
An unsuccessful operation retains its spill and any partial artifacts and can
never return a successful receipt. Each sink owns an exclusively created
directory; existing directories and artifacts are never replaced or removed.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat

from pair_codec import PackedPairs, Universe, read_pairs, write_pairs


WITNESS_SCHEMA = "complete-pair-worst-jsonl-v1"
MAX_WITNESS_BYTES = 2 * 1024**3
MAX_INTERMEDIATE_BYTES = 4 * 1024**3
MAX_PAIR_BYTES = 32 * 1024**2
MAX_RECORD_BYTES = 64 * 1024
SQLITE_CACHE_KIB = 4096
SQLITE_PAGE_BYTES = 4096
FAILURE_RESERVE_BYTES = 4096
_NUMERIC_FIELDS = ("worst_excess_MW", "flow_MW", "rating_MW",
                   "shared_overflow_MW", "unrelaxed_overload_MW")
_FIELDS = frozenset(("pair", "monitored_line_id", "outage_id", "outage_line_id",
                     "hour", *_NUMERIC_FIELDS))
_MANIFEST_FIELDS = frozenset(("schema", "path", "count", "bytes", "sha256",
                              "scope_sha256"))


class WitnessStoreError(ValueError):
    """Malformed/incomplete evidence or a frozen resource containment failure."""


def _limit(value, ceiling, name):
    if type(value) is not int or not 0 < value <= ceiling:
        raise WitnessStoreError(f"Invalid {name}; limits may only reduce frozen caps")
    return value


def _digest(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(character in "0123456789abcdef" for character in value))


class _Scope:
    """Only O(lines + listed outages) metadata, never the pair universe."""

    def __init__(self, scope):
        try:
            self.digest = Universe(scope).scope_sha256
            self.lines = tuple(scope["lines"])
            self.hours = scope["hours"]
            self.count = scope["eligible_pair_count"]
            self.rated = frozenset(scope["rated_line_indices"])
            counts = scope.get("finite_emergency_hour_counts")
            self.emergency_counts = None if counts is None else tuple(counts)
            indices = scope["outage_indices"]
            names = scope["checked_outage_ids"]
            outage_lines = scope["outage_line_ids"]
            if (not self.lines or any(type(name) is not str or not name for name in self.lines)
                    or len(set(self.lines)) != len(self.lines)
                    or type(self.hours) is not int or self.hours < 1
                    or type(self.count) is not int or self.count < 0
                    or len(indices) != len(names) or len(indices) != len(outage_lines)
                    or len(set(indices)) != len(indices) or len(set(names)) != len(names)
                    or not _digest(self.digest)):
                raise WitnessStoreError("Malformed witness source scope")
            self.outages = {}
            for index, name, line in zip(indices, names, outage_lines):
                if (type(index) is not int or not 0 <= index < len(self.lines)
                        or type(name) is not str or not name or line != self.lines[index]):
                    raise WitnessStoreError("Malformed outage source metadata")
                self.outages[index] = (name, line)
            if (any(type(index) is not int or not 0 <= index < len(self.lines)
                    for index in self.rated)
                    or len(self.rated) != len(scope["rated_line_indices"])
                    or self.count != len(self.rated) * len(self.outages)
                    - len(self.rated.intersection(self.outages))
                    or len(self.lines)**2 > 2**32):
                raise WitnessStoreError("Invalid pair universe or uint32 width")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, WitnessStoreError):
                raise
            raise WitnessStoreError("Malformed witness source scope") from exc

    def record(self, value):
        if type(value) is not dict or set(value) != _FIELDS:
            raise WitnessStoreError("Witness does not match complete worst-hour schema")
        pair = value["pair"]
        if (type(pair) is not list or len(pair) != 2
                or any(type(index) is not int for index in pair)):
            raise WitnessStoreError("Witness pair must contain two integer indices")
        monitored, outage = pair
        if monitored not in self.rated or outage not in self.outages or monitored == outage:
            raise WitnessStoreError("Witness pair is outside source scope")
        if self.emergency_counts is not None and not self.emergency_counts[monitored]:
            raise WitnessStoreError("Witness monitored line has no finite emergency hours")
        outage_id, outage_line = self.outages[outage]
        if (value["monitored_line_id"] != self.lines[monitored]
                or value["outage_id"] != outage_id or value["outage_line_id"] != outage_line
                or type(value["hour"]) is not int or not 0 <= value["hour"] < self.hours):
            raise WitnessStoreError("Witness line/outage/hour metadata mismatch")
        for field in _NUMERIC_FIELDS:
            number = value[field]
            try:
                valid = type(number) in (int, float) and math.isfinite(number)
            except OverflowError:
                valid = False
            if not valid:
                raise WitnessStoreError(f"Nonfinite/non-numeric witness field: {field}")
        return monitored * len(self.lines) + outage


def _encode(value, limit):
    # iterencode caps even unusually long source identifiers before joining.
    if any(isinstance(item, str) and len(item) > limit for item in value.values()):
        raise WitnessStoreError("Witness string exceeds frozen record byte cap")
    pieces, size = [], 1
    try:
        for piece in json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                                      allow_nan=False, ensure_ascii=True).iterencode(value):
            encoded = piece.encode("ascii")
            size += len(encoded)
            if size > limit:
                raise WitnessStoreError("Witness record exceeds frozen byte cap")
            pieces.append(encoded)
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, WitnessStoreError):
            raise
        raise WitnessStoreError("Witness is not finite JSON") from exc
    return b"".join(pieces) + b"\n"


def _unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise WitnessStoreError("Duplicate key in witness JSON")
        result[key] = value
    return result


def _reject_constant(value):
    raise WitnessStoreError("Nonfinite witness JSON: " + value)


def _decode(line):
    try:
        return json.loads(line, parse_constant=_reject_constant, object_pairs_hook=_unique)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, WitnessStoreError):
            raise
        raise WitnessStoreError("Malformed witness JSON record") from exc


def _open_regular(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise WitnessStoreError("Witness sidecar is not a regular file")
            return os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise
    except OSError as exc:
        raise WitnessStoreError("Missing or unreadable witness sidecar") from exc


class WitnessSink:
    """Exclusive spill writer. Any failure permanently poisons this sink.

    SQLite has a fixed 4 MiB cache, disabled mmap, and a hard maximum page
    count. Its INTEGER PRIMARY KEY provides ordered streaming without SQL
    sorting or an in-memory witness/pair collection. The scratch database uses
    no journal; crashes or write errors cannot produce a successful receipt.
    The complete immutable sidecars are independently verified before return.
    """

    def __init__(self, directory, scope, *, max_witness_bytes=MAX_WITNESS_BYTES,
                 max_intermediate_bytes=MAX_INTERMEDIATE_BYTES,
                 max_pair_bytes=MAX_PAIR_BYTES, max_record_bytes=MAX_RECORD_BYTES):
        self.max_witness_bytes = _limit(max_witness_bytes, MAX_WITNESS_BYTES, "witness byte cap")
        self.max_intermediate_bytes = _limit(max_intermediate_bytes, MAX_INTERMEDIATE_BYTES,
                                             "intermediate byte cap")
        self.max_pair_bytes = _limit(max_pair_bytes, MAX_PAIR_BYTES, "pair byte cap")
        self.max_record_bytes = _limit(max_record_bytes, MAX_RECORD_BYTES, "record byte cap")
        self.scope = scope
        self._scope = _Scope(scope)
        self.directory = Path(directory).absolute()
        self._connection = None
        self._state = "new"
        self.count = self.bytes = 0
        try:
            self.directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        except OSError as exc:
            raise WitnessStoreError("Witness directory must be exclusively fresh") from exc
        self._state = "open"
        try:
            pages = (self.max_intermediate_bytes - FAILURE_RESERVE_BYTES) // SQLITE_PAGE_BYTES
            if pages < 2:
                raise WitnessStoreError("Intermediate cap cannot hold the bounded spill")
            self._connection = sqlite3.connect(self.directory / "spill.sqlite3", isolation_level=None)
            self._connection.execute(f"PRAGMA page_size={SQLITE_PAGE_BYTES}")
            self._connection.execute("PRAGMA journal_mode=OFF")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA mmap_size=0")
            self._connection.execute(f"PRAGMA cache_size=-{SQLITE_CACHE_KIB}")
            self._connection.execute("PRAGMA temp_store=FILE")
            self._connection.execute(f"PRAGMA max_page_count={pages}")
            self._connection.execute("CREATE TABLE witnesses (q INTEGER PRIMARY KEY, payload BLOB NOT NULL)")
            self._check_storage()
        except Exception as exc:
            self._fail(exc)
            raise WitnessStoreError(f"Witness spill initialization failed: {exc}") from exc

    def _require_open(self):
        if self._state != "open":
            raise WitnessStoreError("Witness sink is failed, closed, or already finalized")

    def _disk_bytes(self):
        return sum(entry.stat().st_size for entry in self.directory.iterdir() if entry.is_file())

    def _check_storage(self, additional=0):
        if self._disk_bytes() + additional > self.max_intermediate_bytes - FAILURE_RESERVE_BYTES:
            raise WitnessStoreError("Witness spill/artifacts exceed intermediate byte cap")

    def _fail(self, error):
        self._state = "failed"
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                pass
            self._connection = None
        # Never remove spill, partial output, or historical artifacts on error.
        evidence = _encode({"status": "resource_or_evidence_incomplete", "count": self.count,
                            "bytes": self.bytes, "error": str(error)[:512]}, FAILURE_RESERVE_BYTES)
        try:
            if self._disk_bytes() + len(evidence) <= self.max_intermediate_bytes:
                with (self.directory / "FAILED.json").open("xb") as stream:
                    stream.write(evidence)
                    stream.flush()
                    os.fsync(stream.fileno())
        except OSError:
            pass

    def add(self, worst):
        self._require_open()
        try:
            q = self._scope.record(worst)
            encoded = _encode(worst, self.max_record_bytes)
            if self.bytes + len(encoded) > self.max_witness_bytes:
                raise WitnessStoreError("Complete witness artifact exceeds frozen byte cap")
            if self.count >= self._scope.count:
                raise WitnessStoreError("Witness count exceeds eligible pair count")
            # The frozen pair sidecar contains exactly four bytes per pair.
            if (self.count + 1) * 4 > self.max_pair_bytes:
                raise WitnessStoreError("Complete pair artifact exceeds frozen byte cap")
            self._connection.execute("INSERT INTO witnesses (q, payload) VALUES (?, ?)", (q, encoded))
            self.count += 1
            self.bytes += len(encoded)
            self._check_storage()
        except Exception as exc:
            self._fail(exc)
            raise WitnessStoreError(f"Witness add failed: {exc}") from exc

    def _pairs(self):
        for (q,) in self._connection.execute("SELECT q FROM witnesses ORDER BY q"):
            yield divmod(q, len(self._scope.lines))

    def finalize(self):
        self._require_open()
        try:
            # Check the combined retained spill/output footprint before opening
            # either artifact. The frozen raw uint32 pair sidecar has no header.
            self._check_storage(self.bytes + self.count * 4)
            path = self.directory / "witnesses.jsonl"
            digest = hashlib.sha256()
            count = size = 0
            previous = -1
            with path.open("xb") as stream:
                for q, payload in self._connection.execute("SELECT q, payload FROM witnesses ORDER BY q"):
                    if q <= previous or len(payload) > self.max_record_bytes:
                        raise WitnessStoreError("Corrupt witness spill order or record length")
                    record = _decode(payload)
                    if self._scope.record(record) != q or not payload.endswith(b"\n"):
                        raise WitnessStoreError("Corrupt witness spill metadata")
                    if size + len(payload) > self.max_witness_bytes:
                        raise WitnessStoreError("Complete witness artifact exceeds frozen byte cap")
                    stream.write(payload)
                    digest.update(payload)
                    size += len(payload)
                    count += 1
                    previous = q
                stream.flush()
                os.fsync(stream.fileno())
            if (count, size) != (self.count, self.bytes):
                raise WitnessStoreError("Witness spill count/byte mismatch")
            packed = PackedPairs(self.scope, self._pairs())
            if packed.nbytes > self.max_pair_bytes:
                raise WitnessStoreError("Complete pair artifact exceeds frozen byte cap")
            pair_manifest = write_pairs(self.directory / "violated_pairs.bin", packed)
            del packed
            result = {"witnesses": {"schema": WITNESS_SCHEMA, "path": str(path), "count": count,
                                    "bytes": size, "sha256": digest.hexdigest(),
                                    "scope_sha256": self._scope.digest},
                      "violated_pairs": pair_manifest}
            validate_witnesses(result, self.scope)
            self._check_storage()
            self._connection.close()
            self._connection = None
            for entry in self.directory.iterdir():
                if entry.is_file():
                    entry.chmod(0o444)
            self._state = "finalized"
            return result
        except Exception as exc:
            self._fail(exc)
            raise WitnessStoreError(f"Witness finalization failed: {exc}") from exc

    def close(self):
        if self._state == "open":
            self._fail(WitnessStoreError("Witness sink closed before successful finalization"))

    def __enter__(self):
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if self._state == "open":
            self._fail(exc or WitnessStoreError("Witness sink left without successful finalization"))
        return False


def _manifests(manifest, pair_manifest):
    if type(manifest) is dict and "witnesses" in manifest:
        if pair_manifest is not None or set(manifest) != {"witnesses", "violated_pairs"}:
            raise WitnessStoreError("Ambiguous complete witness manifest")
        manifest, pair_manifest = manifest["witnesses"], manifest["violated_pairs"]
    if type(manifest) is not dict or set(manifest) != _MANIFEST_FIELDS or pair_manifest is None:
        raise WitnessStoreError("Complete witness and pair manifests are both required")
    return manifest, pair_manifest


def _manifest_check(manifest, scope):
    if (manifest["schema"] != WITNESS_SCHEMA or manifest["scope_sha256"] != scope.digest
            or type(manifest["count"]) is not int or not 0 <= manifest["count"] <= scope.count
            or type(manifest["bytes"]) is not int or not 0 <= manifest["bytes"] <= MAX_WITNESS_BYTES
            or type(manifest["path"]) is not str or not manifest["path"]
            or not _digest(manifest["sha256"])):
        raise WitnessStoreError("Invalid witness manifest schema/count/bytes/hash/scope")


def _scan(stream, scope, manifest, pairs):
    digest, previous, count, size = hashlib.sha256(), -1, 0, 0
    pair_iterator = iter(pairs)
    sentinel = object()
    while True:
        line = stream.readline(MAX_RECORD_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_RECORD_BYTES or not line.endswith(b"\n"):
            raise WitnessStoreError("Oversized or truncated witness record")
        size += len(line)
        count += 1
        if size > manifest["bytes"] or count > manifest["count"]:
            raise WitnessStoreError("Witness artifact exceeds declared count/bytes")
        record = _decode(line)
        q = scope.record(record)
        if q <= previous:
            raise WitnessStoreError("Witness pairs must be unique and in canonical order")
        pair = next(pair_iterator, sentinel)
        if pair is sentinel or tuple(record["pair"]) != tuple(pair):
            raise WitnessStoreError("Witness/pair sidecars disagree")
        previous = q
        digest.update(line)
    if next(pair_iterator, sentinel) is not sentinel:
        raise WitnessStoreError("Pair sidecar has witnesses missing")
    if (count != manifest["count"] or size != manifest["bytes"]
            or digest.hexdigest() != manifest["sha256"]):
        raise WitnessStoreError("Witness sidecar count/bytes/hash mismatch")
    return count


def iter_witnesses(manifest, scope, *, pair_manifest=None):
    """Validate complete evidence before yielding any record, then stream it.

    Accept the combined finalize() result or the witness manifest accompanied
    by pair_manifest. The first pass is bounded and checks every pair, record,
    byte, and hash. No valid prefix of an invalid artifact is exposed as valid.
    """
    manifest, pair_manifest = _manifests(manifest, pair_manifest)
    source = _Scope(scope)
    _manifest_check(manifest, source)
    try:
        pairs = read_pairs(pair_manifest, scope)
        with _open_regular(manifest["path"]) as stream:
            before = os.fstat(stream.fileno())
            if before.st_size != manifest["bytes"]:
                raise WitnessStoreError("Witness sidecar byte length mismatch")
            _scan(stream, source, manifest, pairs)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise WitnessStoreError("Witness sidecar changed during validation")
            stream.seek(0)
            for _ in range(manifest["count"]):
                line = stream.readline(MAX_RECORD_BYTES + 1)
                if len(line) > MAX_RECORD_BYTES or not line.endswith(b"\n"):
                    raise WitnessStoreError("Witness sidecar changed after validation")
                record = _decode(line)
                source.record(record)
                yield record
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise WitnessStoreError("Witness sidecar changed after validation")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, WitnessStoreError):
            raise
        raise WitnessStoreError(f"Invalid complete witness evidence: {exc}") from exc


def validate_witnesses(manifest, scope, *, pair_manifest=None):
    """Fully validate without materializing the witnesses; return exact count."""
    count = 0
    for _ in iter_witnesses(manifest, scope, pair_manifest=pair_manifest):
        count += 1
    return count
