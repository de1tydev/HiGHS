"""Source-derived case assertions for the portable projected candidate.

All source algorithms stay in their frozen modules. This module imports only
stdlib until an explicitly bound current case is requested. No implicit date,
historical input, factor, incumbent, or nonproduction fallback is accepted.
"""
from __future__ import annotations
from collections.abc import Mapping
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

from ._paths import ROOT, source_sha
HERE = ROOT
# Attribution only; runtime library identity is read from this run's manifest.
PROPOSAL_SHA = '0811c3ef9a663ad81fe9c53e9846350f4d4c6a71a8fe20059c5a1e354d93b296'
_loaded = None

def require(ok, message):
    if not ok: raise ValueError(message)

def binding():
    from . import case_binding
    return case_binding

def case():
    global _loaded
    key = (os.environ.get('HELDOUT_CASE_BINDING'), os.environ.get('HELDOUT_CASE_BINDING_SHA256'))
    require(all(key), 'An explicitly bound local case descriptor is required')
    if _loaded is None:
        value = binding().load(*key)
        binding().verify_inputs(value)
        _loaded = (key, value)
    require(key == _loaded[0], 'Case binding changed inside a process')
    require(binding().sha(key[0]) == key[1], 'Current case descriptor bytes changed')
    return _loaded[1]

def runtime_binding():
    from . import binding as runtime
    return runtime

def config_path():
    value = case()
    runtime_binding()
    binding().verify_runtime(value)
    return Path(value['runtime']['config']['path'])

def input_pins():
    value = case()
    cfg = runtime_binding().config()
    return dict(source=value['source']['sha256'], expected=value['model']['expected']['sha256'],
        mps=value['model']['mps']['sha256'], generator=source_sha('primal-cache-replay-v4.1/core/scuc/generate.py'),
        library=binding().sha(cfg['library']))

class LazyPins(Mapping):
    """No active source is opened merely by importing a consumer."""
    def __init__(self, *, suffix=False): self.suffix = suffix
    def _items(self):
        pins = input_pins()
        return {k+'_sha256': pins[k] for k in ('source','expected','mps','generator')} if self.suffix else pins
    def __getitem__(self, key): return self._items()[key]
    def __iter__(self): return iter(self._items())
    def __len__(self): return len(self._items())

def check_inputs(pins, *, data=None, expected=None):
    value = case()
    required = {k+'_sha256': v for k,v in input_pins().items() if k in ('source','expected','mps','generator')}
    require(all(pins.get(k) == v for k,v in required.items()), 'Held-out input identity receipt mismatch')
    require(value['mapping_pairs'] == [], 'Held-out mapping pairs must be explicitly empty')
    if data is not None:
        derived = binding().source_contract(data)
        for field in ('first_start','hard_zero'):
            require(derived[field] == value[field], 'Held-out source-derived '+field+' mismatch')
        require(derived['scope'] == {k:v for k,v in value['scope'].items() if k!='virtual_full_rows'}, 'Held-out source coverage mismatch')
        require(derived['topology'] == {k:v for k,v in value['topology'].items()
            if k not in ('lodf_binary64_C_sha256','minimum_outage_denominator')}, 'Held-out ordered topology mismatch')
        for field in ('source_object_sha256','source_ordered_sha256','source_names_sha256','binary_names_sha256'):
            require(derived[field] == value['provenance'][field], 'Held-out source identity mismatch: '+field)
        if expected is not None:
            require(list(expected['col_names']) == derived['column_names'], 'Held-out complete source column order mismatch')
    if expected is not None: check_shape(expected, 'original')

def check_shape(expected, role):
    wanted = case()['shapes'][role]
    require({k:int(expected[k]) for k in ('num_col','num_row','num_nz')} == wanted, 'Held-out '+role+' shape mismatch')

def check_scope_shape(hours, buses, lines, rated, outages):
    scope = case()['scope']
    require((hours,buses,lines,rated,outages) == tuple(scope[k] for k in
        ('hours','buses','lines','finite_rated_lines','distinct_listed_single_line_outages')), 'Held-out source shape mismatch')

def check_mapping_scope(scope):
    value = case()
    require(scope['normal_signed_rows'] == value['scope']['signed_normal_rows'] and
        scope['seed_signed_rows'] == value['shapes']['mapping_rows'] == 0 and
        scope['retained_soft_rows_checked'] == scope['normal_signed_rows'], 'Held-out exact empty mapping row inventory mismatch')

def check_counts(counts):
    require(counts == case()['scope'], 'Held-out full-scope counts mismatch')

def check_lodf(digest):
    require(digest == case()['topology']['lodf_binary64_C_sha256'], 'Fresh held-out LODF coefficient bits mismatch')

def check_full_descriptor(descriptor):
    value = case()
    require(descriptor['production_scope'] is True, 'Production scope is mandatory')
    require(descriptor['source_object_sha256'] == value['provenance']['source_object_sha256'], 'Held-out source object mismatch')
    for field in ('ordered_bus_ids','ordered_line_ids','ordered_generator_ids','ordered_monitored_indices',
        'ordered_outage_indices','ordered_monitored_ids','ordered_outage_ids','normal_limit_binary64_sha256',
        'emergency_limit_binary64_sha256','normal_finite_mask_sha256','emergency_finite_mask_sha256',
        'lodf_binary64_C_sha256','coverage_by_hour'):
        require(descriptor[field] == value['topology'][field], 'Held-out scope identity mismatch: '+field)
    check_counts(descriptor['counts'])
    check_mapping_scope(descriptor['subset_mapping_scope'])
    require(descriptor['retained_nonnetwork_row_prefix_end'] == value['shapes']['retained_nonnetwork_row_prefix_end'], 'Held-out original network boundary mismatch')

def check_selected(selected, hours):
    fs = case()['first_start']
    wanted = [dict(unit=u['unit'],prefix_end=t,C_hex=u['C_hex'],C_exact=u['C_exact'],nonzeros=t+2)
        for u in fs['units'] for t in range(hours)]
    require(hours == fs['hours'] and selected == wanted, 'Held-out source first-start selection mismatch')

def check_family(family):
    value = case(); fs = value['first_start']
    require(family['logical_first_start_inventory'] == fs, 'Held-out logical first-start inventory mismatch')
    require(family['amendment_proposal_sha256'] == zero_cost().PROPOSAL_SHA and
        family['amendment_manifest_sha256'] == zero_cost().MANIFEST_SHA, 'Zero-cost amendment identity mismatch')
    zero_cost().verify_family_certificate(family['zero_omission_certificate'], value)
    for field in ('hours','units','row_count','nonzeros','implementation_sha256','proof_manifest_sha256','selection_uses_point'):
        require(family[field] == fs[field], 'Held-out complete first-start family mismatch: '+field)
    require(family['source_sha256'] == value['source']['sha256'] and
        family['source_object_sha256'] == value['provenance']['source_object_sha256'], 'Held-out first-start source mismatch')
    require(family['row_start'] == value['shapes']['projected_base']['num_row'], 'Held-out first-start insertion point mismatch')
    require(family['row_count'] == fs['unit_count']*fs['hours'] and
        family['nonzeros'] == fs['unit_count']*fs['hours']*(fs['hours']+3)//2, 'Held-out first-start enumeration relation mismatch')

def check_family_bytes(ceiling):
    require(ceiling == case()['first_start']['additive_mps_bytes'], 'Held-out first-start additive byte reservation mismatch')

def check_hard_zero(shed, changed, already_zero, reserve):
    zero = case()['hard_zero']
    require((shed,changed,already_zero,reserve) == tuple(zero[k] for k in
        ('shed_columns','changed_shed_upper_bounds','already_zero_shed_columns','reserve_shortfall_columns')), 'Held-out hard-zero inventory mismatch')

def check_hard_zero_certificate(certificate):
    require(all(certificate[k] == v for k,v in case()['hard_zero'].items()), 'Held-out hard-zero source bound delta mismatch')

def check_binary_scope(hours, generators, count):
    value = case()
    require(hours == value['case']['hours'] and list(generators) == value['topology']['ordered_generator_ids'] and
        count == value['shapes']['binary_count'], 'Held-out all-source binary inventory mismatch')

def check_carry_shape(retained, columns, hours, lines, binaries):
    value = case()
    require(retained == value['shapes']['retained_columns'] and columns <= 142094 and
        hours == value['case']['hours'] and lines == value['scope']['lines'] and
        binaries == value['shapes']['binary_count'], 'Held-out carry dimensions/binaries mismatch')

def check_coverage(scope):
    require(all(scope[k] == case()['scope'][k] for k in
        ('signed_normal_rows','signed_security_rows','unsigned_security_pair_hours')), 'Held-out full coverage mismatch')

def check_rated(rated):
    require(list(rated) == case()['topology']['ordered_monitored_indices'], 'Held-out ordered monitored inventory mismatch')

def check_physical_scope(hours, expected, data, scope):
    value = case()
    check_inputs({k+'_sha256':v for k,v in input_pins().items()}, data=data, expected=expected)
    require(hours == value['case']['hours'] and list(scope['generators']) == value['topology']['ordered_generator_ids'] and
        scope['outage_line_ids'] == value['topology']['ordered_outage_ids'] and
        len(scope['checked_outage_ids']) == value['scope']['distinct_listed_single_line_outages'] and
        scope['eligible_pair_hours'] == value['scope']['unsigned_security_pair_hours'], 'Held-out physical source scope mismatch')

def check_native_minimum(columns, rows):
    base = case()['shapes']['projected_first_start']
    require(base['num_col'] <= columns and base['num_row'] <= rows, 'Held-out production adaptive minimum dimensions')

def check_manifest(manifest):
    value = case()
    expected = dict(hours=value['case']['hours'], subset_mapping_pairs=[],
        virtual_security_scope='all_source_listed_nonself_outages', original_binary_count=value['shapes']['binary_count'],
        **{k:value['scope'][k] for k in ('signed_normal_rows','signed_security_rows','unsigned_security_pair_hours')})
    require(manifest['scope'] == expected, 'Held-out arm scope differs from common current case')
    require(manifest['case_binding'] == dict(path=os.environ['HELDOUT_CASE_BINDING'],sha256=os.environ['HELDOUT_CASE_BINDING_SHA256']), 'Arm case descriptor identity mismatch')
    for role in ('source','expected','mps'):
        item = value['source'] if role=='source' else value['model'][role]
        require(manifest['inputs'][role] == {k:item[k] for k in ('path','sha256')}, 'Arm current input path/hash mismatch: '+role)
    runtime_binding()
    binding().verify_runtime(value)

def check_payload(payload):
    required = [path for path in HERE.rglob('*.py') if '__pycache__' not in path.parts]
    require(all(path.resolve() in payload for path in required), 'Executable dependency absent from manifest')


def zero_cost():
    from . import zero_cost as zero
    return zero

def certify_omissions(source, original, retained, model, *, production):
    zero = zero_cost()
    inventory = binding().first_start_inventory(source)
    if production:
        value = case()
        require(inventory == value['first_start'], 'Current logical first-start selection mismatch')
        check_shape(retained, 'projected_base')
        certificate = zero.certify_for_case(source, original, retained, value, model)
        zero.verify_family_certificate(certificate, value)
    else:
        # Existing positive-only tiny fixture has no omitted row. Zero fixtures
        # exercise the certifier against explicit independent mock authorities.
        require(inventory['zero_prefix_count'] == 0, 'Zero omission requires independent production model authorities')
        certificate = None
    return inventory, certificate
