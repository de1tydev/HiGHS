"""Pinned configuration readback on a separate, empty reference handle.

Import and record validation are pure Python: only probe() loads native code.
This is never evidence from the live solving handle. No model is read and no
solve or presolve API is bound. Native execution remains the caller's decision.
"""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import hashlib
import json
import math
from pathlib import Path
import re
import struct


SOURCE_COMMIT = 'd547a3ad8af5399651187fb0e133cf0e42615b82'
NATIVE_GITHASH = 'd547a3ad8a'
HIGHS_VERSION = '1.15.1'
SCHEMA = 'fuel-projection-configuration-readback-v1'
REFERENCE_SCALING = {
    'simplex_scale_strategy': 2, 'user_bound_scale': 0,
    'user_objective_scale': 0, 'cost_scale_factor': 0,
    'allowed_matrix_scale_factor': 20, 'allowed_cost_scale_factor': 0,
}
TOLERANCES = {
    'primal_feasibility_tolerance': 1e-7,
    'mip_feasibility_tolerance': 1e-6,
    'kkt_tolerance': 1e-7,
}
# Exact v4.1 adapter.policy.options(PROOF), retained without importing binding.
PROOF_OPTIONS = (
    'threads = 2\nparallel = off\npresolve = on\n'
    'write_solution_to_file = true\nwrite_solution_style = 0\n'
    'log_dev_level = 1\nhighs_analysis_level = 128\n'
    'mip_rel_gap = 0.01\nmip_improving_solution_save = false\n'
    'mip_lp_solver = choose\nmip_ipm_solver = choose\n'
)
SYMBOLS = (
    'Highs_create', 'Highs_destroy', 'Highs_getSizeofHighsInt',
    'Highs_version', 'Highs_githash', 'Highs_readOptions',
    'Highs_setBoolOptionValue', 'Highs_setIntOptionValue',
    'Highs_setDoubleOptionValue', 'Highs_getOptionType',
    'Highs_getIntOptionValue', 'Highs_getDoubleOptionValue',
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(path):
    digest = hashlib.sha256()
    try:
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError('Unreadable artifact: ' + str(path)) from exc
    return digest.hexdigest()


def _equal(actual, expected):
    """Typed recursive equality; distinguish bool/int and signed floating zero."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is float:
        return math.isfinite(actual) and struct.pack('>d', actual) == struct.pack('>d', expected)
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(_equal(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def options_text():
    """The only supported proof option bytes; all numerical policy is explicit."""
    return (PROOF_OPTIONS +
            ''.join(name + ' = ' + format(value, '.17g') + '\n' for name, value in TOLERANCES.items()) +
            ''.join(name + ' = ' + str(value) + '\n' for name, value in REFERENCE_SCALING.items()))


def _option_map():
    return {name: dict(type=kind, requested=value, actual=value, passed=True)
            for kind, values in (('Double', TOLERANCES), ('Int', REFERENCE_SCALING))
            for name, value in values.items()}


def _path(value, label):
    _require(isinstance(value, (str, Path)) and bool(str(value)), 'Missing ' + label)
    path = Path(value)
    _require(path.is_absolute() and '\x00' not in str(path), 'Absolute ' + label + ' required')
    return path


def _runtime(cfg):
    _require(isinstance(cfg, dict), 'Missing pinned configuration')
    _require(cfg.get('pristine_source_commit') == SOURCE_COMMIT, 'Pinned source commit mismatch')
    pins, library_pins = cfg.get('runtime_pins'), cfg.get('runtime_library_pins')
    _require(isinstance(pins, dict) and isinstance(library_pins, dict), 'Missing runtime pins')
    binary = _path(cfg.get('binary'), 'executable')
    library = _path(cfg.get('library'), 'library')
    header = runtime_path('pristine-build/HConfig.h')
    expected = ((binary, runtime_sha('binary')), (library, runtime_sha('library')), (header, runtime_sha('hconfig')))
    for path, digest in expected:
        _require(pins.get(str(path)) == digest and _sha(path) == digest, 'Pinned runtime identity mismatch: ' + str(path))
    _require(library_pins.get(str(library)) == runtime_sha('library'), 'Missing pinned reference DSO')
    # Preserve and verify every library alias and extras pin supplied by the
    # enclosing driver, without interpreting unrelated Python runtime pins.
    _require(bool(library_pins), 'Empty runtime library pins')
    for path, digest in library_pins.items():
        _require(isinstance(path, str) and Path(path).is_absolute() and
                 isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest) is not None and
                 pins.get(path) == digest and _sha(path) == digest, 'Runtime DSO pin mismatch: ' + str(path))
    return dict(
        executable_path=str(binary.resolve()), executable_sha256=runtime_sha('binary'),
        library_path=str(library.resolve()), library_sha256=runtime_sha('library'),
        source_commit=SOURCE_COMMIT, native_githash=NATIVE_GITHASH,
        highs_version=HIGHS_VERSION, highs_int_bytes=4,
        source_build_header_path=str(header.resolve()), source_build_header_sha256=runtime_sha('hconfig'),
        runtime_library_pins=dict(library_pins),
    )


def validate_invocation(options_path, command, cfg, model, solution, native_limit):
    """Reject every unsupported option/CLI override before any native load."""
    _require(type(native_limit) in (int, float), 'Native limit must be finite and positive')
    try:
        _require(math.isfinite(native_limit) and native_limit > 0, 'Native limit must be finite and positive')
    except OverflowError as exc:
        raise ValueError('Native limit must be finite and positive') from exc
    options_path, model, solution = (_path(value, label) for value, label in
                                    ((options_path, 'options path'), (model, 'model path'), (solution, 'solution path')))
    _require(type(command) is list and all(type(item) is str for item in command), 'CLI argv must be a list of strings')
    runtime = _runtime(cfg)
    expected = [str(cfg['binary']), str(model), '--options_file', str(options_path),
                '--time_limit', format(native_limit, '.17g'), '--random_seed', '0', '--solution_file', str(solution)]
    _require(command == expected, 'Unsupported or conflicting CLI argv')
    try:
        contents = options_path.read_bytes()
    except OSError as exc:
        raise ValueError('Cannot read exact option bytes') from exc
    _require(contents == options_text().encode('utf-8'), 'Unsupported or conflicting option bytes')
    return dict(
        options_path=str(options_path), options_sha256=hashlib.sha256(contents).hexdigest(),
        command=list(command), model_path=str(model), model_sha256=_sha(model),
        solution_path=str(solution), native_limit_seconds=float(native_limit),
        configured_binary=str(cfg['binary']), configured_library=str(cfg['library']),
        option_probe_source_sha256=_sha(__file__), **runtime,
    )


def _native_readback(library_path, options_path):
    """Public ABI calls only. Kept isolated so source-only checks need no ctypes."""
    import ctypes as C
    I, D, P = C.c_int32, C.c_double, C.c_void_p
    signatures = {
        'Highs_create': (P, []), 'Highs_destroy': (None, [P]),
        'Highs_getSizeofHighsInt': (I, [P]), 'Highs_version': (C.c_char_p, []),
        'Highs_githash': (C.c_char_p, []), 'Highs_readOptions': (I, [P, C.c_char_p]),
        'Highs_setBoolOptionValue': (I, [P, C.c_char_p, I]),
        'Highs_setIntOptionValue': (I, [P, C.c_char_p, I]),
        'Highs_setDoubleOptionValue': (I, [P, C.c_char_p, D]),
        'Highs_getOptionType': (I, [P, C.c_char_p, C.POINTER(I)]),
        'Highs_getIntOptionValue': (I, [P, C.c_char_p, C.POINTER(I)]),
        'Highs_getDoubleOptionValue': (I, [P, C.c_char_p, C.POINTER(D)]),
    }
    try:
        lib = C.CDLL(library_path)
        for name, (restype, argtypes) in signatures.items():
            function = getattr(lib, name)
            function.restype, function.argtypes = restype, argtypes
        # Same dladdr method as frozen canonical_mps_export/readback.py;
        # locally isolated to avoid that module's NumPy/exporter imports.
        class DlInfo(C.Structure):
            _fields_ = [('filename', C.c_char_p), ('base', P), ('symbol', C.c_char_p), ('address', P)]
        dladdr = C.CDLL(None).dladdr
        dladdr.restype, dladdr.argtypes = C.c_int, [P, C.POINTER(DlInfo)]
        provenance = {}
        for name in SYMBOLS:
            info = DlInfo()
            _require(dladdr(C.cast(getattr(lib, name), P), C.byref(info)) != 0 and bool(info.filename),
                     'Cannot establish C API symbol provenance: ' + name)
            path = Path(info.filename.decode()).resolve()
            provenance[name] = dict(path=str(path), sha256=_sha(path),
                                    symbol=info.symbol.decode() if info.symbol else None)
        _validate_symbols(provenance, library_path)
        handle = lib.Highs_create()
        _require(bool(handle), 'Reference Highs_create failed')
        try:
            _require(lib.Highs_getSizeofHighsInt(handle) == 4, 'Reference HighsInt ABI mismatch')
            _require(lib.Highs_githash().decode() == NATIVE_GITHASH, 'Reference source commit mismatch')
            _require(lib.Highs_version().decode() == HIGHS_VERSION, 'Reference version mismatch')
            _require(lib.Highs_setBoolOptionValue(handle, b'output_flag', 0) == 0, 'Cannot quiet reference handle')
            # Exercise exact typed setters before parsing the exact CLI file.
            # Reading it afterward must preserve every requested numerical value.
            for name, item in _option_map().items():
                kind = item['type']
                _require(getattr(lib, 'Highs_set' + kind + 'OptionValue')(handle, name.encode(), item['requested']) == 0,
                         'Reference option set failed: ' + name)
            _require(lib.Highs_readOptions(handle, str(options_path).encode()) == 0, 'Reference options parser failed')
            actual = {}
            for name, item in _option_map().items():
                kind, option_type = item['type'], I()
                _require(lib.Highs_getOptionType(handle, name.encode(), C.byref(option_type)) == 0 and
                         option_type.value == (2 if kind == 'Double' else 1), 'Reference option type mismatch: ' + name)
                value = D() if kind == 'Double' else I()
                _require(getattr(lib, 'Highs_get' + kind + 'OptionValue')(handle, name.encode(), C.byref(value)) == 0,
                         'Reference option readback failed: ' + name)
                _require(_equal(value.value, item['requested']), 'Reference option value mismatch: ' + name)
                actual[name] = dict(item, actual=value.value)
            return dict(options=actual, loaded_symbol_provenance=provenance)
        finally:
            lib.Highs_destroy(handle)
    except (OSError, AttributeError, UnicodeError, TypeError) as exc:
        raise ValueError('Reference C API readback failed') from exc


def _validate_symbols(provenance, library_path):
    _require(type(provenance) is dict and set(provenance) == set(SYMBOLS), 'Incomplete C API provenance map')
    for name, item in provenance.items():
        _require(type(item) is dict and set(item) == {'path', 'sha256', 'symbol'} and
                 item['path'] == library_path and item['sha256'] == runtime_sha('library') and
                 item['symbol'] == name, 'Pinned C API symbol provenance mismatch: ' + name)


def _labels():
    return dict(schema=SCHEMA, passed=True, evidence_kind='configuration_readback',
                readback_scope='Exact proof options file parsed on a separate reference handle; typed getters verify LP/MIP/KKT tolerances and six scaling options',
                same_live_solving_handle=False, live_native_readback_verified=False,
                optimization_or_presolve_called=False, model_read_called=False)


def probe(options_path, command, cfg, model, solution, native_limit):
    """Read configuration on a separate pinned DSO handle; never solve or read a model."""
    before = validate_invocation(options_path, command, cfg, model, solution, native_limit)
    native = _native_readback(before['library_path'], options_path)
    record = dict(before, **_labels(), **native)
    # Rehash all bound files after the native calls as well as before them.
    validate_record(record, options_path, command, cfg, model, solution, native_limit)
    return record


def validate_record(record, options_path, command, cfg, model, solution, native_limit):
    """Pure record/artifact validation; does not import or call any native API."""
    expected = dict(validate_invocation(options_path, command, cfg, model, solution, native_limit),
                    **_labels(), options=_option_map())
    _require(type(record) is dict and set(record) == set(expected) | {'loaded_symbol_provenance'}, 'Incomplete configuration record')
    for name, value in expected.items():
        _require(_equal(record.get(name), value), 'Configuration record mismatch: ' + name)
    _validate_symbols(record['loaded_symbol_provenance'], expected['library_path'])
    return record


def _read_record(path):
    def unique(items):
        result = {}
        for name, value in items:
            _require(name not in result, 'Duplicate configuration record key')
            result[name] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite configuration record')
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=reject)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Cannot read saved configuration record') from exc


def native_options(record, record_path):
    """Translate persisted, revalidated evidence to the numerical helper contract."""
    evidence_sha256 = _sha(record_path)
    _require(_equal(_read_record(record_path), record), 'Saved configuration record differs')
    _require(type(record) is dict, 'Missing configuration record')
    required = ('configured_binary', 'configured_library', 'runtime_library_pins', 'source_build_header_path',
                'options_path', 'command', 'model_path', 'solution_path', 'native_limit_seconds')
    _require(all(name in record for name in required), 'Incomplete configuration record')
    _require(type(record['runtime_library_pins']) is dict, 'Missing runtime library pins')
    pins = dict(record['runtime_library_pins'])
    pins.update({record['configured_binary']: runtime_sha('binary'),
                 record['configured_library']: runtime_sha('library'),
                 record['source_build_header_path']: runtime_sha('hconfig')})
    cfg = dict(binary=record['configured_binary'], library=record['configured_library'],
               runtime_pins=pins, runtime_library_pins=record['runtime_library_pins'],
               pristine_source_commit=SOURCE_COMMIT)
    validate_record(record, record['options_path'], record['command'], cfg,
                    record['model_path'], record['solution_path'], record['native_limit_seconds'])
    _require(_sha(record_path) == evidence_sha256, 'Saved configuration record changed during validation')
    return dict(evidence_kind='pinned_reference', evidence_sha256=evidence_sha256,
                **TOLERANCES, scaling_options=dict(REFERENCE_SCALING),
                adapter_evidence=dict(kind='configuration_readback', record_path=str(Path(record_path).resolve()),
                                      options_sha256=record['options_sha256'], command=list(record['command']),
                                      library_sha256=runtime_sha('library'), executable_sha256=runtime_sha('binary'),
                                      source_commit=SOURCE_COMMIT, highs_int_bytes=4),
                same_live_solving_handle=False, live_native_readback_verified=False)
