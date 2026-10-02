"""Portable binding and integrity helpers. Standard library only; no numerical work."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

DATES = ('2017-02-01', '2017-08-01', '2017-11-01')
STATUS = 'source_and_mock_review_ready_no_numerical_launch'

class BindingError(ValueError):
    pass

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def read_json(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result: raise BindingError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def reject(value): raise BindingError('Nonfinite JSON: ' + value)
    def finite_float(token):
        value = float(token)
        if not math.isfinite(value): reject(token)
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=reject, parse_float=finite_float)

def write_json(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink(): raise BindingError('Refusing existing artifact: ' + str(path))
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())

def checked_path(value, *, exists=True, library=False):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise BindingError('Empty path or control character')
    raw = Path(value).absolute()
    if library and (any(c.isspace() for c in str(raw)) or ':' in str(raw)):
        raise BindingError('Loader paths must contain no whitespace or colon')
    result = raw.resolve(strict=exists)
    if library and (any(c.isspace() for c in str(result)) or ':' in str(result)):
        raise BindingError('Resolved loader path contains whitespace or colon')
    return result

def relative_path(root, name):
    if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts or name in ('', '.'):
        raise BindingError('Invalid relative source path')
    result = checked_path(str(Path(root) / name))
    if not result.is_relative_to(Path(root).resolve()): raise BindingError('Source path escapes root')
    return result

def verify(pins):
    for name, digest in pins.items():
        if not re.fullmatch('[0-9a-f]{64}', digest) or sha(name) != digest:
            raise BindingError('Pinned artifact changed: ' + name)

def fresh_directory(path, protected=()):
    raw = Path(path).absolute()
    checked_path(str(raw), exists=False)
    if raw.exists() or raw.is_symlink(): raise BindingError('Output already exists: ' + str(raw))
    resolved = raw.resolve()
    for item in protected:
        other = Path(item).resolve()
        if resolved == other or resolved.is_relative_to(other) or other.is_relative_to(resolved):
            raise BindingError('Output overlaps a protected input root')
    # Parent must exist, so no ancestor is silently created or reused as output.
    if not raw.parent.is_dir(): raise BindingError('Create the output parent first')
    raw.mkdir(exist_ok=False)
    return raw.resolve()

def bindings(here):
    path = Path(here) / 'BINDINGS.json'
    if not path.exists(): return None  # Pure unit imports only; runtime verification rejects this state.
    value = read_json(path)
    if value.get('schema') != 1 or value.get('driver') != str(Path(here).resolve()):
        raise BindingError('Unrecognized or relocated materialization; prepare a fresh work directory')
    for name in ('work', 'source', 'build', 'data', 'package', 'research_package', 'python', 'binary', 'library', 'extras'):
        checked_path(value[name], library=name in ('library', 'extras'))
    return value

def minimal_environment(here):
    value = bindings(here)
    if value is None:
        # No external process is permitted without a prepared binding; mocks may inspect this.
        work = Path(here).parent / 'UNPREPARED'
        library = work / 'lib'
    else:
        work = Path(value['work'])
        library = Path(value['library']).parent
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'TZ': 'UTC',
            'HOME': str(work/'environment/home'), 'TMPDIR': str(work/'environment/tmp'),
            'XDG_CACHE_HOME': str(work/'environment/cache'),
            'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
            'NUMEXPR_NUM_THREADS': '1', 'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONNOUSERSITE': '1', 'LD_LIBRARY_PATH': str(library)}

def release_pins(value):
    release_path = Path(value['package'])/'PACKAGE_MANIFEST.json'
    if sha(release_path) != value['release_sha256']: raise BindingError('Release manifest changed')
    release = read_json(release_path)
    pins = {str(release_path): value['release_sha256']}
    for name, digest in release['files'].items():
        pins[str(relative_path(value['package'], name))] = digest
        if name.startswith('payload/'):
            pins[str(relative_path(Path(value['work'])/'replay', name.removeprefix('payload/')))] = digest
    for name, digest in release['external_files'].items():
        pins[str(relative_path(value['research_package'], name))] = digest
    for source, target in release['external_materialization'].items():
        pins[str(relative_path(Path(value['work'])/'replay', target))] = release['external_files'][source]
    for date in DATES:
        pins[str(Path(value['data'])/('case89pegase_'+date+'.json.gz'))] = release['data'][date]['compressed_sha256']
    return pins

def assert_clean_bundle(here, value):
    release = read_json(Path(value['package'])/'PACKAGE_MANIFEST.json')
    allowed = {name.removeprefix('payload/') for name in release['files'] if name.startswith('payload/')}
    allowed.update(release['external_materialization'].values())
    allowed.update('combined_screening_driver/'+name for name in ('BINDINGS.json','CAMPAIGN_PLAN.json','REVIEW_MANIFEST.json'))
    replay = Path(value['work'])/'replay'
    for item in replay.rglob('*'):
        if item.name == '__pycache__' or item.suffix in ('.pyc', '.pyo'):
            raise BindingError('Bytecode cache in source bundle: ' + str(item))
        relative = str(item.relative_to(replay))
        if item.is_symlink(): raise BindingError('Symlink in materialized replay: '+relative)
        if item.is_file() and relative not in allowed and not relative.startswith('combined_screening_driver/run_v1/'):
            raise BindingError('Unlisted materialized source: '+relative)
    for item in (Path(value['package'])/'payload').rglob('*'):
        if item.name == '__pycache__' or item.suffix in ('.pyc', '.pyo'):
            raise BindingError('Bytecode cache in release payload: ' + str(item))
    for directory in value['python_inspection']['startup_directories']:
        root = Path(directory)
        if not root.exists(): continue
        hooks = list(root.glob('*.pth')) + list(root.glob('sitecustomize*')) + list(root.glob('usercustomize*'))
        if hooks: raise BindingError('Startup hook requires a clean installation: ' + str(hooks[0]))

def validate_manifest(here, path=None):
    here = Path(here).resolve(); value = bindings(here)
    if value is None: raise BindingError('Run prepare_replay.py prepare first')
    record = read_json(path or here/'REVIEW_MANIFEST.json')
    if record.get('status') != STATUS or record.get('release_sha256') != value['release_sha256']:
        raise BindingError('Unrecognized runtime freeze')
    if record.get('bindings_sha256') != sha(here/'BINDINGS.json'):
        raise BindingError('Runtime bindings changed')
    mandatory = release_pins(value)
    mandatory.update(value['preparation_pins'])
    mandatory[str(here/'BINDINGS.json')] = record['bindings_sha256']
    mandatory[str(here/'CAMPAIGN_PLAN.json')] = value['campaign_plan_sha256']
    inventory_path = Path(value['work'])/'runtime_inventory.json'
    if sha(inventory_path) != record['runtime_inventory_sha256']: raise BindingError('Runtime inventory changed')
    inventory = read_json(inventory_path)
    mandatory.update(inventory['artifact_sha256'])
    mandatory[str(inventory_path)] = record['runtime_inventory_sha256']
    loader_path = Path(value['work'])/'loader_inventory.json'
    if sha(loader_path) != record['loader_inventory_sha256']: raise BindingError('Loader inventory changed')
    mandatory[str(loader_path)] = record['loader_inventory_sha256']
    mandatory.update(read_json(loader_path)['artifact_sha256'])
    pins = record.get('artifact_sha256', {})
    if pins != mandatory: raise BindingError('Mandatory source/runtime pin omitted, added, or changed')
    if Path(sys.executable).absolute() != Path(value['python']).absolute() or not __debug__:
        raise BindingError('Wrong interpreter or disabled assertions')
    assert_clean_bundle(here, value)
    verify(pins)
    return record
