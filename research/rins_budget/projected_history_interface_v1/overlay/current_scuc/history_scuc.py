"""One explicit exposed June-to-October proposal and public-API probe.

No changes to ordinary CLI report parsing, original physics, or bound admission.
This module belongs only to the separately sealed experimental package.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import itertools
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

from current_scuc._paths import ROOT, source_sha
from current_scuc import binding as b, process_runner as process

ROLE = 'history_probe'
API_SCHEMA = 'projected-history-api-evidence/v1'
ADAPTER_SHA = '64fc588e461c918ead65bd55c9c0dbaa9667f3047d0ba95734e41ea9b48944ca'
PROBE_SECONDS = 30.
NATIVE_SECONDS = 25.
CHECK_SECONDS = 60.
ADMISSION_SECONDS = 30.
ORDINARY_RESERVE = 180.
NATIVE_FILE_BYTES = 16 * 1024**2
METADATA_BYTES = 1024**2
PRODUCTION_PROFILE = dict(admission=30., probe_process=30., probe_native=25., check=60., ordinary_reserve=180., final_reserve=360.)
TINY_PROFILE = dict(admission=2., probe_process=30., probe_native=25., check=5., ordinary_reserve=80., final_reserve=20.)


def record(path):
    return dict(path=str(Path(path).resolve()), sha256=b.sha(path))


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    b.require(len(payload) <= METADATA_BYTES, 'Historical metadata exceeds 1 MiB')
    with Path(path).open('xb') as stream:
        stream.write(payload)


def load_plan():
    path = ROOT / 'history_plan.json'
    digest = source_sha('history_plan.json')
    plan = b.read(path)
    b.require(plan['schema'] == 'projected-history-fixed-plan/v1' and plan['mode'] in ('history', 'tiny_history'), 'Unknown frozen historical plan')
    b.require(plan['adapter']['sha256'] == ADAPTER_SHA and b.sha(plan['adapter']['path']) == ADAPTER_SHA, 'Qualified API adapter changed')
    b.require(plan['simulated_chronology'] is True and plan['solver_random_seed'] == 1, 'Fixed retrospective development policy')
    b.require(plan['profile'] == (PRODUCTION_PROFILE if plan['mode']=='history' else TINY_PROFILE), 'Frozen history timing profile changed')
    return plan, digest


def _june(plan):
    """Call the qualified data-only importer without leaving sys.path changes."""
    support = Path(plan['qualified_interface']).resolve()
    for relative, digest in plan['qualified_source_pins'].items():
        b.require(b.sha(support / relative) == digest, 'Qualified historical admission source changed')
    names = ('common', 'history', 'history_start', 'june_label')
    b.require(not any(name in sys.modules for name in names), 'Historical helper module collision')
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(support))
        module = importlib.import_module('june_label')
        label = module.admit_june(plan['recovery_root'], seconds=ADMISSION_SECONDS)
        b.require(module.digest(label.record) == label.record_digest, 'Historical label mutated after admission')
        return copy.deepcopy(label.record)
    finally:
        sys.path[:] = previous
        for name in names:
            sys.modules.pop(name, None)


def propose(plan, original_data, restored):
    inventory = restored['source_binary_inventory']
    u = [entry for entry in inventory if entry['name'].startswith('u_')]
    if plan['mode'] == 'history':
        cfg = b.config()
        b.require(cfg['inputs']['current']['sha256'] == plan['target_raw_source_sha256'], 'Fixed October source changed')
        label = _june(plan)
        b.require(label['scope'] == 'scuc_checked' and label['case'] == 'case1354pegase'
                  and label['start'] == '2017-06-01T00:00:00+00:00'
                  and label['end'] == '2017-06-02T12:00:00+00:00'
                  and plan['target_scenario_start'] == '2017-10-01T00:00:00+00:00', 'Fixed nonoverlapping simulated pair changed')
        # Same exact static projection used by the qualified June importer.
        def safe(value):
            if isinstance(value, float) and not math.isfinite(value): return '+inf' if value > 0 else '-inf'
            if isinstance(value, dict): return {key: safe(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)): return [safe(item) for item in value]
            return value
        topology = identity(safe(dict(buses=list(original_data['Buses']), generators=list(original_data['Generators']),
            lines=list(original_data['Transmission lines'].items()), contingencies=list(original_data['Contingencies'].items()), hours=36)))
        b.require(topology == label['topology'], 'Historical/current topology incompatibility')
    else:
        # A fixed synthetic mechanism fixture, not a SCUC training label.
        b.require(list(original_data['Generators']) == ['g0', 'g1'] and len(u) == 4, 'Tiny fixed fixture changed')
        schedules = list(itertools.product((0, 1), repeat=4))
        label = dict(scope='synthetic_mechanism_only', columns=[entry['name'] for entry in u], u=list(schedules[-1]),
                     enumerated_commitment_assignments=len(schedules), selection='fixed all-on member of enumeration',
                     historical_feasibility_claimed=False)
    b.require(label['columns'] == [entry['name'] for entry in u] and len(label['u']) == len(u), 'Exact historical/current commitment names differ')
    mapped, fixed = [], []
    for entry, value in zip(u, label['u']):
        b.require(type(value) is int and value in (0, 1) and entry['integrality'] == 1, 'Nonliteral historical binary')
        bounds = (entry['lower'], entry['upper'])
        if bounds in ((0., 0.), (1., 1.)):
            fixed.append([entry['name'], value, entry['lower']])
            continue  # Current source-fixed values always prevail, including conflicts.
        b.require(bounds == (0., 1.), 'Unsupported current commitment bounds')
        mapped.append([entry['name'], entry['original_column'], entry['projected_column'], value])
    b.require(len({row[0] for row in mapped}) == len(mapped), 'Duplicate projected proposal')
    return dict(schema='projected-history-proposal/v1', simulated_chronology=True, trained_model=False,
                historical_record=label, mapped_current_commitments=mapped, omitted_current_fixed=fixed,
                target_identity_sha256=restored['identity']['integer_target_identity_sha256'],
                adaptive_map_hash=restored['identity']['adaptive_map_hash'])


def _options():
    return dict(threads=2, parallel='off', random_seed=1, time_limit=NATIVE_SECONDS, mip_rel_gap=0, mip_abs_gap=0)


def _artifact(item, *, inside=None, checked=None):
    path = Path(item['path']).resolve()
    b.require(path.is_file() and not path.is_symlink() and b.sha(path) == item['sha256'], 'Historical API artifact changed')
    if inside is not None: b.require(path.is_relative_to(inside), 'Foreign historical API artifact')
    if checked is not None: checked(path, item['sha256'], inside=inside is not None)
    return path


def verify_api_evidence(row, *, expected_seed, checked=None):
    b.require(row['role'] == ROLE and row['call'] == 1 and expected_seed == row['solver_random_seed'] == 1, 'Historical API role/seed changed')
    ev = row['api_evidence']
    b.require(ev['schema'] == API_SCHEMA, 'Historical API evidence schema')
    rd = Path(row['master_identity']['model_path']).resolve().parent / 'history-probe'
    files = {}
    for key in ('proposal', 'suggestions', 'request', 'metadata', 'point'):
        path = _artifact(ev[key], inside=rd, checked=checked)
        files[str(path)] = ev[key]['sha256']
    adapter = _artifact(ev['adapter'], checked=checked)
    library = _artifact(ev['library'], checked=checked)
    plan, plan_sha = load_plan()
    b.require(ev['plan_sha256'] == plan_sha and record(adapter) == plan['adapter'], 'History plan/adapter changed')
    request = b.read(ev['request']['path']); meta = b.read(ev['metadata']['path'])
    cfg = b.config()
    b.require(request['master_identity_sha256'] == identity(row['master_identity']) and
              request['model'] == dict(path=row['master_identity']['model_path'], sha256=row['master_identity']['model_sha256']), 'Historical current master changed')
    b.require(request['command'] == [str(adapter), row['master_identity']['model_path'], ev['suggestions']['path'],
              ev['point']['path'], ev['metadata']['path'], '25', 'probe'], 'Historical actual API argv changed')
    wanted_command=[cfg['python'],'-B','-s','-m','current_scuc.history_scuc','--exec-adapter',ev['request']['path'],ev['request']['sha256']]
    b.require(row['command'] == row['process']['command'] == wanted_command, 'Historical supervised argv/request changed')
    process.require_clean(row['process'])
    b.require(meta['mode'] == 'probe' and meta['outcome'] == 'point' and meta['run_api_status'] in (0, 1)
              and meta['native_model_status'] in (7, 13) and meta['complete_primal_present'] is True
              and meta['model_fields_verified'] is True and meta['options_verified'] is True
              and meta['options'] == _options(), 'Unaccepted historical API metadata')
    b.require(Path(meta['loaded_library_path']).resolve() == library == Path(cfg['library']).resolve()
              and record(library) == request['library'], 'Historical library mismatch')
    b.require(row['native_limit_seconds'] == NATIVE_SECONDS and row['allocation_seconds'] == PROBE_SECONDS, 'Historical fixed process/native cap changed')
    return dict(files_sha256=files, options=meta['options'])


def _clean_probe(receipt):
    if not receipt['hard_watchdog_killed']:
        process.require_clean(receipt, allowed_returns=(0, 2))
        return True
    b.require(receipt['cleanup_verified'] is True and receipt['resource_accounting_complete'] is True
              and receipt['wait4_echild'] is True and not receipt['remaining_owned_pids']
              and not receipt['interrupted'] and not receipt['error'] and not receipt['health_check_error']
              and receipt['actual_within_allocation'] is True, 'Unclean probe timeout is terminal')
    return False


def attempt(plan, plan_sha, cfg, data, restored, exported, state, ledger, out, deadline, *, master):
    """Return a checked projected point or a clean pre-evaluation abstention.

    This never calls the mutable full oracle. Its caller owns that terminal
    boundary and finishes the charged history_check phase after full evaluation.
    """
    from current_scuc.common import start_output_phase, storage
    budget = storage(); rd = Path(exported['identity']['model_path']).parent
    probe = rd / 'history-probe'; probe.mkdir()
    profile=plan['profile']
    state['history'] = dict(plan_sha256=plan_sha, simulated_chronology=True, policy='one previous-window commitment copy',
                           trained_model=False, lower_bound=None, upper_bound=None,
                           admission_cap_seconds=profile['admission'],check_cap_seconds=profile['check'])
    reserve = profile['admission'] + PROBE_SECONDS + profile['check'] + profile['ordinary_reserve']
    if ledger.spent + reserve > 600 or deadline - time.monotonic() < reserve + profile['final_reserve']:
        state['history']['outcome'] = 'abstained_before_admission_insufficient_reserve'
        return None
    tick = time.monotonic()
    admission_remaining=profile['admission']-sum(item['actual'] for item in ledger.auxiliary if item['stage']=='history_admission')
    b.require(admission_remaining>0,'No historical admission allowance remains')
    try:
        start_output_phase(rd, 'historical proposal files', [budget.WriteBound(probe/name, METADATA_BYTES,
            'historical proposal metadata', 'maximum1MiB metadata') for name in ('proposal.json','request.json','process.json')]
            + [budget.WriteBound(probe/'suggestions.txt', NATIVE_FILE_BYTES, 'named binary suggestions', 'maximum16MiB')])
        proposal = propose(plan, data, restored)
        write(probe / 'proposal.json', proposal)
        with (probe / 'suggestions.txt').open('x') as stream:
            for name, _, _, value in proposal['mapped_current_commitments']: stream.write(f'{name} {value}\n')
    finally:
        b.require(ledger.debit_auxiliary('history_admission', admission_remaining, time.monotonic()-tick), 'Historical admission/600 ledger exceeded')
    if not proposal['mapped_current_commitments']:
        state['history']['outcome'] = 'abstained_no_free_commitments'
        return None
    b.require(ledger.spent + PROBE_SECONDS + profile['check'] + profile['ordinary_reserve'] <= 600
              and deadline-time.monotonic() >= PROBE_SECONDS+profile['check']+profile['ordinary_reserve']+profile['final_reserve'], 'Historical probe reserve lost')
    point, metadata = probe / 'complete.point', probe / 'api.json'
    api_command = [plan['adapter']['path'], exported['identity']['model_path'], str(probe/'suggestions.txt'), str(point), str(metadata), '25', 'probe']
    request = dict(schema='projected-history-api-exec/v1', command=api_command, adapter=plan['adapter'], library=record(cfg['library']),
                   model=dict(path=exported['identity']['model_path'], sha256=exported['identity']['model_sha256']),
                   suggestions=record(probe/'suggestions.txt'), master_identity_sha256=identity(exported['identity']), plan_sha256=plan_sha)
    write(probe/'request.json', request); req = record(probe/'request.json')
    command = [cfg['python'], '-B', '-s', '-m', 'current_scuc.history_scuc', '--exec-adapter', req['path'], req['sha256']]
    start_output_phase(rd, 'historical API probe', [budget.WriteBound(probe/name, NATIVE_FILE_BYTES,
        'historical adapter output', 'tested16MiB native file cap') for name in ('solver.log','complete.point')]
        + [budget.WriteBound(metadata, NATIVE_FILE_BYTES, 'API metadata', 'enforced16MiB native file cap; accepted metadata at most1MiB')])
    receipt = process.run(command, probe/'solver.log', out, PROBE_SECONDS)
    index = len(ledger.auxiliary)
    debit_ok = ledger.debit_auxiliary('history_probe', PROBE_SECONDS, receipt['process_wall_seconds'], process_receipt=receipt)
    state['history']['pending_check_started'] = time.monotonic()
    write(probe/'process.json', receipt)
    b.require(debit_ok, 'Historical process/600 ledger exceeded')
    ordinary_exit = _clean_probe(receipt)
    # Descriptive raw telemetry, never used to admit a point or a bound.
    text = (probe/'solver.log').read_text()
    state['history']['mechanism_log'] = dict(path=str(probe/'solver.log'), sha256=b.sha(probe/'solver.log'),
        completion_lines=[line for line in text.splitlines() if 'user-supplied' in line.lower() or 'User-supplied' in line][:20],
        interpretation='Public run may continue ordinary search after completion; endpoint alone does not prove assignment completion')
    if not ordinary_exit:
        ledger.reject_probe(index); state['history']['outcome'] = 'clean_probe_timeout_cold_fallback'; return None
    meta = b.read(metadata)
    b.require(metadata.stat().st_size <= METADATA_BYTES, 'Historical API metadata exceeds cap')
    b.require(meta['model_fields_verified'] is True and meta['options_verified'] is True and meta['options'] == _options()
              and Path(meta['loaded_library_path']).resolve() == Path(cfg['library']).resolve(), 'Historical probe identity/options failed')
    b.require(b.sha(cfg['library']) == request['library']['sha256'] and b.sha(plan['adapter']['path']) == ADAPTER_SHA
              and b.sha(exported['identity']['model_path']) == exported['identity']['model_sha256'], 'Historical live input changed')
    if meta['outcome'] == 'no_point' and meta['complete_primal_present'] is False:
        ledger.reject_probe(index); state['history']['outcome'] = 'no_point_cold_fallback'; return None
    b.require(meta['outcome'] == 'point' and meta['complete_primal_present'] is True and meta['run_api_status'] in (0, 1)
              and meta['native_model_status'] in (7, 13), 'Historical API status failed')
    check_started = state['history']['pending_check_started']
    values = {}
    for line in point.read_text().splitlines():
        words = line.split()
        b.require(len(words) == 2 and words[0] not in values, 'Malformed historical complete point')
        value = float(words[1]); b.require(math.isfinite(value), 'Nonfinite historical complete point'); values[words[0]] = value
    # Structural/checker exceptions and objective disagreement are terminal.
    checked = master.check_integer_values(exported['expected'], values)
    b.require(type(checked['passed']) is bool and type(checked['linear_objective']) in (int,float)
              and math.isfinite(checked['linear_objective']), 'Malformed historical checker result')
    for name in ('point_objective', 'solver_reported_objective'):
        objective = meta[name]
        b.require(type(objective) in (int,float) and math.isfinite(objective) and
            abs(objective-checked['linear_objective']) <= max(1e-5, abs(objective)*1e-10), 'Historical objective mismatch')
    if checked['passed'] is False:
        failures=checked['failures']
        b.require(isinstance(failures,list) and failures and set(failures)<={
            'independent row infeasibility','independent bound infeasibility','independent binary integrality infeasibility'},
            'Historical checker failure is not ordinary numerical infeasibility')
        check_ok=ledger.debit_auxiliary('history_check', profile['check'], time.monotonic()-check_started)
        state['history'].pop('pending_check_started')
        b.require(check_ok, 'Rejected history check exceeded ledger')
        ledger.reject_probe(index); state['history'].update(outcome='projected_point_rejected_cold_fallback', rejection=failures); return None
    api = dict(schema=API_SCHEMA, plan_sha256=plan_sha, proposal=record(probe/'proposal.json'), suggestions=record(probe/'suggestions.txt'),
               request=req, metadata=record(metadata), point=record(point), adapter=plan['adapter'], library=request['library'])
    row = dict(call=1, role=ROLE, solver_random_seed=1, cut_batches=state['cut_batches'], native_limit_seconds=NATIVE_SECONDS,
               allocation_seconds=PROBE_SECONDS, incumbent_input=str(probe/'suggestions.txt'), no_basis_or_search_state_input=True,
               master_identity=exported['identity'], command=command, process=receipt, api_evidence=api)
    verify_api_evidence(row, expected_seed=1)
    ledger.accept_probe(index); state['history']['outcome'] = 'accepted_projected_point_pending_full_evaluation'
    return dict(row=row, check=checked, check_started=check_started, check_cap_seconds=profile['check'],
                check_deadline=min(check_started+profile['check'], deadline-profile['final_reserve']))


def main():
    parser = argparse.ArgumentParser(description='Contained execution of the frozen API probe request')
    parser.add_argument('--exec-adapter', nargs=2, required=True)
    args = parser.parse_args(); path, wanted = args.exec_adapter
    b.require(b.sha(path) == wanted, 'API exec request changed')
    request = b.read(path); plan, plan_sha = load_plan()
    b.require(request['schema'] == 'projected-history-api-exec/v1' and request['plan_sha256'] == plan_sha, 'API exec scope changed')
    for key in ('adapter', 'library', 'model', 'suggestions'): _artifact(request[key])
    b.require(request['adapter'] == plan['adapter'] and request['command'][0] == plan['adapter']['path']
              and request['command'][1] == request['model']['path'] and request['command'][2] == request['suggestions']['path']
              and request['command'][-2:] == ['25', 'probe'], 'API exec argv changed')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); resource.setrlimit(resource.RLIMIT_FSIZE, (NATIVE_FILE_BYTES,)*2)
    os.execv(request['command'][0], request['command'])


if __name__ == '__main__': main()
