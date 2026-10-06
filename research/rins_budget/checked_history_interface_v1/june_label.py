"""Read-only admission of one reviewed June archive; no solver or physics call."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import math
from pathlib import Path
import time
import numpy as np

from common import HERE, case_binding, checked_member, digest, read_json, require, sha, write_json
from history import Label, _ADMITTED
from current_scuc.core.driver.fractional_separator import source_scope, expected_column_names, point_sha256
from current_scuc.core.driver.primal_and_bound import read_primal

PIN_LIST_SHA256 = 'ee45b622645d52dfcf409879b43aec4cc8893b607916f03dbe03041132578112'


def admit_june(root, *, seconds=60.):
    started = time.monotonic()
    require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 60, 'Fresh validation allowance')
    deadline = started + seconds
    pins_path = HERE / 'june_admission_pins.json'
    require(sha(pins_path) == PIN_LIST_SHA256, 'Admission trust pins changed')
    pins = read_json(pins_path)
    root = Path(root).resolve()
    verified = {}
    for relative, wanted in {**pins['archives'], **pins['members']}.items():
        require(time.monotonic() < deadline, 'New validation deadline expired')
        verified[relative] = checked_member(root, relative, wanted)
    get = lambda relative: read_json(verified[relative])
    endpoint = get('VERIFIED_ENDPOINT.json')
    physical = get('selected/run/candidate/physical/result.json')
    request = get('selected/run/candidate/physical-request.json')
    completion = get('selected/run/candidate/physical/completion.json')
    terminal = get('candidate-result-selected-fields.json')['scalars']
    audit = get('audit-anchor/audit/run01-june-seed1/AUDIT.json')
    require(audit['audit_passed'] is True and audit['scientific_passed'] is True and audit['classification'] == 'PASS', 'Archived independent audit rejected')
    require(completion['complete'] is True and completion['request_sha256'] == sha(verified['selected/run/candidate/physical-request.json'])
            and completion['result_sha256'] == sha(verified['selected/run/candidate/physical/result.json']), 'Physical receipt chain')
    require(terminal['selected_final_call'] == endpoint['point']['selected_final_call'] == 2
            and terminal['final_upper_admitted'] is True and terminal['selected_point_role'] == 'production_quality_endpoint', 'Wrong terminal point')
    require(all(physical[k] is True for k in ('passed', 'upper_bound_eligible', 'numerical_physical_witness',
                                            'literal_row_check_passed', 'direct_dc_check_passed')), 'Full historical physical receipt failed')
    require(physical['physical_dc_lower_bound_certified'] is False and physical['direct_violated_pair_count'] == 0, 'Physical scope changed')
    source_path = verified['source-anchor/input/case1354pegase_2017-06-01.json.gz']
    require(sha(source_path) == request['source_sha256'] == physical['identity']['source_sha256'], 'Source receipt mismatch')
    data = case_binding.read_source(source_path)
    scope = source_scope(data, 36, source_sha256=sha(source_path))
    names = expected_column_names(data, 36, scope)
    require(len(names) == endpoint['point']['original_columns'] == 313776, 'Original column authority')
    authority = request['source_binary_authority']
    binary_names = [f'{kind}_{generator}_{hour}' for generator in data['Generators'] for hour in range(36) for kind in ('u', 'y', 'z')]
    require(authority['names'] == binary_names and authority['ordered_generator_ids'] == list(data['Generators']), 'Source binary order mismatch')
    require(authority['identity_sha256'] == endpoint['point']['source_u_y_z_identity_sha256'], 'Source binary identity mismatch')
    with np.load(verified['selected/run/candidate/mip-02/round-03-original-lift.npz'], allow_pickle=False) as bundle:
        require(bundle.files == ['a0'], 'Unexpected stored point arrays')
        values = bundle['a0'].copy()
    require(values.dtype.str == '<f8' and values.shape == (313776,) and np.isfinite(values).all(), 'Complete original binary64 point required')
    payload = hashlib.sha256(values.tobytes()).hexdigest()
    require(payload == endpoint['point']['binary64_sha256'] == physical['stored_lift_binary64_sha256'], 'Point payload binding')
    parsed = read_primal(verified['selected/run/candidate/physical/original.sol'], names)
    require(parsed is not None and np.array([parsed['values'][name] for name in names], dtype='<f8').tobytes() == values.tobytes(), 'Physical point differs from complete stored lift')
    require(point_sha256(parsed['values']) == endpoint['point']['named_point_sha256'] == physical['matrix_check']['point_sha256'], 'Named point hash mismatch')
    original = get('selected/run/candidate/mip-02/round-03-source-quality.json')
    full = get('selected/run/candidate/mip-02/round-03-full-source-quality.json')
    require(original['passed'] is True and full['passed'] is True and full['zero_radius'] is True
            and full['full_scope_coverage_complete'] is True and full['stored_lift_binary64_sha256'] == payload, 'Original/literal checker evidence')
    require(full['full_scope_identity_sha256'] == physical['full_scope_identity_sha256'] == request['full_scope']['identity_sha256'], 'Full scope identity mismatch')
    for key in ('signed_normal_rows', 'signed_security_rows', 'unsigned_security_pair_hours'):
        require(full[key] == request['full_scope'][key], 'Incomplete outage/hour coverage')
    require(all(0 <= physical['slack_metrics'][k]['positive_sum_MWh'] <= 1e-5
                for k in ('load_shedding', 'reserve_shortfall', 'shared_overflow')), 'Historical quality failed')
    require(physical['checked_upper'] == endpoint['checked_values']['checked_upper'], 'Historical checked cost changed')
    manifest = get('source-anchor/package/current_scuc/SOURCE_MANIFEST.json')['files_sha256']
    require(physical['physical_checker_sha256'] == manifest['core/scuc/check_solution.py']
            and physical['direct_separator_sha256'] == manifest['core/driver/fractional_separator.py'], 'Checker source binding')
    inventory = get('selected/run/candidate/mip-02/master.mps.meta.json')['identity']['source_binary_inventory']
    require([entry['name'] for entry in inventory] == binary_names, 'Binary inventory order')
    selected, u = [], []
    for entry in inventory:
        j = entry['original_column']
        require(type(j) is int and 0 <= j < len(names) and names[j] == entry['name'] and entry['integrality'] == 1, 'Binary point index/name mismatch')
        require(values[j] in (0., 1.) and entry['lower'] <= values[j] <= entry['upper'], 'Exact binary label required; no rounding')
        if entry['name'].startswith('u_'):
            selected.append(entry['name'])
            u.append(int(values[j]))
    require(len(selected) == 9360 and len(set(selected)) == len(selected), 'Complete commitment inventory')
    # Static topology only; no load/renewable or solution data enters compatibility.
    def safe(v):
        if isinstance(v, float) and not math.isfinite(v):
            return '+inf' if v > 0 else '-inf'
        if isinstance(v, dict):
            return {k: safe(w) for k, w in v.items()}
        if isinstance(v, (list, tuple)):
            return [safe(w) for w in v]
        return v
    topology = digest(safe(dict(buses=list(data['Buses']), generators=list(data['Generators']),
                                lines=list(data['Transmission lines'].items()), contingencies=list(data['Contingencies'].items()), hours=36)))
    at = lambda v, t: v[t] if isinstance(v, list) else v
    features = [math.fsum(float(at(bus['Load (MW)'], t)) for bus in data['Buses'].values()) for t in range(36)]
    require(all(math.isfinite(v) for v in features), 'Nonfinite source features')
    # Trusted audit is a conservative observed label-availability bound in 2026.
    # Fresh extraction time is separate; neither timestamp is backdated to 2017.
    observed = dt.datetime.now(dt.timezone.utc).isoformat()
    require(time.monotonic() <= deadline, 'New validation deadline expired')
    record = dict(scope='scuc_checked', case='case1354pegase', start='2017-06-01T00:00:00+00:00',
                  end='2017-06-02T12:00:00+00:00', observed_available_at=audit['audited_at_utc'], fresh_admitted_at=observed,
                  archived_audited_at=audit['audited_at_utc'], feature_spec='total-bus-load-hourly-mw-identity/v1',
                  feature=features, topology=topology, id=digest(dict(archives=pins['archives'], point=payload)),
                  source_sha256=sha(source_path), columns=selected, u=u, evidence_sha256=PIN_LIST_SHA256,
                  data_only=True, historical_checked_cost=physical['checked_upper'],
                  admission_seconds=time.monotonic() - started, original_monotonic_fields_unchanged=True)
    return Label(record, _ADMITTED, digest(record))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recovery-root', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    label = admit_june(a.recovery_root)
    write_json(a.out, label.record)


if __name__ == '__main__':
    main()
