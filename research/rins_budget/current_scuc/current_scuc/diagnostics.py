"""Pinned solve-advice shim and exact-version numerical endpoint admission."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import hashlib
import math
from pathlib import Path
import re
from current_scuc.common import ROOT, require, finite, helpers
from current_scuc.options import DISCOVERY, PROOF_ROLE, ROLES

ADVISORY_SOURCE_SHA = '62aeb110a4dcbb26f6e73932fba3b924c546ee5902520f0e1fa3cb42decca0d1'
STATUS_SOURCE_PINS = {
    'pristine-source/highs/lp_data/HighsSolve.cpp': ADVISORY_SOURCE_SHA,
    'pristine-source/highs/lp_data/HighsModelUtils.cpp': '584f18dee538ffcc779d9f5924d27ec40145be54304b4e38e8fdabf4936347ae',
    'pristine-source/highs/lp_data/HighsStatus.cpp': '973cd1932fe6c8d4d96fd1adf6c373ca818721b5df3b0558539bf301049af021',
    'pristine-source/highs/lp_data/Highs.cpp': '6f84c2f12277e7bf335b13e0ce63936d3f3c2b9ec95dd4910ffa8de077f899f0',
    'pristine-source/app/RunHighs.cpp': '724b3105716d31b6fe584dfc6e03955de71bb39d1e06aef7ce91fe15d252051f',
}
EXPECTED_TIME_LIMIT_RETURN = 'callSolveMip return of HighsStatus::Warning'
BOUND_METRIC = re.compile(r'Inconsistent max bound violation: MIP solver \(\s*(\S+)\); LP \(\s*(\S+)\); Difference of\s+(\S+)')
PATTERNS = (
    r'WARNING: Problem has some excessively (?:small|large) (?:costs|bounds on variables|bounds on continuous variables|bounds on non-continuous variables|bounds on constraints)',
    r'WARNING:    Consider scaling the objective by 1e[+-][0-9]+, or setting the user_objective_scale option to -?[0-9]+',
    r'WARNING:    Consider scaling the    bounds by 1e[+-][0-9]+, or setting the user_bound_scale option to -?[0-9]+',
    r'WARNING:    Consider setting the user_(?:objective|bound)_scale option to -?[0-9]+',
    r'WARNING: Problem is badly scaled, which may compromise the speed, accuracy and reliability of solvers in HiGHS',
)


def filter_scaling_advisories(text, source_path=None, *, mip_report=None, measurement=None, model_path=None, role=PROOF_ROLE):
    require(role in ROLES, 'Unknown MIP role')
    source = runtime_path('pristine-source/highs/lp_data/HighsSolve.cpp') if source_path is None else Path(source_path)
    require(helpers().sha256(source) == ADVISORY_SOURCE_SHA, 'Advisory source pin changed')
    kept, filtered, status_filtered, bound_measurements = [], [], [], []
    lines = text.splitlines(keepends=True)
    has_status = any(line.rstrip('\r\n') == EXPECTED_TIME_LIMIT_RETURN for line in lines)
    if has_status:
        require(sum(line.rstrip('\r\n') == EXPECTED_TIME_LIMIT_RETURN for line in lines) == 1,
            'Duplicate MIP return-status diagnostic')
        require(model_path is not None and isinstance(mip_report, dict) and isinstance(measurement, dict),
            'MIP return-status diagnostic lacks current report/process evidence')
        for relative, digest in STATUS_SOURCE_PINS.items():
            require(helpers().sha256(runtime_path(relative)) == digest, 'MIP return-status source pin changed: '+relative)
        sections = re.split(r'(?m)^Solving report[ \t]*$', text)
        require(len(sections) == 2, 'MIP return-status diagnostic requires one top-level report')
        require(EXPECTED_TIME_LIMIT_RETURN in sections[1].splitlines(), 'Return-status diagnostic precedes final report')
        def unique(label):
            values = re.findall(r'^  '+re.escape(label)+r'[ \t]+(.+)$', sections[1], re.M)
            require(len(values) == 1, 'Nonunique final '+label)
            return values[0].strip()
        accepted_warning_statuses = ('Time limit reached', 'Solution limit reached') if role == DISCOVERY else ('Time limit reached',)
        status = unique('Status')
        require(unique('Model') == Path(model_path).stem and status in accepted_warning_statuses,
            'Return-status diagnostic is not the current role-eligible master')
        require(mip_report.get('status') == status and all(mip_report.get(k) is True for k in
            ('clean_return','loaded_library_identity_valid','identities_valid','parent_report_identity_valid'))
            and isinstance(mip_report.get('model_definition_diagnostics'), list)
            and all(any(re.fullmatch(pattern, diagnostic) for pattern in PATTERNS)
                    for diagnostic in mip_report['model_definition_diagnostics']), 'Ineligible strict role/status report')
        # Reuse the exact existing cleanup policy. This shim cannot waive a kill,
        # incomplete reap, process overrun, error or missing resource receipt.
        import current_scuc.process_runner as process_runner
        process_runner.require_clean(measurement)
    for line in lines:
        plain = line.rstrip('\r\n')
        require('callSolveMip return of HighsStatus' not in plain or plain == EXPECTED_TIME_LIMIT_RETURN,
            'Unapproved or near-match MIP return-status diagnostic')
        if plain == EXPECTED_TIME_LIMIT_RETURN and has_status:
            status_filtered.append(plain)
        elif any(re.fullmatch(pattern, plain) for pattern in PATTERNS):
            filtered.append(plain)
        else:
            kept.append(line)
        if 'Inconsistent max bound violation' in plain:
            metric = BOUND_METRIC.fullmatch(plain)
            require(metric is not None, 'Malformed MIP bound diagnostic')
            numbers = [float(value) for value in metric.groups()]
            require(all(math.isfinite(value) and value >= 0 for value in numbers), 'Nonfinite/negative MIP bound diagnostic')
            bound_measurements.append(dict(line=plain,mip_solver=numbers[0],lp=numbers[1],difference=numbers[2],
                source_sha256=ADVISORY_SOURCE_SHA,acceptance_threshold_added=False,
                qualification='Diagnostic measurements only; unchanged master/original numerical QA remains mandatory'))
    clean = ''.join(kept)
    # Strict warnings/errors are not waived even if unrelated to model terms.
    bad = [line for line in clean.splitlines() if re.search(r'\b(?:warning|error|ignored|dropped)\b', line, re.I)
           and not re.fullmatch(r'\s*(?:Primal-dual|P-D) objective error\s*:\s*[0-9.eE+\-]+\s*', line)]
    require(not bad, 'Unapproved native diagnostics: '+repr(bad))
    return clean, dict(source_path=str(source), source_sha256=ADVISORY_SOURCE_SHA,
        filtered_lines=filtered, raw_log_sha256=hashlib.sha256(text.encode()).hexdigest(),
        role=role, expected_time_limit_return_lines=(status_filtered if mip_report and mip_report.get('status') == 'Time limit reached' else []),
        expected_solution_limit_return_lines=(status_filtered if mip_report and mip_report.get('status') == 'Solution limit reached' else []), expected_return_source_pins=STATUS_SOURCE_PINS if status_filtered else {},
        bound_diagnostic_measurements=bound_measurements,
        raw_log_preserved=True, unmatched_diagnostics_fatal=True, numerical_thresholds_changed=False)


def accepted_statuses(role=PROOF_ROLE):
    require(role in ROLES, 'Unknown MIP role')
    return ('Optimal', 'Time limit reached', 'Solution limit reached') if role == DISCOVERY else ('Optimal', 'Time limit reached')


def admit_report(report, *, role):
    """Explicit discovery barrier precedes every bound use, even for Optimal."""
    require(role in ROLES, 'Unknown MIP role')
    result = dict(report, role=role)
    if role == DISCOVERY:
        result.update(bound_status_valid=False, certificate_bound_eligible=False,
            upper_bound_eligible=False, global_lower=None, diagnostic_only=True,
            raw_master_objective_is_checked_original_upper=False,
            discovery_stop_activated=(report.get('status') == 'Solution limit reached'))
    require(result.get('status') in accepted_statuses(role) and result.get('model_definition_diagnostics') == []
        and all(result.get(k) is True for k in ('clean_return','loaded_library_identity_valid',
            'identities_valid','parent_report_identity_valid')), 'Unclean native role/status or identity')
    return result


def interval(lower, upper):
    if not finite(lower) or not finite(upper):
        return dict(passed=False, qualified=False, reason='nonfinite_endpoint')
    gap = (upper-lower)/max(abs(upper), 1e-10)
    if not math.isfinite(gap) or lower > upper:
        return dict(passed=False, qualified=False, reason='negative_or_nonfinite_gap')
    return dict(passed=True, qualified=gap <= .01, lower=lower, upper=upper, gap=gap,
        target=.01, lower_domain='hard_zero_shedding_reserve_integer_full_literal_lodf_subset', physical_dc_lower_bound_certified=False)


def lower_record(report, master_identity, cut_batches, *, target_identity):
    """The frozen parser supplies the conservative 12-digit allowance."""
    require(master_identity['integer_target_identity_sha256'] == target_identity, 'Mixed integer target')
    require(all(master_identity.get(k, {}).get('sense') == 1 and master_identity.get(k, {}).get('offset') == 0
        for k in ('master_hashes','canonical_master_hashes')), 'Wrong or missing objective identity')
    require(all(report.get(k) is True for k in ('clean_return','loaded_library_identity_valid',
        'identities_valid','parent_report_identity_valid','bound_status_valid','certificate_bound_eligible')),
        'Ineligible top-level MIP bound')
    require(report.get('status') in ('Optimal','Time limit reached') and report.get('model_definition_diagnostics') == [],
        'Ineligible MIP status/diagnostics')
    require(all(finite(report.get(k)) for k in ('printed_lower','lower_rounding_allowance','global_lower')),
        'Unavailable MIP bound is not zero')
    token = report.get('raw_lower_token')
    require(type(token) is str and len(token.split()) == 1 and math.isfinite(float(token))
        and float(token) == report['printed_lower'], 'MIP bound token changed')
    from current_scuc.core.driver.primal_and_bound import allowance
    require(report['lower_rounding_allowance'] == allowance(report['printed_lower'], report['raw_lower_token'])
        and report['global_lower'] == report['printed_lower']-report['lower_rounding_allowance'], 'Altered MIP display allowance')
    import current_scuc.no_shedding as no_shedding
    return dict(kind='numericalMIP', lower_domain=no_shedding.DOMAIN, lower=report['global_lower'], raw_token=report['raw_lower_token'],
        allowance=report['lower_rounding_allowance'], exact_certificate=False, report=report,
        master_identity=master_identity, integer_target_identity_sha256=target_identity, cut_batches=cut_batches)


def best_lower(records, target_identity):
    require(bool(records), 'No eligible lower endpoint')
    for r in records:
        require(r['kind'] in ('exactLP','numericalMIP') and finite(r['lower']), 'Invalid lower endpoint')
        require(r['integer_target_identity_sha256'] == target_identity, 'Mixed candidate target bounds')
        require(r.get('lower_domain') == 'hard_zero_shedding_reserve_integer_full_literal_lodf_subset', 'Mixed lower-domain bounds')
    return max(records, key=lambda r: r['lower'])
