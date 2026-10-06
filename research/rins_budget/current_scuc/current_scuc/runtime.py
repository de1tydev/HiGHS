"""Local HiGHS identities and explicit native qualification.

Discovery and manifest verification perform no native load or solve. Runtime
hashes identify this build; they are never compared to historical ELF hashes.
Scientific callers still own effective-option, matrix and result admission.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import sys

SCHEMA = 'current-scuc-native-runtime/v1'
SOURCE_COMMIT = 'd547a3ad8af5399651187fb0e133cf0e42615b82'
SOURCE_TREE = '788b41e141fa455509c71593e1718b7b71168320'
SOURCE_REPOSITORY = 'https://github.com/ERGO-Code/HiGHS'
NATIVE_GITHASH = 'd547a3ad8a'
HIGHS_VERSION = '1.15.1'
GUARD_INDEX_SHA256 = '3cade5b38755a4f3c6fdedd36f07dea3d3cd62203d9f4acdcd800331f4050eb3'
HELPER_SOURCE_SHA256 = 'b7cd24d5852080cde20e2d0e269783090bfc004fa2f82fb30f92c9b3ecc73d4a'
MANIFEST_ENV = 'CURRENT_SCUC_RUNTIME_MANIFEST'
RECOVERED_NATIVE_HASHES = {
    'binary':'46437643f469aab7ada837b257ec13273d932e7a099033ffda4491abab682ebd',
    'library':'a3bbbf553c3590769eb289d56e82b8cad8bb2b84aa8f7f6aabfa7eecb9c7ffa3',
    'extras':'add1358fa82827a3ead2137b8483956fb8f38ff86f2b0ada974125dcb58b7e0d',
    'native_assess':'df3611f5cdeb340dbeb9962ac877341ec75206cc38bf441fd73ede85c931c444',
}
EXPECTED_OPTIONS = {
    'CMAKE_BUILD_TYPE': 'Release', 'FAST_BUILD': 'ON',
    'BUILD_SHARED_LIBS': 'ON', 'BUILD_SHARED_EXTRAS_LIB': 'ON',
    'HIPO': 'OFF', 'HIGHSINT64': 'OFF', 'DEBUGSOL': 'OFF',
    'ZLIB': 'ON', 'CUPDLP_GPU': 'OFF', 'HIPDLP_HIP': 'OFF',
    'BUILD_TESTING': 'ON', 'ALL_TESTS': 'ON',
    'CMAKE_C_FLAGS': '', 'CMAKE_CXX_FLAGS': '',
    'CMAKE_C_FLAGS_RELEASE': '-O3 -DNDEBUG',
    'CMAKE_CXX_FLAGS_RELEASE': '-O3 -DNDEBUG',
    'CMAKE_EXE_LINKER_FLAGS': '-flto=2',
    'CMAKE_SHARED_LINKER_FLAGS': '-flto=2',
}
BUILD_COMMAND = 'See native/BUILD.md; build the official pinned source, then run native/make_runtime_manifest.py'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def strict_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON value: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=invalid)


def source_guard_hashes():
    path = Path(__file__).with_name('native_source_guards.json')
    require(sha256(path) == GUARD_INDEX_SHA256, 'Bundled native source guard inventory changed')
    return strict_json(path)


def _resolve(base, value, label):
    require(type(value) is str and value and '\x00' not in value, 'Missing ' + label)
    path = Path(value)
    return (base / path).resolve(strict=True) if not path.is_absolute() else path.resolve(strict=True)


def _record(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file(), 'Not a regular file: ' + str(path))
    return {'path': str(path), 'sha256': sha256(path), 'bytes': path.stat().st_size}


def _checked_record(base, item, label):
    require(type(item) is dict and set(item) == {'path', 'sha256', 'bytes'}, 'Invalid artifact record: ' + label)
    path = _resolve(base, item['path'], label)
    require(type(item['bytes']) is int and item['bytes'] > 0 and path.stat().st_size == item['bytes'],
            'Artifact size mismatch: ' + label)
    require(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}', item['sha256']) and
            sha256(path) == item['sha256'], 'Artifact hash mismatch: ' + label)
    return path


def cmake_cache(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line or line.startswith(('#', '//')):
            continue
        match = re.fullmatch(r'([^:=]+):[^=]+=(.*)', line)
        if match:
            require(match[1] not in values, 'Duplicate CMake cache key: ' + match[1])
            values[match[1]] = match[2]
    return values


def validate_build(cache_path, hconfig_path):
    cache = cmake_cache(cache_path)
    for name, expected in EXPECTED_OPTIONS.items():
        require(cache.get(name) == expected, 'Unsupported native build option: ' + name)
    text = Path(hconfig_path).read_text()
    for macro in ('FAST_BUILD', 'ZLIB_FOUND', 'CUPDLP_CPU', 'HIGHS_SHARED_EXTRAS_LIBRARY'):
        require(re.search(r'^#define ' + macro + r'\s*$', text, re.M), 'Required build macro missing: ' + macro)
    for macro in ('HIGHSINT64', 'HIPO', 'CUPDLP_GPU', 'HIGHS_DEBUGSOL'):
        require(not re.search(r'^#define ' + macro + r'\b', text, re.M), 'Unsupported build macro: ' + macro)
    for macro, value in {'HIGHS_GITHASH': '"'+NATIVE_GITHASH+'"', 'HIGHS_VERSION_MAJOR':'1',
                         'HIGHS_VERSION_MINOR':'15', 'HIGHS_VERSION_PATCH':'1', 'CMAKE_BUILD_TYPE':'"Release"'}.items():
        require(re.findall(r'^#define '+macro+r'\s+(.+)$', text, re.M) == [value], 'Build header mismatch: '+macro)
    for key in ('CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_GENERATOR'):
        require(cache.get(key), 'Missing native build provenance: ' + key)
    return cache


def git_tree_from_inventory(records):
    """Reconstruct the upstream Git tree identity, including executable modes."""
    tree = {}
    require(type(records) is list and 1 <= len(records) <= 10000, 'Invalid source inventory')
    for row in records:
        require(type(row) is dict and set(row) == {'path','mode','git_blob','sha256','bytes'}, 'Invalid source inventory row')
        p = PurePosixPath(row['path'])
        require(not p.is_absolute() and str(p) == row['path'] and all(x not in ('','.','..') for x in p.parts), 'Unsafe source inventory path')
        require(row['mode'] in ('100644','100755') and re.fullmatch('[0-9a-f]{40}', row['git_blob']) and
                re.fullmatch('[0-9a-f]{64}', row['sha256']) and type(row['bytes']) is int and row['bytes'] >= 0,
                'Invalid source inventory identity')
        node = tree
        for part in p.parts[:-1]:
            require(not isinstance(node.get(part), tuple), 'Source path collision')
            node = node.setdefault(part, {})
        require(p.name not in node, 'Duplicate source inventory path')
        node[p.name] = (row['mode'], row['git_blob'])
    def git_hash(node):
        payload = b''
        for name in sorted(node, key=lambda k: k.encode()+ (b'/' if isinstance(node[k],dict) else b'')):
            value = node[name]
            mode, digest = ('40000', git_hash(value)) if isinstance(value,dict) else value
            payload += mode.encode()+b' '+name.encode()+b'\0'+bytes.fromhex(digest)
        return hashlib.sha1(b'tree '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
    return git_hash(tree)


@dataclass(frozen=True)
class RuntimePaths:
    manifest_path: Path
    manifest_sha256: str
    binary: Path
    library: Path
    extras: Path
    native_assess: Path
    source_root: Path
    build_root: Path
    artifacts: dict
    manifest: dict

    def driver_config(self):
        pins = {str(path): self.manifest['artifacts'][key]['sha256'] for key,path in self.artifacts.items()}
        libraries = {str(self.library): pins[str(self.library)], str(self.extras): pins[str(self.extras)]}
        for alias in ('libhighs.so', 'libhighs.so.1'):
            path = self.library.parent / alias
            if path.is_file():
                require(path.resolve() == self.library and sha256(path) == pins[str(self.library)], 'Library alias changed')
                libraries[str(path)] = pins[str(self.library)]
        pins.update(libraries)
        return dict(binary=str(self.binary), library=str(self.library), extras=str(self.extras),
                    native_assess=str(self.native_assess), native_assess_source=str(self.artifacts['native_assess_source']),
                    binary_sha256=pins[str(self.binary)], library_sha256=pins[str(self.library)],
                    extras_sha256=pins[str(self.extras)], native_assess_sha256=pins[str(self.native_assess)],
                    hconfig_sha256=pins[str(self.artifacts['hconfig'])],
                    cmake_cache_sha256=pins[str(self.artifacts['cmake_cache'])],
                    source_root=str(self.source_root), build_root=str(self.build_root),
                    runtime_manifest=str(self.manifest_path), runtime_manifest_sha256=self.manifest_sha256,
                    runtime_pins=pins, runtime_library_pins=libraries, build_pins=dict(pins),
                    native_source_guards=source_guard_hashes(), pristine_source_commit=SOURCE_COMMIT,
                    pristine_source_tree=SOURCE_TREE, python=str(Path(sys.executable).absolute()),
                    runtime_identity_kind=self.manifest.get('runtime_identity_kind','locally_rebuilt_official_source'), native_qualified=False)

    def verify(self):
        require(sha256(self.manifest_path) == self.manifest_sha256, 'Runtime manifest changed')
        return discover_runtime(self.binary, self.manifest_path)


def discover_runtime(highs, runtime_manifest=None):
    """Verify files and semantics only; the caller separately qualifies native code."""
    binary = Path(highs).expanduser().resolve(strict=True)
    if runtime_manifest is None:
        candidates = [binary.parent.parent/'runtime-manifest.json',
                      binary.parent.parent/'share/current_scuc/runtime-manifest.json']
        found = [path for path in candidates if path.is_file()]
        require(len(found) == 1, 'HiGHS needs one matching runtime-manifest.json. ' + BUILD_COMMAND)
        manifest_path = found[0].resolve()
    else:
        manifest_path = Path(runtime_manifest).expanduser().resolve(strict=True)
    manifest_digest = sha256(manifest_path)
    m = strict_json(manifest_path)
    require(m.get('schema') == SCHEMA, 'Unsupported native runtime manifest. ' + BUILD_COMMAND)
    source = m.get('source', {})
    require(source.get('repository') == SOURCE_REPOSITORY and source.get('commit') == SOURCE_COMMIT and
            source.get('tree') == SOURCE_TREE and source.get('version') == HIGHS_VERSION and
            source.get('native_githash') == NATIVE_GITHASH, 'Unsupported HiGHS source identity')
    require(git_tree_from_inventory(source.get('files')) == SOURCE_TREE, 'Native source inventory tree mismatch')
    source_root = _resolve(manifest_path.parent, m.get('source_root'), 'source_root')
    build_root = _resolve(manifest_path.parent, m.get('build_root'), 'build_root')
    require(source_root.is_dir() and build_root.is_dir(), 'Missing native source/build directory')
    inventory = {row['path']:row for row in source['files']}
    for relative, digest in source_guard_hashes().items():
        require(relative in inventory and inventory[relative]['sha256'] == digest and
                sha256(source_root/relative) == digest, 'Native source guard mismatch: '+relative)
        data = (source_root/relative).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        require(blob == inventory[relative]['git_blob'], 'Native guard differs from official Git tree: '+relative)
    required = {'binary','library','extras','native_assess','native_assess_source','hconfig','cmake_cache','helper_build_receipt'}
    require(type(m.get('artifacts')) is dict and required <= m['artifacts'].keys(), 'Incomplete native runtime artifact inventory')
    artifacts = {key:_checked_record(manifest_path.parent,item,key) for key,item in m['artifacts'].items()}
    require(artifacts['binary'] == binary, '--highs differs from runtime manifest binary')
    require(artifacts['hconfig'] == (build_root/'HConfig.h').resolve() and
            artifacts['cmake_cache'] == (build_root/'CMakeCache.txt').resolve(), 'Build evidence path mismatch')
    require(os.access(binary,os.X_OK) and os.access(artifacts['native_assess'],os.X_OK), 'Native executable permission missing')
    require(sha256(artifacts['native_assess_source']) == HELPER_SOURCE_SHA256, 'Assessment helper must be exact v3 source')
    cache = validate_build(artifacts['cmake_cache'], artifacts['hconfig'])
    require(m.get('build_options') == {k:cache[k] for k in EXPECTED_OPTIONS}, 'Build option record mismatch')
    require(m.get('compiler') == {k:cache[k] for k in ('CMAKE_C_COMPILER','CMAKE_CXX_COMPILER','CMAKE_GENERATOR')}, 'Compiler record mismatch')
    require(any(k.startswith('c_compiler_') for k in artifacts) and any(k.startswith('cxx_compiler_') for k in artifacts), 'Compiler evidence missing')
    helper = strict_json(artifacts['helper_build_receipt'])
    if m.get('runtime_identity_kind','locally_rebuilt_official_source') == 'recovered_current_v3':
        require(helper.get('schema') == 'current-scuc-recovered-assess/v1' and
                helper.get('source_sha256') == HELPER_SOURCE_SHA256 and
                helper.get('source_commit') == SOURCE_COMMIT and
                helper.get('rebuild_performed') is False and
                helper.get('original_build_receipt_is_not_v3_proof') is True,
                'Recovered assessment provenance mismatch')
        for key,digest in RECOVERED_NATIVE_HASHES.items():
            require(m['artifacts'][key]['sha256'] == digest, 'Recovered native artifact mismatch: '+key)
    else:
        require(m.get('runtime_identity_kind','locally_rebuilt_official_source') == 'locally_rebuilt_official_source',
                'Unsupported runtime identity kind')
        require(helper.get('schema') == 'current-scuc-native-assess-build/v1' and
                helper.get('source_sha256') == HELPER_SOURCE_SHA256 and
                helper.get('source_commit') == SOURCE_COMMIT and
                helper.get('library_sha256') == m['artifacts']['library']['sha256'] and
                helper.get('binary_sha256') == m['artifacts']['native_assess']['sha256'] and
                helper.get('hconfig_sha256') == m['artifacts']['hconfig']['sha256'] and
                type(helper.get('command')) is list and helper['command'] and
                '-std=c++17' in helper['command'], 'Assessment helper build evidence mismatch')
    require(sha256(manifest_path) == manifest_digest, 'Runtime manifest changed during verification')
    return RuntimePaths(manifest_path,manifest_digest,binary,artifacts['library'],artifacts['extras'],
                        artifacts['native_assess'],source_root,build_root,artifacts,m)


def load_runtime_config(path):
    m = strict_json(path)
    require(m.get('schema') == SCHEMA and 'binary' in m.get('artifacts',{}), 'Expected native runtime manifest')
    binary = _resolve(Path(path).resolve().parent,m['artifacts']['binary']['path'],'binary')
    return discover_runtime(binary,path).driver_config()


def runtime_path(relative, cfg=None):
    """Map scientific source/build references to the verified local installation."""
    if cfg is None:
        path = os.environ.get(MANIFEST_ENV)
        require(path, 'Set '+MANIFEST_ENV+' before loading scientific modules')
        cfg = load_runtime_config(path)
    value = PurePosixPath(str(relative))
    require(not value.is_absolute() and '..' not in value.parts, 'Unsafe runtime-relative path')
    mapping = {'pristine-source':cfg['source_root'], 'pristine-build':cfg['build_root']}
    if value.parts and value.parts[0] in mapping:
        return Path(mapping[value.parts[0]]).joinpath(*value.parts[1:])
    if str(value) in ('projected-start-containment-v3/native_assess','projected-start-containment-build-v1/native_assess'):
        return Path(cfg['native_assess'])
    if str(value) == 'projected-start-containment-v3/native_assess.cpp':
        return Path(cfg['native_assess_source'])
    raise ValueError('Unmapped native runtime path: '+str(value))


def platform_guard():
    require(sys.platform == 'linux' and platform.machine() in ('x86_64','amd64') and
            sys.byteorder == 'little' and struct.calcsize('P') == 8 and struct.calcsize('d') == 8,
            'Initial runtime requires Linux x86-64, little-endian binary64')


def symbol_provenance(lib, names):
    """Resolve actual loaded DSO origins; never infer them from requested paths."""
    import ctypes as C
    P = C.c_void_p
    class DlInfo(C.Structure):
        _fields_ = [('filename',C.c_char_p),('base',P),('symbol',C.c_char_p),('address',P)]
    dladdr = C.CDLL(None).dladdr
    dladdr.restype, dladdr.argtypes = C.c_int,[P,C.POINTER(DlInfo)]
    result = {}
    for name in names:
        info = DlInfo()
        require(dladdr(C.cast(getattr(lib,name),P),C.byref(info)) != 0 and info.filename,
                'Cannot identify native symbol: '+name)
        path = Path(info.filename.decode()).resolve(strict=True)
        result[name] = dict(path=str(path),sha256=sha256(path),symbol=info.symbol.decode() if info.symbol else None)
    return result


def qualify_capi(runtime):
    """Explicit native empty-handle ABI/DSO test; no model, solve or presolve."""
    import ctypes as C
    platform_guard()
    runtime.verify()
    I,P = C.c_int32,C.c_void_p
    lib = C.CDLL(str(runtime.library))
    # Extras are required even though the public C API lives in libhighs.
    C.CDLL(str(runtime.extras))
    signatures = {'Highs_create':(P,[]),'Highs_destroy':(None,[P]),
        'Highs_version':(C.c_char_p,[]),'Highs_githash':(C.c_char_p,[]),'Highs_getSizeofHighsInt':(I,[P])}
    for name,(restype,argtypes) in signatures.items():
        getattr(lib,name).restype,getattr(lib,name).argtypes = restype,argtypes
    symbols = symbol_provenance(lib,signatures)
    digest = runtime.manifest['artifacts']['library']['sha256']
    require(all(v['path'] == str(runtime.library) and v['sha256'] == digest and v['symbol'] == k
                for k,v in symbols.items()),'Native C API symbol provenance mismatch')
    handle = lib.Highs_create()
    require(handle,'Cannot create HiGHS reference handle')
    try:
        require(lib.Highs_getSizeofHighsInt(handle) == 4,'Native HighsInt must be 32 bits')
        require(lib.Highs_version().decode() == HIGHS_VERSION and lib.Highs_githash().decode() == NATIVE_GITHASH,
                'Native version/commit mismatch')
    finally:
        lib.Highs_destroy(handle)
    mapped_libraries = verify_native_mappings(runtime)
    runtime.verify()
    return dict(passed=True,mapped_libraries=mapped_libraries,source_commit=SOURCE_COMMIT,version=HIGHS_VERSION,highs_int_bytes=4,
                symbols=symbols,model_read_called=False,optimization_or_presolve_called=False,
                effective_options_qualified=False,native_assess_qualified=False,
                runtime_manifest_sha256=runtime.manifest_sha256)


PYTHON_VERSIONS = {'numpy':'2.3.5','scipy':'1.17.0','threadpoolctl':'3.6.0'}


def loaded_python_identities():
    """Bind current distribution files without importing numerical/native modules.

    Installed RECORD digests are checked when present. Call once during binding;
    keep the result as immutable run evidence. Science callers must still call
    verify_loaded_runtime after numerical imports and before admission.
    """
    import base64
    import importlib.metadata
    identities = {}
    for name, version in PYTHON_VERSIONS.items():
        dist = importlib.metadata.distribution(name)
        require(dist.version == version, 'Unsupported '+name+' version: '+dist.version)
        require(dist.files, 'Missing installed RECORD inventory: '+name)
        for entry in dist.files:
            path = Path(dist.locate_file(entry)).resolve(strict=True)
            require(path.is_file(), 'Missing installed distribution file: '+str(path))
            digest = sha256(path)
            if entry.hash:
                require(entry.hash.mode == 'sha256', 'Unsupported RECORD hash: '+str(entry))
                encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b'=').decode()
                require(encoded == entry.hash.value, 'Installed RECORD mismatch: '+str(path))
            if entry.size is not None:
                require(path.stat().st_size == entry.size, 'Installed RECORD size mismatch: '+str(path))
            row = dict(path=str(path),sha256=digest,bytes=path.stat().st_size,distribution=name,version=version)
            require(str(path) not in identities or identities[str(path)]['sha256'] == digest,
                    'Conflicting distribution file: '+str(path))
            identities[str(path)] = row
    # Pin loaded platform DSOs, including the actual allocator used by C API option names.
    for path in mapped_native_paths():
        row = _record(path)
        identities.setdefault(row['path'],dict(row,distribution='platform-native',version=platform.platform()))
    # The interpreter itself is an explicit runtime authority as well.
    python = _record(sys.executable)
    identities[python['path']] = dict(python,distribution='python',version=platform.python_version())
    return [identities[path] for path in sorted(identities)]


def verify_loaded_runtime(identities):
    """Same loaded-module/one-thread BLAS admission as the scientific runner."""
    from threadpoolctl import threadpool_info
    pinned = {item['path']:item['sha256'] for item in identities}
    loaded = {}
    for name,module in list(sys.modules.items()):
        if name.split('.')[0] in ('numpy','scipy','threadpoolctl') and getattr(module,'__file__',None):
            path = str(Path(module.__file__).resolve())
            require(path in pinned and sha256(path) == pinned[path], 'Unpinned loaded numerical module: '+name)
            loaded[path] = pinned[path]
    pools = threadpool_info()
    for pool in pools:
        path = str(Path(pool['filepath']).resolve())
        require(path in pinned and sha256(path) == pinned[path], 'Unpinned loaded numerical DSO')
        require(pool.get('num_threads') == 1, 'Numerical BLAS is not single-threaded')
        loaded[path] = pinned[path]
    return dict(loaded_file_count=len(loaded),files=loaded,threadpools=pools)


def native_assess_fixture(runtime, workdir):
    """Prepare a 1x1 helper test; caller must use its contained process runner.

    This writes fresh synthetic inputs only. It does not execute native code.
    The fixture checks genuine assessment, complete readback and loaded DSO.
    """
    runtime.verify()
    out = Path(workdir).resolve()
    out.mkdir(parents=True,exist_ok=False)
    model, point = out/'model.mps',out/'point.sol'
    model.write_text('NAME tiny_assess\nROWS\n N obj\n G demand\nCOLUMNS\n    x  obj  2\n    x  demand  1\nRHS\n    rhs  demand  1\nBOUNDS\n BV bnd  x\nENDATA\n')
    point.write_text('Model status\nNot Set\n\n# Primal solution values\nFeasible\nObjective 2\n# Columns 1\nx 1\n')
    return dict(command=[str(runtime.native_assess),str(model),str(point),str(out/'native.bin'),str(out/'native.log')],
                model=_record(model),point=_record(point),runtime_manifest_sha256=runtime.manifest_sha256,
                expected_library_sha256=runtime.manifest['artifacts']['library']['sha256'],
                maximum_process_seconds=10.,maximum_output_bytes=65536,optimization_or_presolve_called=False)


def validate_native_assess_fixture(runtime, workdir, fixture):
    """Validate all v3 helper fields after the caller has successfully reaped it."""
    import io
    runtime.verify()
    out = Path(workdir).resolve()
    require(fixture['runtime_manifest_sha256'] == runtime.manifest_sha256,'Helper fixture runtime changed')
    for name in ('model','point'):
        _checked_record(out,fixture[name],name)
    path = out/'native.bin'
    require(0 < path.stat().st_size <= 65536,'Unsafe assessment fixture output size')
    stream = io.BytesIO(path.read_bytes())
    def take(count):
        value = stream.read(count)
        require(len(value) == count,'Truncated native helper fixture output')
        return value
    def unpack(fmt):
        return struct.unpack(fmt,take(struct.calcsize(fmt)))
    def string():
        length, = unpack('<I')
        require(0 < length < 4096,'Unsafe helper string length')
        return take(length).decode()
    require(take(8) == b'HSCONT01','Helper v3 dump magic mismatch')
    dso = Path(string()).resolve(strict=True)
    require(dso == runtime.library and sha256(dso) == fixture['expected_library_sha256'],'Helper loaded wrong DSO')
    require(unpack('<9i') == (1,1,1,1,0,1,1,1,1),'Helper assessment/dimensions mismatch')
    offset,mip_tol,primal_tol,infinity = unpack('<4d')
    require((offset,mip_tol,primal_tol) == (0.,1e-6,1e-7) and infinity == float('inf'),'Helper tolerance metadata mismatch')
    for fmt,expected,label in [('<d',(0.,),'col_lower'),('<d',(1.,),'col_upper'),('<d',(2.,),'col_cost'),
        ('<d',(1.,),'row_lower'),('<d',(float('inf'),),'row_upper'),('<i',(1,),'integrality'),
        ('<2i',(0,1),'a_start'),('<i',(0,),'a_index'),('<d',(1.,),'a_value')]:
        require(unpack(fmt) == expected,'Helper matrix readback mismatch: '+label)
    require(string() == 'x' and string() == 'demand','Helper names mismatch')
    require(unpack('<d') == (1.,) and unpack('<d') == (1.,),'Helper point/activity mismatch')
    require(stream.read() == b'','Trailing helper fixture output')
    return dict(passed=True,helper_source_sha256=HELPER_SOURCE_SHA256,
                helper_sha256=runtime.manifest['artifacts']['native_assess']['sha256'],
                loaded_library=_record(dso),matrix_fields_verified=16,
                dump=_record(path),optimization_or_presolve_called=False)


def mapped_native_paths():
    paths = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/'):
            path = Path(fields[5])
            if '.so' in path.name and path.is_file():
                paths.add(path.resolve())
    return sorted(paths)


def verify_native_mappings(runtime):
    expected = {runtime.library:runtime.manifest['artifacts']['library']['sha256'],
                runtime.extras:runtime.manifest['artifacts']['extras']['sha256']}
    actual = [p for p in mapped_native_paths() if p.name.startswith('libhighs')]
    require(set(actual) == set(expected),'Unexpected/missing mapped HiGHS library or extras DSO')
    require(all(sha256(path) == expected[path] for path in actual),'Mapped HiGHS DSO bytes changed')
    return [_record(path) for path in actual]
