"""Pure/mocked combined-arm contracts, never numerical topology work."""
import copy
import hashlib
from pathlib import Path
import py_compile
import sys
import tempfile
import unittest
from unittest.mock import patch
import cold_screen_pair as pair
import contracts
import policy
import stage_child

class CombinedTests(unittest.TestCase):
    def test_fixed_arm_records(self):
        self.assertEqual(policy.arm_record('A'),dict(name='A',lp_discovery=False,root_credit=False,separator_variant='baseline'))
        self.assertEqual(policy.arm_record('B'),dict(name='B',lp_discovery=True,root_credit=True,separator_variant='optimized'))
        with self.assertRaises(Exception):policy.ARMS['A'].lp_discovery=True
        with self.assertRaises(ValueError):policy.arm_record('C')

    def test_runtime_manifest_delegates_and_normalizes_binding_errors(self):
        # Mandatory portable pin coverage lives in test_portable_runtime. The
        # numerical contracts expose the same public error type as before.
        record={'status':'source_and_mock_review_ready_no_numerical_launch'}
        with patch.object(contracts,'_validate_manifest',return_value=record) as validate:
            self.assertIs(contracts.runtime_manifest('/mock'),record)
            validate.assert_called_once_with(contracts.HERE,'/mock')
        for error in (ValueError('changed pin'),OSError('missing artifact'),KeyError('required pin')):
            with self.subTest(error=type(error)),patch.object(contracts,'_validate_manifest',side_effect=error):
                with self.assertRaises(contracts.ContractError) as caught:contracts.runtime_manifest('/mock')
                self.assertIs(caught.exception.__cause__,error)

    def good_tiny(self):
        def stage(arm,kind,active,new,full=False):
            selector={'passed':True,'arm':arm,'loaded_python_modules':{'fractional_separator':{'sha256':contracts.SEPARATOR_SHA256[arm]}}}
            return {'kind':kind,'active_pairs':active,'accepted_new_pairs':new,'generate_selector':selector,'check_selector':selector,
                    'check':{'full_source_primal_pass':full}}
        return {'A':{'state':{'complete':True,'arm_record':policy.arm_record('A'),'certificate':{'upper':660.},'lp_seed_pairs':[],
            'trace':[stage('A','mip',[],[[1,2]]),stage('A','mip',[[1,2]],[],True)]}},
            'B':{'state':{'complete':True,'arm_record':policy.arm_record('B'),'certificate':{'upper':660.},'lp_seed_pairs':[[1,2]],
            'trace':[stage('B','lp',[],[[1,2]]),stage('B','mip',[[1,2]],[],True)]}}}

    def test_tiny_asymmetric_entry_and_full_certificates(self):
        good=self.good_tiny();self.assertTrue(pair.tiny_pipeline_verified(good))
        for arm in ('A','B'):
            for bad in (None,float('nan'),0,661.):
                value=copy.deepcopy(good);value[arm]['state']['certificate']['upper']=bad
                self.assertFalse(pair.tiny_pipeline_verified(value))
        bad=copy.deepcopy(good);bad['A']['state']['trace'].pop(0);self.assertFalse(pair.tiny_pipeline_verified(bad))
        bad=copy.deepcopy(good);bad['A']['state']['trace'][0]['kind']='lp';self.assertFalse(pair.tiny_pipeline_verified(bad))
        bad=copy.deepcopy(good);bad['B']['state']['lp_seed_pairs']=[];self.assertFalse(pair.tiny_pipeline_verified(bad))
        bad=copy.deepcopy(good);bad['B']['state']['trace'][-1]['check']['full_source_primal_pass']=False;self.assertFalse(pair.tiny_pipeline_verified(bad))
        bad=copy.deepcopy(good);bad['B']['state']['trace'][-1]['check_selector']['loaded_python_modules']['fractional_separator']['sha256']='0'*64
        self.assertFalse(pair.tiny_pipeline_verified(bad))

    def test_integrity_failure_is_fail_closed_and_debited(self):
        class Backend:
            eligible=set()
            def start(self,state):pass
            def checkpoint(self,state):pass
            def stage(self,kind,active,allocation,debit,record):
                debit({'process_wall_seconds':3.25})
                raise pair.ContractError('Pinned artifact changed')
        state=pair.run_pipeline(Backend(),False,total=20.)
        self.assertTrue(state['stop_campaign']);self.assertEqual(state['failure_class'],'integrity_or_resource')
        self.assertEqual(state['budget']['solver_process_wall_seconds'],3.25)

    def test_tiny_failure_never_borrows_development_gate(self):
        fake={'tiny_pipeline_verified':False,'comparison':{'development_gate_pass':True}}
        with patch.object(pair,'run_pair',return_value=fake):
            self.assertEqual(pair.run_phase(Path('/mock'),'tiny'),1)

    def test_phase_marker_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(pair,'HERE',Path(tmp)),patch.object(pair,'runtime_manifest'),patch.object(pair,'sha',return_value='a'*64),patch.object(pair,'run_phase',return_value=0) as run,patch('sys.argv',['driver','--run-reviewed','--phase','tiny']):
            self.assertEqual(pair.main(),0)
            with self.assertRaises(pair.ContractError):pair.main()
            self.assertEqual(run.call_count,1)
            self.assertTrue((Path(tmp)/'run_v1/tiny.phase_receipt.json').exists())

    def test_normal_solver_timeout_retains_debit_without_integrity_stop(self):
        from test_contract import MockBackend,outcome
        result=outcome('mip',no_point=True,wall=20.1,killed=True)
        result['report']['bound_status_valid']=False
        state=pair.run_pipeline(MockBackend([result]),False,total=20.)
        self.assertFalse(state['complete']);self.assertFalse(state.get('stop_campaign',False))
        self.assertEqual(state['budget']['solver_process_wall_seconds'],20.1)

    def test_real_stage_timeout_censors_truncated_credit_after_debit(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend=pair.RuntimeBackend(Path(tmp),Path('/mock/source'),2,0,tiny=True,arm='B')
            record={};debits=[]
            def execute(command,log,env,watchdog):
                Path(log).write_text('truncated RootChildCredit trace')
                Path(command[-1]).write_text('partial solution being written at containment deadline')
                return {'returncode':-9,'hard_watchdog_killed':True,'process_wall_seconds':22.1}
            with patch.object(backend,'auxiliary',return_value={'objective_scope':'unchanged_original_source'}) as auxiliary,patch.object(pair,'verify'),patch.object(pair,'sha',return_value='a'*64),patch.object(pair,'execute',side_effect=execute),patch.object(pair,'solver_report',return_value={'status':None}),patch('credit_events.parse_credit_events',side_effect=ValueError('Incomplete main credit call')):
                result=backend.stage('mip',[],20.,debits.append,record)
            self.assertEqual(len(debits),1);self.assertEqual(debits[0]['process_wall_seconds'],22.1)
            self.assertFalse(record['root_child_credit_censored']['activation_eligible'])
            self.assertNotIn('root_child_credit',record);self.assertIsNone(result['check'])
            self.assertEqual(auxiliary.call_count,1);self.assertIn('solution_sha256',record)

    def test_three_cases_only(self):
        for date in policy.DATES:self.assertIn(date,str(contracts.source_case(date)))
        for invalid in ('2017-01-01','../2017-02-01',None):
            with self.assertRaises(contracts.ContractError):contracts.source_case(invalid)

    def test_reserved_order_and_per_date_paired_medians(self):
        expected=[('2017-11-01',1,'BA'),('2017-08-01',1,'AB'),('2017-02-01',3,'BA'),('2017-02-01',4,'AB'),('2017-11-01',2,'AB'),('2017-08-01',2,'BA'),('2017-08-01',3,'AB'),('2017-02-01',5,'BA'),('2017-11-01',3,'BA')]
        self.assertEqual(list(policy.CONFIRMATION),expected)
        records=[{**i,'comparison':{'valid_comparison':True,'metrics':{m:{'reduction_fraction':.35} for m in policy.METRICS}}} for i in policy.schedule()]
        self.assertTrue(policy.confirmation_gate(records)['passed'])
        self.assertFalse(policy.confirmation_gate(records[:-1])['passed'])
        for val in (0.,-.01,float('nan')):
            bad=copy.deepcopy(records);bad[0]['comparison']['metrics'][policy.METRICS[0]]['reduction_fraction']=val
            self.assertFalse(policy.confirmation_gate(bad)['passed'])
        bad=copy.deepcopy(records);bad[0]['seed']=2;self.assertFalse(policy.confirmation_gate(bad)['passed'])
        bad=copy.deepcopy(records)
        for i in (0,4):bad[i]['comparison']['metrics'][policy.METRICS[0]]['reduction_fraction']=.29
        self.assertFalse(policy.confirmation_gate(bad)['passed'])

class SelectorTests(unittest.TestCase):
    def plan(self):
        return {'arms':{k:policy.arm_record(k) for k in ('A','B')},
            'common_module_paths':{k:str(stage_child.HERE/(k+'.py')) for k in ('contracts','primal_and_bound','model_stage')},
            'separator_paths':{k:str(v) for k,v in stage_child.SEPARATORS.items()},
            'module_sha256':{**{str(stage_child.HERE/(k+'.py')):'a'*64 for k in ('contracts','primal_and_bound','model_stage')},
                             **{str(stage_child.SEPARATORS[k]):v for k,v in stage_child.HASHES.items()}}}
    def test_selector_paths_and_arm_records_fail_closed(self):
        plan=self.plan()
        for arm in ('A','B'):stage_child.validate_plan(plan,arm)
        cases=[]
        p=copy.deepcopy(plan);p['arms']['A']['lp_discovery']=True;cases.append(p)
        p=copy.deepcopy(plan);p['separator_paths']['B']='/tmp/arbitrary.py';cases.append(p)
        p=copy.deepcopy(plan);p['common_module_paths']['model_stage']='/tmp/other.py';cases.append(p)
        p=copy.deepcopy(plan);p['module_sha256'][str(stage_child.SEPARATORS['B'])]='0'*64;cases.append(p)
        for p in cases:
            with self.assertRaises(ValueError):stage_child.validate_plan(p,'B')
        with self.assertRaises(ValueError):stage_child.validate_plan(plan,'C')

    def test_exact_bytes_bypass_stale_pyc_and_reject_collision_or_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.py';path.write_text('value = "old"\n')
            py_compile.compile(str(path),doraise=True)
            stat=path.stat();path.write_text('value = "new"\n')
            import os
            os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
            digest=hashlib.sha256(path.read_bytes()).hexdigest();name='_combined_selector_mock'
            try:
                mod,receipt=stage_child.load_source(name,path,digest)
                self.assertEqual(mod.value,'new');self.assertEqual(receipt['sha256'],digest)
                with self.assertRaises(ValueError):stage_child.load_source(name,path,digest)
            finally:sys.modules.pop(name,None)
            with self.assertRaises(ValueError):stage_child.load_source(name,path,'0'*64)
            self.assertNotIn(name,sys.modules)

if __name__=='__main__':unittest.main()
