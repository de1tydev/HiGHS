"""Role-specific policy, process ledger and proof-only certificate gate."""
import re
from common import *
import cold_screen_pair as existing
import primal_and_bound as original
from pair_codec import PackedPairs

DISCOVERY = 'integer_discovery'
PROOF = 'integer_proof'
ROLES = {DISCOVERY, PROOF}

def options_text(role):
    if role not in ROLES: raise ContractError('Unknown role')
    text = existing.options_text('mip', False)
    if role == DISCOVERY: text += 'mip_max_improving_sols = 1\n'
    validate_options(role, text)
    return text

def validate_options(role, text):
    base = existing.options_text('mip', False)
    expected = base + ('mip_max_improving_sols = 1\n' if role == DISCOVERY else '')
    if role not in ROLES or text != expected:
        raise ContractError('Role/options leakage or common A options changed')

class Budget:
    def __init__(self, total=600.):
        if not finite(total) or not 0 < total <= 600: raise ContractError('Invalid budget')
        self.total, self.spent, self.discovery_calls = float(total), 0., 0
        self.calls = []

    def allocation(self, role):
        remaining = max(0., self.total-self.spent)
        if role == PROOF: return remaining
        if role != DISCOVERY: raise ContractError('Unknown budget role')
        return 0. if self.discovery_calls else min(300., remaining)

    def debit(self, role, allocation, measurement):
        wall = measurement.get('process_wall_seconds')
        if not finite(wall) or wall < 0 or not finite(allocation) or allocation <= 0:
            raise ContractError('Missing/nonfinite actual process debit')
        if allocation != self.allocation(role): raise ContractError('Stale/invalid allocation')
        self.spent += wall
        self.discovery_calls += role == DISCOVERY
        self.calls.append(dict(role=role, allocation=allocation, actual=wall, overrun=max(0., wall-allocation)))

    def record(self):
        return dict(total=self.total, solver_process_wall_seconds=self.spent,
                    remaining=max(0., self.total-self.spent), in_budget=self.spent<=self.total,
                    lp_policy_valid=True, lp_calls=0, lp_process_wall_seconds=0.,
                    discovery_calls=self.discovery_calls, calls=self.calls)

def report_for_role(text, measured, model, role):
    if role not in ROLES: raise ContractError('Unknown report role')
    # Never parse any killed or abnormal-return output, including diagnostic reports.
    if (measured.get('returncode') != 0 or measured.get('hard_watchdog_killed')
        or measured.get('interrupted') or measured.get('launch_or_measurement_error')):
        raise ContractError('Failed/killed solver process; output is not parsed')
    report = original.solver_report(text, measured, 'mip', model, LIBRARY, identities_valid=True)
    accepted = {'Optimal', 'Time limit reached'} | ({'Solution limit reached'} if role == DISCOVERY else set())
    warnings = [line for line in text.splitlines() if re.match(r'^(WARNING|ERROR):', line)]
    if (warnings or report.get('status') not in accepted or report['model_definition_diagnostics']
        or not all(report.get(k) is True for k in ('clean_return', 'loaded_library_identity_valid',
                                                  'identities_valid', 'parent_report_identity_valid'))):
        raise ContractError('Unclean exact role/model/runtime status: '+str(report.get('status'))+' '+repr(warnings))
    report.update(role=role, usable_status=True)
    if role == DISCOVERY:
        # Keep raw report diagnostics, but erase all certificate channels even for Optimal.
        report.update(scope='integer_discovery_diagnostic_only', upper_bound_eligible=False,
                      certificate_bound_eligible=False, bound_status_valid=False, global_lower=None)
    return report

def certificate(upper, bounds, ledger):
    if any(b.get('role') != PROOF or b.get('master_identity',{}).get('role') != PROOF for b in bounds):
        return dict(valid=False, complete=False, gap=None, reason='Non-proof role in certificate ledger')
    return original.certificate(upper, bounds, ledger)

def run_pipeline(backend, candidate, *, total=600.):
    budget = Budget(total); active = None; bounds = []; upper = None
    state = dict(arm='early_candidate' if candidate else 'A', complete=False, trace=[],
                 reason='not started', target_gap=.01, warm_start=False, initial_pairs=[],
                 lp_discovery=False, constructive_seed=False, discovery_bound_carry=False,
                 incumbent_carry=False, basis_carry=False, solver_state_carry=False)
    def stage(role):
        allocation = budget.allocation(role)
        if allocation <= 0: return None
        rec = dict(kind='mip', role=role, active_pairs=backend.pair_manifest(active), allocation=allocation,
                   upper_bound_eligible=False, certificate_bound_eligible=False)
        state['trace'].append(rec)
        debited = False
        def debit(measured):
            nonlocal debited
            if debited: raise ContractError('Solver charged twice')
            budget.debit(role, allocation, measured); debited=True
            rec['solver']=measured; state['budget']=budget.record(); backend.checkpoint(state)
        result = backend.stage(role, active, allocation, debit, rec)
        if not debited: raise ContractError('Solver process was not charged')
        rec.update(result)
        report = result['report']
        if report.get('role') != role or not report.get('usable_status') or not report.get('clean_return'):
            raise ContractError('Stage role/clean-status gate failed')
        checked, new = existing.validate_stage(result, 'mip', backend.eligible, active)
        if role == DISCOVERY:
            if any(report.get(k) for k in ('upper_bound_eligible','bound_status_valid','certificate_bound_eligible')) or report.get('global_lower') is not None:
                raise ContractError('Discovery report attempted certificate promotion')
            if checked and (checked.get('upper_bound_eligible') or checked.get('certificate_bound_eligible') or checked.get('checked_upper') is not None):
                raise ContractError('Discovery point attempted upper-bound promotion')
        backend.checkpoint(state)
        return rec, checked, new
    try:
        backend.start(state)
        active = PackedPairs(backend.eligible)
        if candidate:
            result = stage(DISCOVERY)
            if result is not None:
                rec, checked, new = result
                if new:
                    active=active.merged(new); rec['accepted_new_pairs']=backend.pair_manifest(new)
                rec['discovery_transition']='fresh cold proof'
                rec['discovery_point_usable']=checked is not None
            # No discovery U/L or vector is retained for optimization or certification.
        while budget.allocation(PROOF)>0:
            result=stage(PROOF)
            if result is None: break
            rec, checked, new = result
            if checked and checked.get('upper_bound_eligible') is True:
                if checked.get('full_source_primal_pass') is not True or new or not finite(checked.get('checked_upper')):
                    raise ContractError('Unchecked proof upper bound')
                if upper is None or checked['checked_upper']<upper:
                    upper=checked['checked_upper']; state['best_integer_point']=checked
                    state['best_integer_stage']=len(state['trace'])
            report=rec['report']
            if not report.get('bound_status_valid'):
                if report['status']=='Time limit reached':
                    state['reason']='normal proof time limit without finite bound'; break
                raise ContractError('Missing eligible exact proof MIP bound')
            bounds.append(report)
            cert=certificate(upper,bounds,budget.record());state['certificate']=cert
            if upper is not None:
                cert['upper_provenance']={'role':PROOF,'stage':state['best_integer_stage'],
                    'identity':state['best_integer_point'].get('identity'),
                    'check_artifact':state['best_integer_point'].get('check_artifact')}
            if cert.get('complete'):
                state.update(complete=True,reason='full original-source 1% numerical certificate'); break
            if checked is None: state['reason']='normal proof exit without complete primal'; break
            if not new:
                state['reason']='source-secure proof point misses fixed certificate policy'; break
            active=active.merged(new); rec['accepted_new_pairs']=backend.pair_manifest(new)
            state['reason']='solver process budget exhausted'
    except BaseException as exc:
        interrupted=isinstance(exc,(KeyboardInterrupt,SystemExit)) or any(r.get('solver',{}).get('interrupted') for r in state['trace'])
        state.update(complete=False,reason=type(exc).__name__+': '+str(exc),interrupted=bool(interrupted),
                     failure_class='cancellation' if interrupted else 'integrity_or_resource',stop_campaign=True)
    finally:
        state.update(active_pairs=backend.pair_manifest(active) if active is not None else None,
                     budget=budget.record(),integer_master_bounds=bounds)
        state.setdefault('certificate',certificate(upper,bounds,budget.record()))
        if not budget.record()['in_budget']: state['complete']=False
        backend.checkpoint(state)
    return state
