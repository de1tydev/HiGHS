"""Minimal local contracts used by the retained mathematical checkers."""
import json
import math
import os
from pathlib import Path

from . import binding as b
from ._paths import ROOT

ContractError = b.ContractError
sha = b.sha
read_json = b.read
write_json = b.write
verify = b.verify
module = lambda path, name: b.load(name, path)
runtime_manifest = lambda path=None: b.verify_freeze()
HERE = ROOT
GENERATOR = ROOT/'core/scuc/generate.py'
CHECKER = ROOT/'core/scuc/check_solution.py'
EXPORTER = ROOT/'core/canonical_mps_export'

# Importing for pure checks is allowed before runtime configuration. An explicitly
# configured but invalid runtime must fail instead of falling back to placeholders.
_config = b.config() if os.environ.get('PRIMAL_CACHE_CONFIG') else {}
LIBRARY = Path(_config.get('library', 'UNPREPARED/libhighs.so'))
EXTRAS_LIBRARY = Path(_config.get('extras', 'UNPREPARED/libhighs_extras.so'))
BINARY = Path(_config.get('binary', 'UNPREPARED/highs'))
RUNTIME_LIBRARY_PINS = _config.get('runtime_library_pins', {})
TOLERANCE = 1e-5
TARGET = .01
MEMORY_BYTES = 7*1024**3
MIP_SCOPE = 'original_security_master_mip'
LP_SCOPE = 'continuous_security_discovery_only'
FIDELITY_FIELDS = {'num_col', 'num_row', 'num_nz', 'sense', 'offset', 'col_names',
                   'row_names', 'col_lower', 'col_upper', 'col_cost', 'row_lower',
                   'row_upper', 'integrality', 'a_start', 'a_index', 'a_value'}
finite = lambda value: type(value) in (int, float) and math.isfinite(value)


def pairs(raw, scope):
    from .core.driver.pair_codec import PackedPairs, read_pairs
    return read_pairs(raw, scope) if isinstance(raw, dict) else PackedPairs(scope, raw)


def check_lp_integer_difference(original, continuous):
    b.require(set(original) == FIDELITY_FIELDS and set(continuous) == FIDELITY_FIELDS,
              'Incomplete 16-field dictionary')
    for field in FIDELITY_FIELDS-{'integrality'}:
        first, second = original[field], continuous[field]
        if hasattr(first, 'tolist'):
            first = first.tolist()
        if hasattr(second, 'tolist'):
            second = second.tolist()
        b.require(first == second, 'LP changed original ' + field)
    b.require(any(original['integrality']) and not any(continuous['integrality']),
              'LP integrality-only transform failed')
