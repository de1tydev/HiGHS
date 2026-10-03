"""Focused role/state/ledger contracts; no scientific import or optimizer."""
import copy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'payload/combined_screening_driver'))
from common import *
import trial_policy as policy
from pair_codec import PackedPairs,descriptor,write_pairs
from primal_and_bound import parse_primal_text,allowance

def scope():
    return descriptor(dict(lines=['l0','l1','l2'],rated_line_indices=[0,1,2],outage_indices=[2],
        checked_outage_ids=['out2'],outage_line_ids=['l2'],hours=2,buses=['b0','b1','b2'],generators=['g'],
        source_data_sha256='e'*64,source_sha256='f'*64),[2,2,2])

def proof_report(role=policy.PROOF,status='Optimal',lower=100.):
    ident=dict(kind='mip',role=role,objective_scope='unchanged_original_source',model_path='/model',stage_directory='/stage')
    ident.update({k:'a'*64 for k in ('source_sha256','model_sha256','expected_sha256','pair_manifest_sha256',
        'api_report_sha256','options_sha256','executable_sha256','generator_sha256','checker_sha256','runtime_manifest_sha256')})
    token=str(lower);pad=allowance(lower,token)
    return dict(role=role,scope='original_security_master_mip',status=status,usable_status=True,clean_return=True,
        loaded_library_identity_valid=True,identities_valid=True,parent_report_identity_valid=True,
        model_definition_diagnostics=[],bound_status_valid=True,certificate_bound_eligible=True,
        upper_bound_eligible=False,printed_lower=lower,raw_lower_token=token,lower_rounding_allowance=pad,
        global_lower=lower-pad,master_identity=ident)

class Fake:
    def __init__(self,path,discovery='rows',fail=None,overshoot=False,double=False):
        self.path=Path(path);self.eligible=scope();self.calls=[];self.discovery=discovery
        self.fail=fail;self.overshoot=overshoot;self.double=double
    def start(self,state):pass
    def checkpoint(self,state):json.dumps(state,allow_nan=False)
    def pair_manifest(self,active):
        p=self.path/(active.content_sha256()+'.u32')
        if not p.exists():write_json(str(p)+'.json',write_pairs(p,active),fresh=True)
        return read_json(str(p)+'.json')
    def stage(self,role,active,allocation,debit,rec):
        self.calls.append((role,tuple(active),allocation))
        debit(dict(process_wall_seconds=allocation+1 if self.overshoot else .1))
        if self.double:debit(dict(process_wall_seconds=.1))
        if self.fail:raise ContractError(self.fail)
        report=proof_report(role)
        discovery=role==policy.DISCOVERY
        if discovery:report.update(scope='integer_discovery_diagnostic_only',global_lower=None,
            certificate_bound_eligible=False,bound_status_valid=False)
        if discovery and self.discovery in {'no_lower','infinite_lower'}:
            report.update(printed_lower=None,raw_lower_token='inf' if self.discovery=='infinite_lower' else None,
                          lower_rounding_allowance=None)
        if discovery and self.discovery=='source_secure':report.update(printed_lower=50.,raw_lower_token='50')
        new=PackedPairs(self.eligible,[(0,2)] if discovery and self.discovery in {'rows','no_lower','infinite_lower'} else [])
        check=dict(kind='mip',primal_present=True,matrix_check={'passed':True},new_pairs=self.pair_manifest(new),
            full_source_primal_pass=not new,upper_bound_eligible=not discovery,certificate_bound_eligible=False,
            checked_upper=None if discovery else 100.)
        if discovery and self.discovery=='no_point':check=None
        return dict(report=report,check=check)

class Tests(unittest.TestCase):
    def test_options_are_exact_existing_A(self):
        self.assertEqual(policy.options_text(policy.PROOF),policy.existing.options_text('mip',False))
        self.assertEqual(policy.options_text(policy.DISCOVERY),policy.options_text(policy.PROOF)+'mip_max_improving_sols = 1\n')
        for role,other in [(policy.PROOF,policy.DISCOVERY),(policy.DISCOVERY,policy.PROOF)]:
            with self.assertRaises(ContractError):policy.validate_options(role,policy.options_text(other))
        with self.assertRaises(ContractError):policy.options_text('lp')
    def test_discovery_debit_once_and_actual_remaining(self):
        b=policy.Budget();self.assertEqual(b.allocation(policy.DISCOVERY),300.)
        b.debit(policy.DISCOVERY,300.,{'process_wall_seconds':360.})
        self.assertEqual(b.allocation(policy.DISCOVERY),0.)
        self.assertEqual(b.allocation(policy.PROOF),240.)
        with self.assertRaises(ContractError):b.debit(policy.DISCOVERY,300.,{'process_wall_seconds':1.})
        b.debit(policy.PROOF,240.,{'process_wall_seconds':241.})
        self.assertFalse(b.record()['in_budget']);self.assertEqual(b.record()['solver_process_wall_seconds'],601.)
    def test_bad_debits(self):
        for value in [None,float('nan'),float('inf'),-1.]:
            with self.subTest(value=value),self.assertRaises(ContractError):
                policy.Budget().debit(policy.PROOF,600.,{'process_wall_seconds':value})
        with self.assertRaises(ContractError):policy.Budget().debit(policy.PROOF,300.,{'process_wall_seconds':1.})
    def test_one_discovery_always_transitions_without_certificate(self):
        for kind in ['rows','no_point','no_rows','source_secure','no_lower','infinite_lower']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                b=Fake(tmp,kind);state=policy.run_pipeline(b,True)
                self.assertTrue(state['complete'],state['reason'])
                self.assertEqual([r[0] for r in b.calls],[policy.DISCOVERY,policy.PROOF])
                self.assertEqual(b.calls[1][1],((0,2),) if kind in {'rows','no_lower','infinite_lower'} else ())
                self.assertEqual(state['best_integer_stage'],2)
                self.assertEqual(len(state['integer_master_bounds']),1)
                self.assertEqual(state['certificate']['upper_provenance']['role'],policy.PROOF)
                self.assertAlmostEqual(state['budget']['solver_process_wall_seconds'],.2)
    def test_control_has_no_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Fake(tmp);state=policy.run_pipeline(b,False)
            self.assertTrue(state['complete']);self.assertEqual([r[0] for r in b.calls],[policy.PROOF])
    def test_discovery_role_rejected_even_when_optimal_and_good_bound(self):
        for role in [policy.DISCOVERY,None,'repair']:
            report=proof_report(role)
            self.assertFalse(policy.certificate(100.,[report],{'in_budget':True,'lp_policy_valid':True})['complete'])
        self.assertTrue(policy.certificate(100.,[proof_report()],{'in_budget':True,'lp_policy_valid':True})['complete'])
    def test_failure_and_double_debit_stop_before_proof(self):
        for fail,double in [('killed',False),('malformed',False),('identity',False),(None,True)]:
            with self.subTest(fail=fail,double=double),tempfile.TemporaryDirectory() as tmp:
                b=Fake(tmp,fail=fail,double=double);state=policy.run_pipeline(b,True)
                self.assertTrue(state['stop_campaign']);self.assertFalse(state['complete'])
                self.assertEqual(len(b.calls),1);self.assertEqual(state['budget']['solver_process_wall_seconds'],.1)
    def test_overshoot_counts_and_cannot_certify(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Fake(tmp,overshoot=True);state=policy.run_pipeline(b,True,total=20.)
            self.assertEqual(len(b.calls),1);self.assertEqual(state['budget']['solver_process_wall_seconds'],21.)
            self.assertFalse(state['complete'])
    def test_role_status_split_and_clean_errors_before_parse(self):
        clean={'returncode':0,'hard_watchdog_killed':False}
        for status in ['Solution limit reached','Optimal','Time limit reached','Interrupt','HighsInterrupt','Unknown']:
            for role in [policy.DISCOVERY,policy.PROOF]:
                with self.subTest(role=role,status=status),patch.object(policy.original,'solver_report',return_value=proof_report(role,status)):
                    if status in {'Optimal','Time limit reached'} or (role==policy.DISCOVERY and status=='Solution limit reached'):
                        r=policy.report_for_role('',clean,Path('/model'),role)
                        if role==policy.DISCOVERY:self.assertIsNone(r['global_lower']);self.assertFalse(r['bound_status_valid'])
                    else:
                        with self.assertRaises(ContractError):policy.report_for_role('',clean,Path('/model'),role)
        for measured in [{'returncode':1},{'returncode':0,'hard_watchdog_killed':True},{'returncode':0,'interrupted':True}]:
            with patch.object(policy.original,'solver_report') as parser,self.assertRaises(ContractError):
                policy.report_for_role('untrusted partial',measured,Path('/model'),policy.DISCOVERY)
            parser.assert_not_called()
    def test_discovery_without_finite_lower_remains_usable(self):
        for token in [None,'inf','-inf','nan']:
            source=proof_report(status='Time limit reached')
            source.update(printed_lower=None,raw_lower_token=token,global_lower=None,
                          lower_rounding_allowance=None,bound_status_valid=False,certificate_bound_eligible=False)
            with patch.object(policy.original,'solver_report',return_value=source):
                r=policy.report_for_role('',{'returncode':0},Path('/model'),policy.DISCOVERY)
                self.assertTrue(r['usable_status']);self.assertIsNone(r['global_lower'])
    def test_malformed_primal_stays_fatal(self):
        good='Model status\nSolution limit reached\n# Primal solution values\nFeasible\nObjective 1\n# Columns 1\nx 1\n# Rows 0\n# Dual solution values\nNone\n'
        self.assertEqual(parse_primal_text(good,['x'])['values'],{'x':1.})
        for text in [good.replace('x 1\n','x 1\nx 1\n'),good.replace('x 1\n',''),good.replace('x 1','x nan'),good.replace('Feasible','Infeasible'),good.replace('Objective 1','Objective inf')]:
            with self.assertRaises(ContractError):parse_primal_text(text,['x'])
        self.assertIsNone(parse_primal_text('Model status\nTime limit reached\n# Primal solution values\nNone\n# Dual solution values\nNone\n',['x']))

if __name__=='__main__':unittest.main()
