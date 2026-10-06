"""Strict complete primal, all-field matrix and original-MIP-only certificate gates."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import math
from decimal import Decimal
from pathlib import Path
import re
from current_scuc.contracts import *

ALLOWANCE_REASON = 'half of 12-significant-digit display unit plus max(1e-5,abs(raw)*1e-11)'
ELIGIBLE_STATUSES = {'Optimal', 'Time limit reached'}

def parse_primal_text(text, expected_names):
    """Never read dual columns; explicit None is distinct from malformed output."""
    if len(expected_names) != len(set(expected_names)): raise ContractError('Duplicate expected name')
    headers = list(re.finditer(r'^# Primal solution values[ \t]*\r?\n', text, re.M))
    if len(headers) != 1: raise ContractError('Missing or duplicate primal section')
    status = re.findall(r'^Model status\s*\n([^\n]+)', text, re.M)
    if len(status) != 1: raise ContractError('Missing/duplicate solution model status')
    section = text[headers[0].end():].split('# Dual solution values', 1)[0]
    if re.fullmatch(r'\s*None\s*', section): return None
    if not re.match(r'Feasible\s*\n', section): raise ContractError('Primal not declared Feasible')
    objectives = re.findall(r'^Objective\s+(\S+)\s*$', section, re.M)
    if len(objectives) != 1: raise ContractError('Missing/duplicate primal objective')
    try: objective = float(objectives[0])
    except ValueError as e: raise ContractError('Malformed objective') from e
    if not math.isfinite(objective): raise ContractError('Nonfinite objective')
    blocks = list(re.finditer(r'^# Columns (\d+)[ \t]*\r?\n', section, re.M))
    if len(blocks) != 1 or int(blocks[0][1]) != len(expected_names):
        raise ContractError('Missing/duplicate/wrong-count primal columns')
    values = {}
    for raw in section[blocks[0].end():].splitlines(keepends=True):
        if raw.startswith('#'): break
        if not raw.strip(): continue
        if not raw.endswith('\n'): raise ContractError('Unterminated primal tail')
        words = raw.split()
        if len(words) != 2 or words[0] in values: raise ContractError('Malformed/duplicate primal column')
        try: value = float(words[1])
        except ValueError as e: raise ContractError('Malformed column value') from e
        if not math.isfinite(value): raise ContractError('Nonfinite primal value')
        values[words[0]] = value
    if set(values) != set(expected_names): raise ContractError('Missing/extra current column names')
    return {'values': values, 'printed_objective': objective, 'status': status[0].strip()}

def read_primal(path, expected_names):
    return parse_primal_text(Path(path).read_text(), expected_names)

def unpack_expected(raw):
    if set(raw) != FIDELITY_FIELDS: raise ContractError('Incomplete expected model dictionary')
    result = dict(raw)
    for field in ('col_lower', 'col_upper', 'row_lower', 'row_upper'):
        result[field] = [math.inf if v == '+inf' else -math.inf if v == '-inf' else v for v in raw[field]]
    return result

def matrix_check(expected, values, kind, identity, *, tolerance=TOLERANCE):
    """Audit intended source CSC, bound to exact API-verified current MPS bytes."""
    if kind not in {'lp', 'mip'} or set(expected) != FIDELITY_FIELDS: raise ContractError('Unknown matrix scope')
    names = expected['col_names']; n = expected['num_col']; m = expected['num_row']
    if len(names) != n or len(set(names)) != n or set(values) != set(names):
        raise ContractError('Matrix exact column-name mismatch')
    integrality = expected['integrality']
    if (kind == 'lp' and any(integrality)) or (kind == 'mip' and not any(integrality)):
        raise ContractError('Current integrality declaration mismatch')
    if expected['sense'] != 1 or expected['offset'] != 0: raise ContractError('Altered objective')
    maxima = {'row': 0., 'lower_bound': 0., 'upper_bound': 0., 'integrality': 0.}
    violations = {}; lhs = [0.] * m; cost_terms = []
    def error(category, value):
        if not math.isfinite(value): raise ContractError('Nonfinite residual: ' + category)
        maxima[category] = max(maxima[category], value, 0.)
        if value > tolerance: violations[category] = violations.get(category, 0) + 1
    for j, name in enumerate(names):
        v = values[name]
        if not finite(v): raise ContractError('Nonfinite matrix point')
        lo, up = expected['col_lower'][j], expected['col_upper'][j]
        error('lower_bound', lo-v if math.isfinite(lo) else 0.)
        error('upper_bound', v-up if math.isfinite(up) else 0.)
        if integrality[j]: error('integrality', abs(v-round(v)))
        cost_terms.append(expected['col_cost'][j] * v)
        for z in range(expected['a_start'][j], expected['a_start'][j+1]):
            lhs[expected['a_index'][z]] += expected['a_value'][z] * v
    for i, value in enumerate(lhs):
        lo, up = expected['row_lower'][i], expected['row_upper'][i]
        if not math.isfinite(value): raise ContractError('Nonfinite row activity')
        error('row', max(lo-value if math.isfinite(lo) else 0., value-up if math.isfinite(up) else 0.))
    objective = math.fsum(cost_terms)
    if not math.isfinite(objective): raise ContractError('Nonfinite linear objective')
    from current_scuc.core.driver.fractional_separator import point_sha256
    return dict(passed=not violations, exact_column_names=True,
                integrality_scope='continuous' if kind == 'lp' else 'original_integer',
                linear_objective=objective, point_sha256=point_sha256(values), tolerance=tolerance,
                violations_by_category=violations, max_violation_by_category=maxima,
                **{k: identity[k] for k in ('model_sha256','expected_sha256','source_sha256',
                                           'solution_sha256','pair_manifest_sha256')})

def objective_consistent(a, b):
    return finite(a) and finite(b) and abs(a-b) <= max(TOLERANCE, max(abs(a),abs(b))*1e-9)

def definition_diagnostics(text):
    subject = r'(?:matrix|coefficient|bound|column|row|objective|integral|integer|RHS|MPS|model|definition)'
    problem = r'(?:warn(?:ing)?|error|ignor(?:e|ed|ing)|drop(?:ped|ping)?|duplicat(?:e|ed)|missing|undefined|unknown|not found)'
    number = r'([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)'
    metrics = (r'[ \t]*P-D objective error[ \t]*:[ \t]*'+number+r'[ \t]*',
               r'[ \t]*'+number+r'[ \t]*/[ \t]*'+number+r'[ \t]+P-D objective error[ \t]*\(tolerance[ \t]*=[ \t]*'+number+r'\)[ \t]*')
    result = []
    for line in text.splitlines():
        metric = next((m for pattern in metrics if (m:=re.fullmatch(pattern,line))), None)
        if metric and all(math.isfinite(float(v)) for v in metric.groups()): continue
        if re.search(subject,line,re.I) and re.search(problem,line,re.I): result.append(line)
    return result

def allowance(raw, token=None):
    token = str(raw) if token is None else token
    return (float(Decimal(10) ** (Decimal(token).adjusted()-11))/2 if raw else 0.) + max(1e-5,abs(raw)*1e-11)

def solver_report(log, measurement, kind, model, library, *, identities_valid):
    """Final top-level exact-model report only; LP never exports a certificate bound."""
    diagnostics = definition_diagnostics(log)
    loaded = re.findall(r'calling init:\s*(\S*libhighs\.so\S*)', log)
    extras = re.findall(r'calling init:\s*(\S*libhighs_extras\.so\S*)', log)
    library_hashes={name:sha(name) for name in RUNTIME_LIBRARY_PINS}
    loader_valid = (bool(loaded) and bool(extras) and Path(library).resolve()==LIBRARY.resolve()
                    and all(Path(p).resolve() == LIBRARY.resolve() for p in loaded)
                    and all(Path(p).resolve() == EXTRAS_LIBRARY.resolve() for p in extras)
                    and library_hashes==RUNTIME_LIBRARY_PINS)
    clean = measurement.get('returncode') == 0 and not measurement.get('hard_watchdog_killed') and not measurement.get('interrupted')
    result = {'scope': MIP_SCOPE if kind == 'mip' else LP_SCOPE,
              'model_definition_diagnostics': diagnostics, 'loaded_library_paths': loaded,
              'loaded_extras_library_paths': extras, 'verified_library_sha256':library_hashes,
              'loaded_library_identity_valid': loader_valid, 'identities_valid': identities_valid,
              'clean_return': clean, 'upper_bound_eligible': False, 'bound_status_valid': False,
              'certificate_bound_eligible': False, 'global_lower': None}
    if kind == 'lp':
        statuses = re.findall(r'^Model status\s*:\s*(.+)$', log, re.M)
        result.update(status=statuses[0].strip() if len(statuses)==1 else None,
                      parent_report_identity_valid=True, printed_lower=None)
        result['usable_status'] = clean and loader_valid and identities_valid and not diagnostics and result['status'] in ELIGIBLE_STATUSES
        return result
    segments = re.split(r'(?m)^Solving report[ \t]*$', log)
    parent = segments[-1] if len(segments)>1 else ''
    def unique(label):
        vals = re.findall(r'^  '+re.escape(label)+r'[ \t]+(.+)$', parent, re.M)
        return vals[0].strip() if len(vals)==1 else None
    status = unique('Status'); model_identity = unique('Model') == Path(model).stem
    raw_token = unique('Dual bound')
    # Dual bound is one token; Timing may include annotations, and is never budget debit.
    try: lower = float(raw_token) if raw_token and len(raw_token.split())==1 else None
    except ValueError: lower = None
    if lower is not None and not math.isfinite(lower): lower = None
    valid = clean and loader_valid and identities_valid and not diagnostics and model_identity and status in ELIGIBLE_STATUSES and lower is not None
    pad = allowance(lower,raw_token) if lower is not None else None
    result.update(status=status, parent_report_identity_valid=model_identity, raw_lower_token=raw_token,
                  printed_lower=lower, lower_rounding_allowance=pad, lower_rounding_allowance_reason=ALLOWANCE_REASON,
                  global_lower=lower-pad if valid else None, bound_status_valid=valid,
                  certificate_bound_eligible=valid, usable_status=clean and status in ELIGIBLE_STATUSES)
    return result

def certificate(upper, bounds, ledger):
    def fail(reason): return dict(valid=False, complete=False, reason=reason, gap=None)
    if not finite(upper): return fail('No source-and-matrix checked integer upper bound')
    eligible = [b for b in bounds if b.get('scope') == MIP_SCOPE and b.get('bound_status_valid') is True]
    if not eligible: return fail('No eligible original integer master lower bound')
    for b in eligible:
        identity=b.get('master_identity',{})
        if identity.get('kind')!='mip' or identity.get('objective_scope')!='unchanged_original_source' or not identity.get('model_path') or not identity.get('stage_directory'):
            return fail('Missing original-master identity')
        for key in ('source_sha256','model_sha256','expected_sha256','pair_manifest_sha256','api_report_sha256',
                    'options_sha256','executable_sha256','generator_sha256','checker_sha256','runtime_manifest_sha256'):
            if not re.fullmatch(r'[0-9a-f]{64}',identity.get(key,'')): return fail('Incomplete original-master hashes')
        raw, lower, pad = b.get('printed_lower'), b.get('global_lower'), b.get('lower_rounding_allowance')
        if not all(finite(v) for v in (raw,lower,pad)) or pad<0 or pad != allowance(raw,b.get('raw_lower_token')) or lower != raw-pad:
            return fail('Invalid or widened lower-bound allowance')
        if (b.get('status') not in ELIGIBLE_STATUSES or not all(b.get(k) is True for k in
            ('clean_return','loaded_library_identity_valid','identities_valid','parent_report_identity_valid','certificate_bound_eligible'))
            or b.get('model_definition_diagnostics') != []): return fail('Invalid bound provenance')
        if lower>upper: return fail('Adjusted lower exceeds checked upper; negative gap is not clipped')
    if len({b['master_identity']['source_sha256'] for b in eligible})!=1:
        return fail('Mixed-source original-master bounds')
    chosen = max(eligible,key=lambda b:b['global_lower']); lower = chosen['global_lower']
    gap = (upper-lower)/max(abs(upper),1e-10)
    if not math.isfinite(gap): return fail('Nonfinite certificate gap')
    complete = gap<=TARGET and ledger['in_budget'] and ledger['lp_policy_valid']
    return dict(valid=True, complete=complete, reason='checked source/matrix integer primal and original-master numerical bound',
                upper=upper, lower=lower, gap=gap, target_met=gap<=TARGET, lower_provenance=chosen,
                budget_valid=ledger['in_budget'], lp_policy_valid=ledger['lp_policy_valid'])
