"""Focused storage admission and bounded serialization. No numerical calls."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import time

GiB = 1024 ** 3
MiB = 1024 ** 2
FREE_FLOOR = 2 * GiB
RAW_LIMIT = GiB
ARTIFACT_LIMIT = 1024
MANIFEST_LIMIT = 16 * MiB
STATE_LIMIT = 128 * MiB
FAILURE_LIMIT = 64 * 1024
METADATA_LIMIT = 512 * MiB
PYTHON_FILE_LIMIT = 512 * MiB
NATIVE_FILE_LIMIT = 64 * MiB
NATIVE_THREE_FILES = 3 * NATIVE_FILE_LIMIT
_ACTIVE_WRITERS = []


class StorageAdmissionError(RuntimeError):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt or {}


def allocated_upper(size, block):
    if type(size) is not int or size < 0 or type(block) is not int or block <= 0:
        raise ValueError('invalid allocation size/granularity')
    return ((size + block - 1) // block) * block


def filesystem(path):
    path = Path(path).absolute()
    while not path.exists():
        path = path.parent
    info = path.stat()
    usage = os.statvfs(path)
    return dict(path=str(path), device=info.st_dev, block_bytes=usage.f_frsize or usage.f_bsize,
                available_bytes=usage.f_bavail * (usage.f_frsize or usage.f_bsize))


def require_free(path, additional_bytes, *, purpose):
    fs = filesystem(path)
    inherited = 0
    for write in _ACTIVE_WRITERS:
        target = Path(write.path)
        targetfs = filesystem(target.parent)
        if targetfs['device'] != fs['device']:
            continue
        maximum = allocated_upper(write.max_bytes, fs['block_bytes'])
        try:
            info = target.lstat()
        except FileNotFoundError:
            info = None
        if info is not None:
            if not stat.S_ISREG(info.st_mode) or info.st_size > write.max_bytes:
                raise StorageAdmissionError('active output exceeded bound: ' + str(target))
            maximum = max(0, maximum - min(info.st_blocks * 512,
                          allocated_upper(info.st_size, fs['block_bytes'])))
        inherited += maximum
    required = FREE_FLOOR + additional_bytes + inherited
    receipt = dict(schema='stage-storage-admission/v2', purpose=purpose, **fs,
                   floor_bytes=FREE_FLOOR, additional_bytes=additional_bytes,
                   active_writer_remaining_bytes=inherited,
                   required_available_bytes=required, admitted=fs['available_bytes'] >= required)
    if not receipt['admitted']:
        raise StorageAdmissionError('insufficient free space for ' + purpose, receipt)
    return receipt












@dataclass(frozen=True)
class WriteBound:
    path: str | Path
    max_bytes: int
    basis: str
    enforcement: str
    atomic_replace: bool = False


@contextmanager
def active_writer_reservations(writes):
    """Serialized worker stdout remains reserved during every artifact write."""
    values = list(writes)
    for write in values:
        if (not isinstance(write, WriteBound) or type(write.max_bytes) is not int or
                write.max_bytes < 0 or not write.basis or not write.enforcement or write.atomic_replace):
            raise StorageAdmissionError('invalid active writer bound')
    previous = list(_ACTIVE_WRITERS)
    _ACTIVE_WRITERS.extend(values)
    try:
        yield
    finally:
        _ACTIVE_WRITERS[:] = previous


def admit_phase(destination, *, phase, writes, metadata_bytes=0):
    """Admit explicit closed writer inventories. This is not a future-run guarantee.

    The caller must identify every writer and an actual source/enforced limit;
    a dimension estimate or the snapshot ceiling is not an output bound.
    Independent destination filesystems get independent floor checks.
    """
    if type(metadata_bytes) is not int or metadata_bytes < 0 or metadata_bytes > METADATA_LIMIT:
        raise StorageAdmissionError('phase metadata reservation is unbounded')
    entries, groups, seen = [], {}, set()
    rootfs = filesystem(destination)
    groups[rootfs['device']] = dict(path=destination, extra=metadata_bytes)
    for write in writes:
        if not isinstance(write, WriteBound) or type(write.max_bytes) is not int or write.max_bytes < 0:
            raise StorageAdmissionError('phase writer has no explicit finite bound')
        if not write.basis or not write.enforcement:
            raise StorageAdmissionError('unbounded writer: ' + str(write.path))
        path = Path(write.path).absolute()
        if str(path) in seen:
            raise StorageAdmissionError('duplicate phase writer: ' + str(path))
        seen.add(str(path))
        try:
            info = path.lstat()
        except FileNotFoundError:
            info = None
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise StorageAdmissionError('phase output is not a regular file: ' + str(path))
        current = info.st_size if info is not None else 0
        if current > write.max_bytes:
            raise StorageAdmissionError('phase output already exceeds bound: ' + str(path))
        fs = filesystem(path.parent)
        # Allocated upper growth, not raw-byte subtraction, covers block tails.
        extra = allocated_upper(write.max_bytes, fs['block_bytes'])
        if info is not None and not write.atomic_replace:
            # Sparse/unwritten current bytes must not be assumed allocated.
            extra = max(0, extra - min(info.st_blocks * 512,
                                      allocated_upper(current, fs['block_bytes'])))
        groups.setdefault(fs['device'], dict(path=path.parent, extra=0))['extra'] += extra
        entries.append(dict(path=str(path), current_bytes=current, maximum_bytes=write.max_bytes,
                            additional_allocated_upper_bytes=extra, basis=write.basis,
                            enforcement=write.enforcement, atomic_replace=write.atomic_replace))
    checks = [require_free(group['path'], group['extra'], purpose='phase ' + phase)
              for group in groups.values()]
    return dict(schema='phase-output-admission/v2', phase=phase, writes=entries,
                metadata_bytes=metadata_bytes, filesystems=checks, admitted=True)


@dataclass
class MetadataBudget:
    limit: int = METADATA_LIMIT
    consumed: int = 0

    def charge(self, size):
        if self.consumed + size > self.limit:
            raise StorageAdmissionError('aggregate metadata reservation exhausted')
        self.consumed += size

    @property
    def remaining(self):
        return self.limit - self.consumed


def json_bytes(value, limit=STATE_LIMIT):
    """Bound encoded bytes before any disk write, including exception metadata."""
    result = bytearray()
    for piece in json.JSONEncoder(sort_keys=True, indent=2, allow_nan=False).iterencode(value):
        raw = piece.encode('utf-8')
        if len(result) + len(raw) + 1 > limit:
            raise StorageAdmissionError('serialized JSON byte ceiling exceeded')
        result.extend(raw)
    result.extend(b'\n')
    return bytes(result)


def atomic_json(path, value, *, fresh=False, limit=STATE_LIMIT, metadata_budget=None):
    path = Path(path)
    raw = json_bytes(value, limit)
    fs = filesystem(path.parent)
    amount = allocated_upper(len(raw), fs['block_bytes'])
    if metadata_budget is not None:
        metadata_budget.charge(amount)
    require_free(path.parent, amount, purpose='atomic metadata ' + path.name)
    partial = path.with_name(path.name + '.partial')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(partial, flags, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if fresh:
        os.chmod(partial, 0o444)
        os.link(partial, path, follow_symlinks=False)
        partial.unlink()
    else:
        if path.is_symlink():
            raise StorageAdmissionError('refuse metadata symlink replacement')
        os.replace(partial, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return dict(path=str(path), size_bytes=len(raw), allocated_upper_bytes=amount)


def terminal_failure_json(path, value, *, all_children_reaped, metadata_budget=None):
    """Final minimal receipt only: all children reaped, no later output phases.

    Terminating the attempt releases future output growth. The fixed floor,
    actual atomic write space and remaining metadata budget still apply.
    """
    if all_children_reaped is not True:
        raise StorageAdmissionError('terminal receipt cannot release live writer reservations')
    previous = list(_ACTIVE_WRITERS)
    _ACTIVE_WRITERS.clear()
    try:
        return atomic_json(path, value, fresh=True, limit=FAILURE_LIMIT,
                           metadata_budget=metadata_budget)
    finally:
        _ACTIVE_WRITERS[:] = previous




class BoundedFile:
    """Seek-capable cap for known fresh binary writers such as numpy NPZ."""
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit

    def write(self, data):
        if self.stream.tell() + len(data) > self.limit:
            raise StorageAdmissionError('phase output file byte ceiling exceeded')
        return self.stream.write(data)

    def seek(self, offset, whence=0):
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self.stream.tell() + offset
        elif whence == 2:
            target = os.fstat(self.stream.fileno()).st_size + offset
        else:
            raise ValueError('invalid seek mode')
        if target < 0 or target > self.limit:
            raise StorageAdmissionError('bounded output seek exceeds ceiling')
        return self.stream.seek(offset, whence)

    def truncate(self, size=None):
        size = self.stream.tell() if size is None else size
        if size < 0 or size > self.limit:
            raise StorageAdmissionError('bounded output truncate exceeds ceiling')
        return self.stream.truncate(size)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is None:
            self.stream.flush()
            os.fsync(self.stream.fileno())
        self.stream.close()


def bounded_open(path, max_bytes, *, metadata_budget=None):
    path = Path(path)
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError('invalid bounded output size')
    fs = filesystem(path.parent)
    amount = allocated_upper(max_bytes, fs['block_bytes'])
    if metadata_budget is not None:
        metadata_budget.charge(amount)
    require_free(path.parent, amount, purpose='bounded original output ' + path.name)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return BoundedFile(os.fdopen(fd, 'w+b'), max_bytes)
