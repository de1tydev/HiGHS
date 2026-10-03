"""Exact, bounded pair interchange; standard library only.

The source universe is implicit. Only explicitly selected pairs are stored, as
strictly increasing uint32 ``i * line_count + k`` values. On disk these are raw
little-endian uint32 values, without a header. Every file requires its manifest.
The frozen 32 MiB limit is a payload/storage limit, not an RSS measurement.
"""

from array import array
from bisect import bisect_left
from collections.abc import Mapping, Set
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile


DESCRIPTOR_SCHEMA = "implicit-source-pairs-v1"
PAIRS_SCHEMA = "packed-pairs-u32le-v1"
MAX_PAIR_BYTES = 32 * 1024 * 1024
MAX_PAIRS = MAX_PAIR_BYTES // 4
UINT32_MAX = (1 << 32) - 1
_CHUNK_VALUES = 16384
_MANIFEST_KEYS = frozenset(("schema", "path", "count", "bytes", "sha256",
                            "scope_sha256", "line_count"))


class PairCodecError(ValueError):
    """Malformed scope, pair sequence, or pair sidecar."""


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PairCodecError("Scope is not canonical JSON data") from exc


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash(value, label):
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise PairCodecError(f"Invalid {label}")
    return value


def _integer(value, label, minimum=0, maximum=UINT32_MAX):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PairCodecError(f"Invalid {label}")
    return value


def _ids(value, label, nonempty=False):
    if not isinstance(value, (list, tuple)) or (nonempty and not value):
        raise PairCodecError(f"Invalid {label}")
    if any(not isinstance(item, str) or not item for item in value):
        raise PairCodecError(f"Invalid {label}")
    if len(value) != len(set(value)):
        raise PairCodecError(f"Duplicate {label}")
    return tuple(value)


def _indices(value, label, line_count, ordered=False):
    if not isinstance(value, (list, tuple)):
        raise PairCodecError(f"Invalid {label}")
    result = tuple(_integer(item, label, maximum=line_count - 1) for item in value)
    if len(result) != len(set(result)):
        raise PairCodecError(f"Duplicate {label}")
    if ordered and any(a >= b for a, b in zip(result, result[1:])):
        raise PairCodecError(f"Noncanonical {label}")
    return result


def _counts(value, universe):
    if not isinstance(value, (list, tuple)) or len(value) != universe.line_count:
        raise PairCodecError("Emergency-hour counts must have one entry per line")
    counts = tuple(_integer(item, "emergency-hour count", maximum=universe.hours)
                   for item in value)
    if any(count and index not in universe._rated_set for index, count in enumerate(counts)):
        raise PairCodecError("Unrated line has finite emergency hours")
    return counts


class Universe:
    """Validated exact scope with O(lines) storage and lazy canonical iteration.

    Outage indices retain source contingency order, which need not be numeric
    order. Iteration sorts only those O(lines) indices; it never builds a pair
    list. Invalid membership queries return False; constructors reject them.
    """

    __slots__ = ("lines", "line_count", "rated_line_indices", "outage_indices",
                 "hours", "scope_sha256", "_rated_set", "_outage_set", "_count")

    def __init__(self, scope):
        if not isinstance(scope, Mapping):
            raise PairCodecError("Scope must be a mapping")
        if "eligible_pairs" in scope:
            raise PairCodecError("Explicit source universe is forbidden")
        if "schema" in scope and scope["schema"] != DESCRIPTOR_SCHEMA:
            raise PairCodecError("Unknown source-pair descriptor schema")
        if "schema" in scope and not all(name in scope for name in
                ("eligible_pair_count", "eligible_pair_hours", "finite_emergency_hour_counts",
                 "descriptor_sha256")):
            raise PairCodecError("Incomplete source-pair descriptor")
        if "descriptor_sha256" in scope and "schema" not in scope:
            raise PairCodecError("Descriptor hash requires a descriptor schema")
        self.lines = _ids(scope.get("lines"), "line IDs", nonempty=True)
        self.line_count = len(self.lines)
        if self.line_count * self.line_count > UINT32_MAX:
            raise PairCodecError("Squared line count does not fit uint32")
        self.hours = _integer(scope.get("hours"), "hours", minimum=1)
        self.rated_line_indices = _indices(scope.get("rated_line_indices"),
                                          "rated indices", self.line_count, ordered=True)
        self.outage_indices = _indices(scope.get("outage_indices"),
                                      "outage indices", self.line_count)
        outage_ids = _ids(scope.get("checked_outage_ids"), "outage IDs")
        outage_lines = _ids(scope.get("outage_line_ids"), "outage line IDs")
        if not (len(outage_ids) == len(outage_lines) == len(self.outage_indices)):
            raise PairCodecError("Outage indices and IDs have different lengths")
        if any(self.lines[index] != line for index, line in zip(self.outage_indices, outage_lines)):
            raise PairCodecError("Outage line IDs disagree with source indices/order")
        for name in ("buses", "generators"):
            if name in scope:
                _ids(scope[name], name, nonempty=True)
        _hash(scope.get("source_data_sha256"), "parsed-source SHA256")
        for name in ("source_sha256", "input_sha256", "raw_source_sha256"):
            if name in scope:
                _hash(scope[name], name)
        self._rated_set = frozenset(self.rated_line_indices)
        self._outage_set = frozenset(self.outage_indices)
        self._count = (len(self._rated_set) * len(self._outage_set) -
                       len(self._rated_set & self._outage_set))
        if "eligible_pair_count" in scope:
            actual = _integer(scope["eligible_pair_count"], "eligible pair count")
            if actual != self._count:
                raise PairCodecError("Eligible pair count disagrees with source scope")
        for name in ("eligible_pair_hours", "finite_emergency_line_hours"):
            if name in scope and (type(scope[name]) is not int or scope[name] < 0):
                raise PairCodecError(f"Invalid {name}")
        if "finite_emergency_hour_counts" in scope:
            counts = _counts(scope["finite_emergency_hour_counts"], self)
            pair_hours = sum(counts[i] * (len(self._outage_set) - (i in self._outage_set))
                             for i in self.rated_line_indices)
            for name, expected in (("eligible_pair_hours", pair_hours),
                                   ("finite_emergency_line_hours", sum(counts))):
                if name in scope and (type(scope[name]) is not int or scope[name] != expected):
                    raise PairCodecError(f"Incorrect {name}")
            if "emergency_rated_line_indices" in scope:
                actual = _indices(scope["emergency_rated_line_indices"],
                                  "emergency rated indices", self.line_count, ordered=True)
                if actual != tuple(i for i, count in enumerate(counts) if count):
                    raise PairCodecError("Incorrect emergency rated indices")
        elif "schema" in scope or "descriptor_sha256" in scope:
            raise PairCodecError("Descriptor lacks emergency-hour counts")
        payload = dict(scope)
        declared_hash = payload.pop("descriptor_sha256", None)
        self.scope_sha256 = _digest(payload)
        if "descriptor_sha256" in scope:
            if _hash(declared_hash, "descriptor SHA256") != self.scope_sha256:
                raise PairCodecError("Descriptor SHA256 mismatch")

    def __len__(self):
        return self._count

    def __contains__(self, pair):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return False
        i, k = pair
        return (type(i) is int and type(k) is int and i != k and
                i in self._rated_set and k in self._outage_set)

    def __iter__(self):
        outages = sorted(self.outage_indices)
        for i in self.rated_line_indices:
            for k in outages:
                if i != k:
                    yield i, k


def descriptor(scope, finite_hours):
    """Return a new canonical descriptor, preserving supplied source fields.

    ``finite_hours`` is either an L-entry sequence of counts, or an integer-keyed
    mapping covering every line or exactly the rated lines. Mapping values may
    be counts or strictly increasing, unique retained-hour indices. Normal-only
    rated lines must be represented and contribute a zero count.
    """
    universe = Universe(scope)
    if isinstance(finite_hours, Mapping):
        keys = tuple(finite_hours)
        if any(type(key) is not int for key in keys):
            raise PairCodecError("Emergency-hour mapping keys must be source indices")
        key_set = set(keys)
        if key_set not in (set(range(universe.line_count)), universe._rated_set):
            raise PairCodecError("Emergency-hour mapping must cover all or all rated lines")
        counts = [0] * universe.line_count
        for index, value in finite_hours.items():
            if isinstance(value, (list, tuple)):
                if len(value) > universe.hours:
                    raise PairCodecError("Too many finite emergency hours")
                previous = -1
                for hour in value:
                    _integer(hour, "finite emergency hour", maximum=universe.hours - 1)
                    if hour <= previous:
                        raise PairCodecError("Noncanonical finite emergency hours")
                    previous = hour
                value = len(value)
            counts[index] = _integer(value, "emergency-hour count", maximum=universe.hours)
    else:
        counts = list(_counts(finite_hours, universe))
    counts = list(_counts(counts, universe))
    pair_hours = sum(counts[i] * (len(universe.outage_indices) - (i in universe._outage_set))
                     for i in universe.rated_line_indices)
    result = dict(scope)
    result.pop("descriptor_sha256", None)
    result.update(schema=DESCRIPTOR_SCHEMA, eligible_pair_count=len(universe),
                  eligible_pair_hours=pair_hours, finite_emergency_hour_counts=counts)
    # Reject stale externally supplied summary fields before signing the result.
    for name, expected in (("eligible_pair_hours", pair_hours),
                           ("finite_emergency_hour_counts", counts)):
        if name in scope and scope[name] != expected:
            raise PairCodecError(f"Existing {name} disagrees with finite hours")
    result["descriptor_sha256"] = _digest(result)
    Universe(result)
    return result


class PackedPairs:
    """An exact selected subset; construction requires unique canonical pairs."""

    __slots__ = ("_universe", "_values")

    def __init__(self, scope, iterable=()):
        self._universe = scope if isinstance(scope, Universe) else Universe(scope)
        self._values = array("I")
        if self._values.itemsize != 4:
            raise PairCodecError("This platform does not provide four-byte unsigned integers")
        if isinstance(iterable, PackedPairs):
            if self.scope_sha256 != iterable.scope_sha256:
                raise PairCodecError("Pair sets belong to different source scopes")
            self._values = iterable._values[:]
            return
        previous = -1
        try:
            iterator = iter(iterable)
        except TypeError as exc:
            raise PairCodecError("Pairs must be an explicit iterable") from exc
        if isinstance(iterable, Universe):
            raise PairCodecError("Implicit universe cannot be used as a selected-pair iterable")
        for pair in iterator:
            value = self._encode(pair)
            if value <= previous:
                raise PairCodecError("Pairs must be sorted and unique")
            self._append(value)
            previous = value

    @property
    def scope_sha256(self):
        return self._universe.scope_sha256

    @property
    def line_count(self):
        return self._universe.line_count

    @property
    def nbytes(self):
        return len(self._values) * 4

    def _byte_chunks(self):
        for start in range(0, len(self), _CHUNK_VALUES):
            chunk = self._values[start:start + _CHUNK_VALUES]
            if sys.byteorder != "little":
                chunk.byteswap()
            yield chunk.tobytes()

    def content_sha256(self):
        """Hash canonical sidecar bytes without constructing a full byte copy."""
        digest = hashlib.sha256()
        for payload in self._byte_chunks():
            digest.update(payload)
        return digest.hexdigest()

    def _encode(self, pair):
        if pair not in self._universe:
            raise PairCodecError("Malformed or ineligible source pair")
        i, k = pair
        return i * self.line_count + k

    def _append(self, value):
        if len(self._values) >= MAX_PAIRS:
            raise PairCodecError("Selected-pair storage exceeds frozen 32 MiB cap")
        self._values.append(value)

    def __len__(self):
        return len(self._values)

    def __bool__(self):
        return bool(self._values)

    def __iter__(self):
        for value in self._values:
            yield divmod(value, self.line_count)

    def __contains__(self, pair):
        if pair not in self._universe:
            return False
        value = pair[0] * self.line_count + pair[1]
        index = bisect_left(self._values, value)
        return index < len(self._values) and self._values[index] == value

    def __eq__(self, other):
        if isinstance(other, PackedPairs):
            return self.scope_sha256 == other.scope_sha256 and self._values == other._values
        if isinstance(other, Set):
            return len(self) == len(other) and all(pair in self for pair in other)
        if isinstance(other, (list, tuple)):
            return (len(self) == len(other) and
                    all(isinstance(right, (list, tuple)) and len(right) == 2 and
                        all(type(index) is int for index in right) and left == tuple(right)
                        for left, right in zip(self, other)))
        return NotImplemented

    def _compatible(self, other):
        if not isinstance(other, PackedPairs):
            other = PackedPairs(self._universe, other)
        if self.scope_sha256 != other.scope_sha256:
            raise PairCodecError("Pair sets belong to different source scopes")
        return other

    def merged(self, other):
        other = self._compatible(other)
        result = PackedPairs(self._universe)
        left, right = self._values, other._values
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] < right[j]:
                result._append(left[i])
                i += 1
            elif right[j] < left[i]:
                result._append(right[j])
                j += 1
            else:
                result._append(left[i])
                i += 1
                j += 1
        while i < len(left):
            result._append(left[i])
            i += 1
        while j < len(right):
            result._append(right[j])
            j += 1
        return result

    def union(self, *others):
        if not others:
            return PackedPairs(self._universe, self)
        result = self
        for other in others:
            result = result.merged(other)
        return result

    def update(self, other):
        self._values = self.merged(other)._values

    def intersects(self, other):
        other = self._compatible(other)
        left, right = self._values, other._values
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] == right[j]:
                return True
            if left[i] < right[j]:
                i += 1
            else:
                j += 1
        return False

    __or__ = merged


def write_pairs(path, pairs):
    """Atomically publish an exclusive sidecar and return its complete manifest.

    A hard link publishes the fully written, fsynced temporary file without
    overwriting an existing destination. The destination's parent must exist.
    Paths are recorded exactly as supplied, so relative manifests are portable
    when read from the same artifact root.
    """
    if not isinstance(pairs, PackedPairs):
        raise PairCodecError("write_pairs requires validated PackedPairs")
    destination = Path(path)
    if pairs.nbytes > MAX_PAIR_BYTES:
        raise PairCodecError("Pair file exceeds frozen 32 MiB cap")
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp",
                                      dir=destination.parent)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as stream:
            for payload in pairs._byte_chunks():
                stream.write(payload)
                digest.update(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        os.unlink(temporary)
    return {"schema": PAIRS_SCHEMA, "path": os.fspath(destination), "count": len(pairs),
            "bytes": pairs.nbytes, "sha256": digest.hexdigest(),
            "scope_sha256": pairs.scope_sha256, "line_count": pairs.line_count}


def read_pairs(manifest, scope):
    """Verify all manifest fields, file bytes, ordering and source membership."""
    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_KEYS:
        raise PairCodecError("Invalid pair manifest fields")
    if manifest["schema"] != PAIRS_SCHEMA:
        raise PairCodecError("Unknown pair sidecar schema")
    path = manifest["path"]
    if not isinstance(path, str) or not path or "\x00" in path:
        raise PairCodecError("Invalid pair sidecar path")
    count = _integer(manifest["count"], "pair count", maximum=MAX_PAIRS)
    size = _integer(manifest["bytes"], "pair byte length", maximum=MAX_PAIR_BYTES)
    if size != count * 4:
        raise PairCodecError("Pair byte length does not match count")
    expected_hash = _hash(manifest["sha256"], "sidecar SHA256")
    expected_scope = _hash(manifest["scope_sha256"], "scope SHA256")
    result = PackedPairs(scope)
    if (_integer(manifest["line_count"], "line count", minimum=1) != result.line_count or
            expected_scope != result.scope_sha256):
        raise PairCodecError("Sidecar scope binding mismatch")
    digest = hashlib.sha256()
    previous = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags), "rb") as stream:
            file_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size != size:
                raise PairCodecError("Pair sidecar length/type mismatch")
            remaining = size
            while remaining:
                payload = stream.read(min(remaining, _CHUNK_VALUES * 4))
                if not payload or len(payload) % 4:
                    raise PairCodecError("Truncated pair sidecar")
                remaining -= len(payload)
                digest.update(payload)
                chunk = array("I")
                chunk.frombytes(payload)
                if sys.byteorder != "little":
                    chunk.byteswap()
                for value in chunk:
                    if value <= previous:
                        raise PairCodecError("Pair sidecar is unsorted or duplicated")
                    pair = divmod(value, result.line_count)
                    if pair not in result._universe:
                        raise PairCodecError("Pair sidecar contains an ineligible pair")
                    result._append(value)
                    previous = value
            if stream.read(1):
                raise PairCodecError("Pair sidecar contains trailing bytes")
    except OSError as exc:
        raise PairCodecError(f"Cannot read pair sidecar: {exc}") from exc
    if len(result) != count or digest.hexdigest() != expected_hash:
        raise PairCodecError("Pair sidecar count/SHA256 mismatch")
    return result
