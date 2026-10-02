"""Pure cold-screening contracts. Importing this module never runs numerical work."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
from portable_runtime import bindings as _bindings, validate_manifest as _validate_manifest
_BINDINGS = _bindings(HERE)
_WORK = Path(_BINDINGS['work']) if _BINDINGS else HERE.parent / 'UNPREPARED'
HIGHS = HERE.parent / 'helpers'
BENCH = HERE.parent / 'scuc'
GENERATOR = BENCH / 'generate.py'
CHECKER = BENCH / 'check_solution.py'
EXPORTER = HERE.parent / 'canonical_mps_export'
LIBRARY = Path(_BINDINGS['library']) if _BINDINGS else _WORK / 'lib/libhighs.so'
EXTRAS_LIBRARY = Path(_BINDINGS['extras']) if _BINDINGS else _WORK / 'lib/libhighs_extras.so'
BINARY = Path(_BINDINGS['binary']) if _BINDINGS else _WORK / 'bin/highs'
RUNTIME_LIBRARY_PINS = dict(_BINDINGS['runtime_library_pins']) if _BINDINGS else {}
RUNTIME_PINS = dict(_BINDINGS['runtime_pins']) if _BINDINGS else {}
DATA_ROOT = Path(_BINDINGS['data']) if _BINDINGS else _WORK / 'data'
SEPARATOR_PATHS = {'A': HERE/'fractional_separator.py', 'B': HERE.parent/'lp_security_separator_optimized/fractional_separator.py'}
SEPARATOR_PATHS['C'] = SEPARATOR_PATHS['B']
SEPARATOR_SHA256 = {'A': '715a29f2f8fdc89b69dd5851a5c398da5d6254a958b67f6becaea224059393b2',
                    'B': '6428ccf878e624498e573d5d830057e90b4865b2ed6e01a78e3944d2ff96287c'}
SEPARATOR_SHA256['C'] = SEPARATOR_SHA256['B']
TARGET_SHA256 = '42d2acf8a9adf569686977e38547f3ee4c6c2b16c036ec54c39492c30baee4a4'
REQUIRED_LOCAL = ('contracts.py', 'policy.py', 'stage_child.py', 'cold_screen_pair.py', 'model_stage.py',
                  'primal_and_bound.py', 'credit_events.py', 'fractional_separator.py', 'tiny_triangle.json',
                  'CAMPAIGN_PLAN.json', 'PROTOCOL.md', 'SOURCE_EXPOSURE.json', 'portable_runtime.py', 'pair_codec.py', 'witness_store.py', 'resource_guard.py')
HOURS, TOLERANCE, TARGET = 36, 1e-5, .01
SOLVER_BUDGET, LP_CAP, LP_CALL_CAP, LP_CALLS = 600., 30., 10., 3
MEMORY_BYTES, AUX_WATCHDOG, MIP_GRACE = 7 * 1024**3, 600., 60.
MIP_SCOPE = 'original_security_master_mip'
LP_SCOPE = 'continuous_security_discovery_only'
FIDELITY_FIELDS = {'num_col', 'num_row', 'num_nz', 'sense', 'offset', 'col_names', 'row_names',
                   'col_lower', 'col_upper', 'col_cost', 'row_lower', 'row_upper',
                   'integrality', 'a_start', 'a_index', 'a_value'}

class ContractError(ValueError):
    pass

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def read_json(path):
    def reject(v): raise ContractError('Nonfinite JSON: ' + v)
    def unique(items):
        result = {}
        for key, value in items:
            if key in result: raise ContractError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject, object_pairs_hook=unique)

def write_json(path, value, *, fresh=False):
    path = Path(path)
    if fresh and path.exists(): raise ContractError('Refusing stale artifact: ' + str(path))
    encoded = json.dumps(value, indent=2, allow_nan=False) + '\n'
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x') as stream:
        stream.write(encoded)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    temporary.replace(path)

def verify(pins):
    for name, digest in pins.items():
        if sha(name) != digest: raise ContractError('Pinned artifact changed: ' + name)

def module(path, name):
    path = Path(path).resolve()
    existing = sys.modules.get(name)
    if existing is not None:
        if Path(existing.__file__).resolve() != path: raise ContractError('Module path collision: ' + name)
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result

def runtime_manifest(path=None):
    try:
        return _validate_manifest(HERE, path)
    except (ValueError, OSError, KeyError) as exc:
        raise ContractError(str(exc)) from exc

def pairs(raw, scope):
    from pair_codec import PackedPairs, read_pairs
    try:
        if isinstance(raw, dict): return read_pairs(raw, scope)
        return PackedPairs(scope, raw)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)

class Budget:
    def __init__(self, total=SOLVER_BUDGET):
        if not finite(total) or not 0 < total <= SOLVER_BUDGET: raise ContractError('Invalid total budget')
        self.total, self.spent, self.lp_spent, self.lp_calls = float(total), 0., 0., 0
        self.lp_policy_valid = True
        self.calls = []

    def allocation(self, kind):
        remaining = max(0., self.total - self.spent)
        if kind == 'mip': return remaining
        if kind != 'lp': raise ContractError('Unknown solver call kind')
        return 0. if self.lp_calls >= LP_CALLS else max(0., min(LP_CALL_CAP, LP_CAP-self.lp_spent, remaining))

    def debit(self, kind, allocation, measurement):
        wall = measurement.get('process_wall_seconds')
        if not finite(wall) or wall < 0 or not finite(allocation) or allocation <= 0:
            raise ContractError('Missing/nonfinite solver process debit')
        if allocation != self.allocation(kind): raise ContractError('Allocation differs from actual remaining budget')
        self.spent += wall
        if kind == 'lp':
            self.lp_calls += 1
            self.lp_spent += wall
            if wall > allocation or self.lp_spent > LP_CAP: self.lp_policy_valid = False
        self.calls.append({'kind': kind, 'allocation': allocation, 'actual': wall,
                           'overrun': max(0., wall-allocation)})

    def record(self):
        return dict(total=self.total, solver_process_wall_seconds=self.spent,
                    lp_process_wall_seconds=self.lp_spent, lp_calls=self.lp_calls,
                    remaining=max(0., self.total-self.spent), lp_policy_valid=self.lp_policy_valid,
                    in_budget=self.spent <= self.total, calls=self.calls)

def check_lp_integer_difference(original, continuous):
    if set(original) != FIDELITY_FIELDS or set(continuous) != FIDELITY_FIELDS:
        raise ContractError('Incomplete intended dictionary')
    for field in FIDELITY_FIELDS - {'integrality'}:
        a, b = original[field], continuous[field]
        if hasattr(a, 'tolist'): a = a.tolist()
        if hasattr(b, 'tolist'): b = b.tolist()
        if a != b: raise ContractError('LP changed original field: ' + field)
    if not any(original['integrality']) or any(continuous['integrality']):
        raise ContractError('LP integrality-only transform failed')

def source_case(case_date):
    plan=read_json(HERE/'CAMPAIGN_PLAN.json')
    if case_date not in plan.get('cases',{}):raise ContractError('Case outside reviewed scope')
    return Path(plan['cases'][case_date])
