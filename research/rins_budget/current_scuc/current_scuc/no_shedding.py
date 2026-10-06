"""One checked hard-zero-shedding subset; original source remains the QA authority."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from fractions import Fraction
import hashlib
import json
import math
import numpy as np

DOMAIN = 'hard_zero_shedding_reserve_integer_full_literal_lodf_subset'
TOLERANCE = 1e-5


def require(ok, message):
    if not ok: raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def same(a, b, message):
    a, b = np.asarray(a), np.asarray(b)
    require(a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(), message)


def target_model(original, model, *, production=False):
    """Copy only upper bounds; derive the full exact delta from source column names."""
    e = model.validate_model(original)
    shed = [j for j, n in enumerate(e['col_names']) if n.startswith('shed_')]
    reserve = [j for j, n in enumerate(e['col_names']) if n.startswith('short_')]
    require(all(e['col_lower'][j] == 0. and math.isfinite(e['col_upper'][j])
        and e['col_upper'][j] >= 0. and e['integrality'][j] == 0 for j in shed), 'Unsupported source shedding bounds/type')
    require(all(e['col_lower'][j] == e['col_upper'][j] == 0. and e['integrality'][j] == 0
        for j in reserve), 'Source reserve shortfall is not already fixed zero')
    changed = [j for j in shed if e['col_upper'][j] > 0.]
    if production:
        import current_scuc.heldout as heldout
        heldout.check_hard_zero(len(shed), len(changed), len(shed)-len(changed), len(reserve))
    target = dict(e, col_upper=e['col_upper'].copy())
    target['col_upper'][changed] = 0.
    before, after = model.model_hashes(e), model.model_hashes(target)
    require(all(before[k] == after[k] for k in before if k != 'col_upper'), 'Subset changed a non-upper field')
    delta = [[j, e['col_names'][j], float(e['col_upper'][j]), 0.] for j in changed]
    certificate = dict(schema='hard-zero-shedding-bound-subset/v1', lower_domain=DOMAIN,
        original_model_hashes=before, subset_target_model_hashes=after,
        shed_columns=len(shed), changed_shed_upper_bounds=len(changed), already_zero_shed_columns=len(shed)-len(changed),
        reserve_shortfall_columns=len(reserve), reserve_shortfall_already_fixed_zero=True,
        shed_inventory_sha256=digest([[j,e['col_names'][j]] for j in shed]),
        reserve_inventory_sha256=digest([[j,e['col_names'][j]] for j in reserve]),
        exact_changed_upper_bound_records_sha256=digest(delta),
        transformation='only originally positive shed upper bounds become binary64 +0; all other fields unchanged',
        original_source_is_lift_check_authority=True, shared_overflow_bounds_unchanged=True,
        lower_valid_for_original_soft_optimum=False, lower_valid_for_negligible_shedding_domain=False,
        physical_dc_lower_bound_certified=False)
    if production:
        heldout.check_hard_zero_certificate(certificate)
    certificate['identity_sha256'] = digest(certificate)
    return target, certificate


def install(projected, metadata, original, model):
    target, cert = target_model(original, model, production=metadata['full_scope']['production_scope'])
    retained = np.asarray(metadata['retained_original_columns'], dtype=np.int32)
    require(set(np.flatnonzero(original['col_upper'] != target['col_upper'])).issubset(set(retained)),
        'Subset changed a removed source column')
    for field in ('col_lower','col_upper','col_cost'):
        same(projected[field][:len(retained)], original[field][retained], 'Unchanged source projection before subset '+field)
    current = dict(projected, col_upper=projected['col_upper'].copy())
    current['col_upper'][:len(retained)] = target['col_upper'][retained]
    meta = dict(metadata, hard_zero_subset=cert)
    validate_retained(current, meta, original, model)
    return current, meta


def validate_retained(current, metadata, original, model):
    target, cert = target_model(original, model, production=metadata['full_scope']['production_scope'])
    require(metadata['hard_zero_subset'] == cert, 'Hard-zero subset identity/bound delta changed')
    retained = np.asarray(metadata['retained_original_columns'], dtype=np.int32)
    for field in ('col_lower','col_upper','col_cost'):
        same(current[field][:len(retained)], target[field][retained], 'retained checked subset '+field)
    return cert


def point_check(original, values, certificate, model, *, production=False):
    _, expected = target_model(original, model, production=production)
    require(certificate == expected, 'Point hard-zero target identity changed')
    x = np.asarray(values)
    require(x.dtype == np.float64 and x.shape == (original['num_col'],) and np.isfinite(x).all(), 'Invalid subset point')
    indices = [j for j,n in enumerate(original['col_names']) if n.startswith(('shed_','short_'))]
    maximum = max((abs(float(x[j])) for j in indices), default=0.)
    result = dict(passed=maximum <= TOLERANCE, fixed_columns_checked=len(indices), maximum_absolute_fixed_value=maximum,
        tolerance=TOLERANCE, exactly_zero=all(x[j] == 0. for j in indices), point_modified=False,
        subset_identity_sha256=certificate['identity_sha256'])
    require(result['passed'], 'Hard-zero target fixed-value check failed')
    return result


def slack_quality(original, values):
    x = np.asarray(values)
    require(x.shape == (original['num_col'],) and np.isfinite(x).all(), 'Nonfinite quality point')
    totals = {label: math.fsum(max(0.,float(x[j])) for j,n in enumerate(original['col_names']) if n.startswith(prefix))
        for label,prefix in (('load_shedding','shed_'),('reserve_shortfall','short_'),('shared_overflow','over_'))}
    return dict(passed=all(0. <= v <= TOLERANCE for v in totals.values()), positive_slack_totals_MWh=totals,
        tolerance_MWh=TOLERANCE, signed_cancellation_allowed=False)


def selection_key(point):
    ev = point['evaluation']
    require(ev['target_subset_quality']['passed'] is True and math.isfinite(ev['provisional_upper']), 'Invalid target endpoint')
    return (not ev['negligible_slack_quality']['passed'], ev['provisional_upper'], point['call'])


def stop_eligible(evaluation, span):
    return (evaluation.get('target_subset_quality',{}).get('passed') is True and
        evaluation.get('negligible_slack_quality',{}).get('passed') is True and
        span.get('passed') is True and span.get('qualified') is True)


def excluding_support(batch, metadata, x, prior_batches):
    """Exact binary64 row residual at the current tuple; new eta has baseline zero."""
    state = metadata['activation']
    nret, hours = state['nret'], state['hours']
    eta = {(line,t): nret+2+k*hours+t for k,line in enumerate(state['active']) for t in range(hours)}
    inverse = np.asarray(metadata['original_to_projected'])
    def key(row):
        return digest({k: row[k] for k in ('line','hour','original_indices','coefficients','eta_coefficient','upper')})
    seen = {key(row) for old in prior_batches for row in old['rows']}
    residuals = []
    for row in batch['rows']:
        if key(row) in seen: continue
        cols = [int(inverse[j]) for j in row['original_indices']]
        require(all(0 <= j < nret for j in cols), 'Support retained mapping changed')
        value = sum((Fraction(float(c))*Fraction(float(x[j])) for c,j in zip(row['coefficients'],cols)), Fraction(0))
        slot = eta.get((row['line'],row['hour']))
        if slot is not None: value += Fraction(float(row['eta_coefficient']))*Fraction(float(x[slot]))
        residuals.append(value-Fraction(float(row['upper'])))
    maximum = max([Fraction(0), *residuals])
    return dict(passed=maximum > Fraction(TOLERANCE), new_rows=len(residuals),
        materially_violated_rows=sum(r > Fraction(TOLERANCE) for r in residuals),
        maximum_positive_residual_MW=float(maximum), threshold_MW=TOLERANCE,
        arithmetic='exact rational products/sums of binary64 row and point', new_line_eta_baseline_MW=0.)
