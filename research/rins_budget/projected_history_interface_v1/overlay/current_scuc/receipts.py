"""Local, hash-bound stage receipts over existing immutable run artifacts.

No archive, duplicate data snapshot, network call, or cleanup is part of sealing.
The orchestrator supplies a fresh immutable STATE snapshot at each boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import secrets
import stat
import time

from . import storage_budget as budget

SCHEMA = 'current-scuc-local-stage-receipt/v1'
MANIFEST_SCHEMA = 'current-scuc-local-stage-manifest/v1'
SOURCE_SCHEMA = 'current-scuc-local-source-reference/v1'
MAX_CHECKPOINTS = 9
WHOLE_STORAGE_REQUIRED = 11 * 1024**3
CLI_STORAGE_REQUIRED = 16 * 1024**3
RAW_ALLOCATION_CAP = 1077935104
METADATA_CAP = 65536
NEW_STAGE_METADATA_RESERVE = budget.MANIFEST_LIMIT + budget.STATE_LIMIT + METADATA_CAP + 2 * 4096
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ROLE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z')
_STATES = {
    'post_native_solve': {'unvalidated'},
    'post_full_check': {'validated', 'rejected', 'check_failed', 'check_cancelled', 'check_timeout'},
}
_CHECKED_ROW_KEYS = ('call', 'role', 'master_identity', 'options_artifacts', 'process',
                     'native_limit_receipt', 'master_quality', 'evaluation', 'report')
_HISTORY_CHECKED_ROW_KEYS = ('call', 'role', 'master_identity', 'process', 'master_quality',
                           'evaluation', 'api_evidence', 'solver_random_seed', 'command',
                           'native_limit_seconds', 'allocation_seconds', 'cut_batches',
                           'incumbent_input', 'no_basis_or_search_state_input')


@dataclass(frozen=True)
class Artifact:
    role: str
    path: str | Path
    expected_sha256: str | None = None
    expected_size_bytes: int | None = None


def require(value, message):
    if not value:
        raise ValueError(message)


def _deadline(value):
    require(type(value) in (int, float) and math.isfinite(value), 'finite whole deadline required')
    return float(value)


def clock(deadline):
    if time.monotonic() >= _deadline(deadline):
        raise TimeoutError('whole deadline reached during local receipt work')


def _sha(value, name):
    require(isinstance(value, str) and _SHA.fullmatch(value), 'invalid SHA256: ' + name)


def _json_bytes(value):
    return budget.json_bytes(value, budget.MANIFEST_LIMIT)


def digest(value):
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def _decode(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON constant: ' + value)
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=invalid)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def inside(path, root):
    """Reject symlinks and traversal, including all ancestors of the run root."""
    path, root = Path(path).absolute(), Path(root).absolute()
    require('..' not in path.parts and '..' not in root.parts and path.is_relative_to(root),
            'receipt path outside current run')
    for part in (path, *path.parents):
        require(not part.is_symlink(), 'receipt symlink path or ancestor')
    require(path.resolve() == path and root.resolve() == root, 'ambiguous receipt path')
    return path


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path, limit=METADATA_CAP):
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
            'nonregular or unbounded metadata')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        require(_identity(os.fstat(stream.fileno())) == _identity(before), 'metadata replaced before read')
        raw = stream.read(limit + 1)
        require(len(raw) <= limit and _identity(os.fstat(stream.fileno())) == _identity(before),
                'metadata changed during read')
    require(_identity(path.lstat()) == _identity(before), 'metadata replaced during read')
    return _decode(raw)


def _hash_file(path, deadline, *, seal=False):
    clock(deadline)
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= budget.PYTHON_FILE_LIMIT,
            'artifact must be bounded regular file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        require(_identity(os.fstat(fd)) == _identity(before), 'artifact replaced before read')
        if seal:
            # Only current-run, finished artifacts may be passed for sealing.
            if before.st_mode & 0o222:
                os.fchmod(fd, stat.S_IMODE(before.st_mode) & ~0o222)
            before = os.fstat(fd)
            os.fsync(fd)
        value = hashlib.sha256()
        size = 0
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            clock(deadline)
            size += len(block)
            require(size <= before.st_size, 'artifact grew while hashing')
            value.update(block)
        require(size == before.st_size and _identity(os.fstat(fd)) == _identity(before),
                'artifact changed during read')
    require(_identity(path.lstat()) == _identity(before), 'artifact replaced during read')
    clock(deadline)
    return value.hexdigest(), before


def sha(path, deadline):
    return _hash_file(path, deadline)[0]


def validate_source_reference(reference):
    require(isinstance(reference, dict) and reference.get('schema') == SOURCE_SCHEMA,
            'local source reference schema required')
    _sha(reference.get('source_manifest_sha256'), 'source manifest')
    # A local reference is deliberately independent of any storage-provider schema.
    forbidden = {'library_file_id', 'file_id', 'library_version', 'readback_library_file_id',
                 'readback_file_id', 'readback_library_version', 'archive_sha256'}
    require(not forbidden.intersection(reference), 'remote archival identity is not a local source reference')
    return _decode(_json_bytes(reference))


def _records(manifest, run, deadline, *, verify_members):
    records = manifest.get('artifacts')
    require(isinstance(records, list) and 0 < len(records) <= budget.ARTIFACT_LIMIT,
            'artifact count bound')
    paths, roles, raw, allocated = set(), set(), 0, 0
    for record in records:
        role = record.get('role')
        require(isinstance(role, str) and _ROLE.fullmatch(role) and role not in roles,
                'invalid/duplicate artifact role')
        roles.add(role)
        path = inside(record['path'], run)
        require(str(path) not in paths and not path.is_relative_to(run/'durability'),
                'duplicate/recursive artifact')
        require(path != run/'STATE.json', 'mutable STATE cannot be a sealed artifact')
        paths.add(str(path))
        _sha(record.get('sha256'), 'artifact')
        size = record.get('size_bytes')
        require(type(size) is int and 0 <= size <= budget.PYTHON_FILE_LIMIT, 'artifact size bound')
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o222
                and list(_identity(info)) == record.get('identity') and info.st_size == size,
                'sealed artifact identity or immutable mode changed')
        if verify_members:
            require(sha(path, deadline) == record['sha256'], 'sealed artifact hash mismatch')
        raw += size
        allocated += budget.allocated_upper(size, 4096)
        clock(deadline)
    require('state_snapshot' in roles, 'one immutable state snapshot required')
    require(raw <= budget.RAW_LIMIT and allocated <= RAW_ALLOCATION_CAP, 'retained artifact bound')
    require(manifest.get('raw_bytes') == raw and manifest.get('raw_allocated_upper_bytes') == allocated,
            'retained artifact size mismatch')
    return records


def verify_receipt(receipt_path, run, source_sha256, deadline, *, verify_members=True):
    clock(deadline)
    _sha(source_sha256, 'source manifest')
    run = Path(run).absolute()
    path = inside(receipt_path, run)
    require(path.name == 'local-receipt.json' and path.parent.parent == run/'durability',
            'wrong local receipt location')
    require(re.fullmatch(r'checkpoint-0[1-9]', path.parent.name), 'invalid checkpoint index')
    index = int(path.parent.name[-2:])
    require(set(p.name for p in path.parent.iterdir()) == {'manifest.json', 'local-receipt.json'},
            'partial or unexpected local receipt contents')
    receipt = read(path)
    require(receipt.get('schema') == SCHEMA and receipt.get('outcome') == 'local_verified'
            and receipt.get('durability') == 'LOCAL_FSYNC_HASH', 'unverified local receipt')
    require(receipt.get('run_directory') == str(run) and receipt.get('checkpoint_index') == index
            and receipt.get('source_manifest_sha256') == source_sha256, 'foreign run/index/source')
    require(receipt.get('whole_deadline_monotonic') == _deadline(deadline), 'whole deadline changed')
    require(receipt.get('rlimit_fsize_bytes') == [budget.PYTHON_FILE_LIMIT]*2, 'Python file cap changed')
    manifest_path = inside(path.parent/'manifest.json', run)
    manifest = read(manifest_path, budget.MANIFEST_LIMIT)
    metadata = {str(p): sha(p, deadline) for p in (path, manifest_path)}
    require(metadata[str(manifest_path)] == receipt.get('manifest_sha256'), 'manifest hash mismatch')
    require(manifest.get('schema') == MANIFEST_SCHEMA, 'local manifest schema mismatch')
    for key in ('stage_id', 'nonce', 'point_id', 'stage_kind', 'stage_state', 'run_directory',
                'checkpoint_index', 'whole_deadline_monotonic', 'source_manifest_sha256'):
        require(receipt.get(key) == manifest.get(key), 'stage identity mismatch: ' + key)
    require(isinstance(receipt.get('nonce'), str) and _SHA.fullmatch(receipt['nonce']), 'invalid stage nonce')
    require(receipt.get('stage_id') == path.parent.name + '-' + receipt['nonce'][:16], 'stage identity changed')
    require(manifest['stage_state'] in _STATES.get(manifest['stage_kind'], set()), 'invalid stage state')
    reference = validate_source_reference(manifest['source_reference'])
    require(reference['source_manifest_sha256'] == source_sha256
            and digest(reference) == receipt.get('source_reference_sha256'), 'source reference mismatch')
    records = _records(manifest, run, deadline, verify_members=verify_members)
    require(digest(records) == receipt.get('content_sha256'), 'artifact inventory hash mismatch')
    require(receipt.get('raw_bytes') == manifest['raw_bytes']
            and receipt.get('raw_allocated_upper_bytes') == manifest['raw_allocated_upper_bytes'],
            'receipt artifact size mismatch')
    prior = receipt.get('prior_receipts')
    require(isinstance(prior, list) and len(prior) == index-1, 'prior checkpoint chain length')
    for number, item in enumerate(prior, 1):
        previous = inside(item['path'], run)
        require(previous == run/'durability'/f'checkpoint-{number:02d}'/'local-receipt.json',
                'prior checkpoint scope/order')
        require(sha(previous, deadline) == item['sha256'], 'prior local receipt changed')
    clock(deadline)
    return dict(receipt=receipt, manifest=manifest, metadata_files_sha256=metadata)


def metadata_bytes(verified):
    # Snapshot JSON is retained once; repeated seals refer to existing bytes.
    return 2*4096 + sum(budget.allocated_upper(Path(path).lstat().st_size, 4096)
                       for path in verified['metadata_files_sha256'])


def verify_run(run, source_sha256, deadline, *, verify_members=True):
    run = Path(run).absolute()
    root = inside(run/'durability', run)
    if not root.exists():
        return []
    paths = sorted(root.iterdir())
    require(len(paths) <= MAX_CHECKPOINTS, 'maximum nine local checkpoints')
    verified, wanted = [], []
    for number, checkpoint in enumerate(paths, 1):
        require(checkpoint.name == f'checkpoint-{number:02d}' and checkpoint.is_dir()
                and not checkpoint.is_symlink(), 'partial or invalid checkpoint sequence')
        path = checkpoint/'local-receipt.json'
        item = verify_receipt(path, run, source_sha256, deadline, verify_members=verify_members)
        require(item['receipt']['prior_receipts'] == wanted, 'predecessor receipt chain mismatch')
        wanted.append(dict(path=str(path), sha256=item['metadata_files_sha256'][str(path)]))
        verified.append(item)
    snapshots = {record['path']: record['size_bytes'] for item in verified
                 for record in item['manifest']['artifacts'] if record['role'] == 'state_snapshot'}
    total = sum(metadata_bytes(item) for item in verified)
    total += sum(budget.allocated_upper(size, 4096) for size in snapshots.values())
    require(total + METADATA_CAP <= budget.METADATA_LIMIT, 'whole-run local metadata cap')
    return verified


def failure_metadata(run, exc):
    path = Path(run)/'local-checkpoint-failure.json'
    if path.exists():
        return str(path)
    value = dict(schema='current-scuc-local-stage-failure/v1', durability='LOCAL_FSYNC_HASH',
                 outcome='failed_or_incomplete', error_type=type(exc).__name__, error=str(exc)[:8192],
                 numerical_retry_permitted=False, data_checkpoint_retry_permitted=False,
                 recorded_at=datetime.now(timezone.utc).isoformat())
    budget.atomic_json(path, value, fresh=True, limit=METADATA_CAP)
    return str(path)


class Checkpoints:
    def __init__(self, run, source_reference, deadline):
        self.run = inside(Path(run).absolute(), Path(run).absolute())
        require(self.run.is_dir(), 'existing run directory required')
        self.reference = validate_source_reference(source_reference)
        self.source_sha256 = self.reference['source_manifest_sha256']
        self.deadline = _deadline(deadline)
        self.failed, self.pins = False, []
        require(not (self.run/'durability').exists(), 'fresh local checkpoint run required')

    def seal(self, *, point_id, stage_kind, state, artifacts, measurements, cleanup_receipt):
        try:
            require(not self.failed and not (self.run/'local-checkpoint-failure.json').exists(),
                    'prior local checkpoint failure is terminal')
            clock(self.deadline)
            require(resource.getrlimit(resource.RLIMIT_FSIZE) == (budget.PYTHON_FILE_LIMIT,)*2,
                    'exact inherited 512 MiB Python file limits required')
            require(isinstance(point_id, str) and _ROLE.fullmatch(point_id), 'invalid stage point identity')
            require(state in _STATES.get(stage_kind, set()), 'invalid stage state')
            require(isinstance(measurements, dict) and isinstance(cleanup_receipt, dict),
                    'measurements and cleanup receipt must be objects')
            previous = verify_run(self.run, self.source_sha256, self.deadline, verify_members=True)
            pins = [dict(path=str(self.run/'durability'/f'checkpoint-{i:02d}'/'local-receipt.json'),
                         sha256=item['metadata_files_sha256'][str(self.run/'durability'/f'checkpoint-{i:02d}'/'local-receipt.json')])
                    for i, item in enumerate(previous, 1)]
            require(pins == self.pins, 'local receipt chain changed since preceding boundary')
            require(len(previous) < MAX_CHECKPOINTS, 'maximum nine local checkpoints')
            prior_snapshots = {record['path']: record['size_bytes'] for item in previous
                               for record in item['manifest']['artifacts'] if record['role'] == 'state_snapshot'}
            prior_metadata = sum(metadata_bytes(item) for item in previous)
            prior_metadata += sum(budget.allocated_upper(size, 4096) for size in prior_snapshots.values())
            require(prior_metadata + NEW_STAGE_METADATA_RESERVE <= budget.METADATA_LIMIT,
                    'whole-run metadata reserve cannot admit next checkpoint')
            items = list(artifacts)
            require(0 < len(items) <= budget.ARTIFACT_LIMIT and all(isinstance(item, Artifact) for item in items),
                    'explicit bounded Artifact allowlist required')
            require(sum(item.role == 'state_snapshot' for item in items) == 1,
                    'exactly one immutable state snapshot required')
            paths, roles, admitted = set(), set(), []
            raw = allocated = 0
            for item in items:
                require(isinstance(item.role, str) and _ROLE.fullmatch(item.role) and item.role not in roles,
                        'invalid or duplicate artifact role')
                roles.add(item.role)
                path = inside(item.path, self.run)
                require(path != self.run/'STATE.json' and not path.is_relative_to(self.run/'durability'),
                        'mutable STATE or recursive durability input')
                require(str(path) not in paths, 'duplicate artifact path')
                paths.add(str(path))
                info = path.lstat()
                require(stat.S_ISREG(info.st_mode) and info.st_size <= budget.PYTHON_FILE_LIMIT,
                        'artifact type/size bound')
                if item.expected_sha256 is not None:
                    _sha(item.expected_sha256, 'expected artifact')
                require(item.expected_size_bytes is None or
                        type(item.expected_size_bytes) is int and item.expected_size_bytes == info.st_size,
                        'expected artifact size mismatch')
                raw += info.st_size
                allocated += budget.allocated_upper(info.st_size, 4096)
                admitted.append((item, path, _identity(info)))
            require(raw <= budget.RAW_LIMIT and allocated <= RAW_ALLOCATION_CAP, 'retained artifact bound')
            admission = budget.require_free(self.run, NEW_STAGE_METADATA_RESERVE,
                                            purpose='local immutable stage receipt metadata')
            require(admission['block_bytes'] == 4096, 'local receipt requires reviewed 4 KiB allocation')
            started = time.monotonic()
            index = len(previous) + 1
            root = self.run/'durability'
            if not root.exists():
                root.mkdir(mode=0o700)
                _fsync_dir(self.run)
            stage = inside(root/f'checkpoint-{index:02d}', self.run)
            stage.mkdir(mode=0o700)
            _fsync_dir(root)
            records = []
            for item, path, identity in admitted:
                require(_identity(path.lstat()) == identity, 'artifact changed before sealing')
                value, info = _hash_file(path, self.deadline, seal=True)
                require(item.expected_sha256 is None or value == item.expected_sha256,
                        'expected artifact hash mismatch')
                records.append(dict(role=item.role, path=str(path), sha256=value,
                                    size_bytes=info.st_size, identity=list(_identity(info))))
            for parent in sorted({Path(record['path']).parent for record in records}):
                _fsync_dir(parent)
            snapshot = next(record for record in records if record['role'] == 'state_snapshot')
            checked = read(snapshot['path'], budget.STATE_LIMIT)
            require(checked.get('run_directory') == str(self.run)
                    and checked.get('source_manifest_sha256') == self.source_sha256,
                    'state snapshot run/source mismatch')
            nonce = secrets.token_hex(32)
            identity = dict(run_directory=str(self.run), checkpoint_index=index,
                            stage_id=stage.name+'-'+nonce[:16], nonce=nonce, point_id=point_id,
                            stage_kind=stage_kind, stage_state=state,
                            source_manifest_sha256=self.source_sha256,
                            whole_deadline_monotonic=self.deadline)
            manifest = dict(schema=MANIFEST_SCHEMA, **identity, source_reference=self.reference,
                            artifacts=records, measurements=measurements, cleanup_receipt=cleanup_receipt,
                            raw_bytes=raw, raw_allocated_upper_bytes=allocated,
                            accounting=dict(started_monotonic=started, storage_admission=admission))
            manifest_path = stage/'manifest.json'
            budget.atomic_json(manifest_path, manifest, fresh=True, limit=budget.MANIFEST_LIMIT)
            receipt = dict(schema=SCHEMA, **identity, outcome='local_verified', durability='LOCAL_FSYNC_HASH',
                           source_reference_sha256=digest(self.reference), manifest_sha256=sha(manifest_path, self.deadline),
                           content_sha256=digest(records), raw_bytes=raw, raw_allocated_upper_bytes=allocated,
                           prior_receipts=pins, rlimit_fsize_bytes=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
                           elapsed_seconds_before_receipt=time.monotonic()-started)
            path = stage/'local-receipt.json'
            clock(self.deadline)
            budget.atomic_json(path, receipt, fresh=True, limit=METADATA_CAP)
            verified = verify_receipt(path, self.run, self.source_sha256, self.deadline, verify_members=True)
            self.pins.append(dict(path=str(path), sha256=verified['metadata_files_sha256'][str(path)]))
            clock(self.deadline)
            return str(path)
        except BaseException as exc:
            self.failed = True
            try:
                failure_metadata(self.run, exc)
            except BaseException:
                pass
            raise


def admit_cli(run_parent):
    """Fixed complete-CLI bound, checked before any preparation work."""
    actual = budget.filesystem(run_parent)
    require(actual['block_bytes'] == 4096, 'CLI storage requires reviewed 4 KiB allocation')
    if actual['available_bytes'] < CLI_STORAGE_REQUIRED:
        raise budget.StorageAdmissionError('complete CLI retention plus launch margin does not fit',
            dict(**actual, required_available_bytes=CLI_STORAGE_REQUIRED, admitted=False))
    admission = budget.require_free(run_parent, CLI_STORAGE_REQUIRED-budget.FREE_FLOOR,
        purpose='complete CLI retention including launch margin')
    admission['absolute_launch_threshold_bytes'] = CLI_STORAGE_REQUIRED
    return admission


def admit_whole(run_parent):
    actual = budget.filesystem(run_parent)
    require(actual['block_bytes'] == 4096, 'whole storage requires reviewed 4 KiB allocation')
    if actual['available_bytes'] < WHOLE_STORAGE_REQUIRED:
        raise budget.StorageAdmissionError('whole local retention plus launch margin does not fit',
            dict(**actual, required_available_bytes=WHOLE_STORAGE_REQUIRED, admitted=False))
    admission = budget.require_free(run_parent,
        WHOLE_STORAGE_REQUIRED-budget.FREE_FLOOR-budget.PYTHON_FILE_LIMIT,
        purpose='whole local checkpoint retention including launch margin')
    admission['absolute_launch_threshold_bytes'] = WHOLE_STORAGE_REQUIRED
    return admission


def bind_checked_stage(receipt_path, run, call, source_sha256, expected_row):
    """Bind a selected carry point to validated immutable local stage bytes."""
    require(type(call) is int and 1 <= call <= 3 and isinstance(expected_row, dict), 'checked call/row required')
    run = Path(run).absolute()
    preliminary = read(inside(receipt_path, run))
    deadline = preliminary['whole_deadline_monotonic']
    verified = verify_receipt(receipt_path, run, source_sha256, deadline, verify_members=True)
    receipt, manifest = verified['receipt'], verified['manifest']
    require(receipt['point_id'] == f'mip-{call:02d}' and receipt['stage_kind'] == 'post_full_check'
            and receipt['stage_state'] == 'validated', 'not this call validated checkpoint')
    records = {record['path']: record for record in manifest['artifacts']}
    snapshot = next(record for record in records.values() if record['role'] == 'state_snapshot')
    state = read(snapshot['path'], budget.STATE_LIMIT)
    require(state.get('run_directory') == str(run) and state.get('source_manifest_sha256') == source_sha256,
            'checked state snapshot run/source mismatch')
    rows = [row for row in state['trace'] if row.get('call') == call]
    require(len(rows) == 1 and expected_row.get('call') == call, 'checked row identity')
    row = rows[0]
    history = row.get('role') == 'history_probe'
    checked_row_keys = _HISTORY_CHECKED_ROW_KEYS if history else _CHECKED_ROW_KEYS
    require(all(key in row and row[key] == expected_row.get(key) for key in checked_row_keys),
            'selected point differs from checked STATE snapshot')
    rd, bound = run/f'mip-{call:02d}', {}

    def member(path, expected=None):
        path = inside(path, run)
        require(path.is_relative_to(rd), 'checked member belongs to another call')
        record = records.get(str(path))
        require(record is not None, 'checked member absent from stage manifest')
        require(expected is None or record['sha256'] == expected, 'checked member metadata/hash mismatch')
        require(sha(path, deadline) == record['sha256'], 'checked member bytes changed')
        bound[str(path)] = record['sha256']

    identity = row['master_identity']
    require(Path(identity['model_path']).absolute() == rd/'master.mps', 'wrong checked master path')
    for prefix in ('model', 'expected', 'api_report', 'row_sidecar'):
        member(identity[prefix+'_path'], identity[prefix+'_sha256'])
    if history:
        from current_scuc.history_scuc import verify_api_evidence
        api = verify_api_evidence(row, expected_seed=state['solver_random_seed'])
        for path, digest_value in api['files_sha256'].items():
            member(path, digest_value)
    else:
        member(rd/'solution.sol')
        for prefix in ('options', 'readback'):
            member(row['options_artifacts'][prefix+'_path'], row['options_artifacts'][prefix+'_sha256'])
    for name in ('adaptive_support_artifact', 'stored_lift_artifact', 'oracle_artifact',
                 'full_source_quality_artifact', 'source_quality_artifact'):
        artifact = row['evaluation'][name]
        for key in ('document', 'arrays'):
            if key in artifact:
                require(Path(artifact[key]['path']).name == artifact[key]['path'], 'checked artifact path scope')
                member(rd/artifact[key]['path'], artifact[key]['sha256'])
    files = dict(verified['metadata_files_sha256'])
    files[snapshot['path']] = snapshot['sha256']
    return dict(schema='current-scuc-checked-local-stage-binding/v1', stage_id=receipt['stage_id'],
                nonce=receipt['nonce'], receipt_sha256=files[str(Path(receipt_path).absolute())],
                content_sha256=receipt['content_sha256'], source_manifest_sha256=source_sha256,
                call=call, metadata_files_sha256=files, checked_point_files_sha256=bound,
                checked_row_sha256=digest({key: row[key] for key in checked_row_keys}),
                durability='LOCAL_FSYNC_HASH', bytes_reread=True, new_checkpoint_created=False)
