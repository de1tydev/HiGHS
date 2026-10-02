"""Source/mock-only tests: no optimizer, generator, real API, or factorization."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from contracts import *
from cold_screen_pair import run_pipeline,options_text,compare_pair,RuntimeBackend
from primal_and_bound import *
from model_stage import accept_api,pack_expected
import model_stage

def expected():
    return dict(num_col=2,num_row=1,num_nz=2,sense=1,offset=0.,col_names=['u','p'],row_names=['R0'],
                col_lower=[0.,0.],col_upper=[1.,10.],col_cost=[0.,1.],row_lower=[0.],row_upper=[0.],
                integrality=[1,0],a_start=[0,1,2],a_index=[0,0],a_value=[-10.,1.])

def primal(rows='u 1\np 10\n',objective='10',tail='# Rows 1\nR0 0\n'):
    return 'Model status\nOptimal\n\n# Primal solution values\nFeasible\nObjective '+objective+'\n# Columns 2\n'+rows+tail+'\n# Dual solution values\nNone\n'

def good_bound(value=99.5):
    raw=str(value)
    identity={key:'a'*64 for key in ('source_sha256','model_sha256','expected_sha256','pair_manifest_sha256','api_report_sha256',
              'options_sha256','executable_sha256','generator_sha256','checker_sha256','runtime_manifest_sha256')}
    identity.update(kind='mip',objective_scope='unchanged_original_source',model_path='/mock/master.mps',stage_directory='/mock')
    return dict(scope=MIP_SCOPE,bound_status_valid=True,certificate_bound_eligible=True,
                master_identity=identity,
                status='Optimal',printed_lower=value,raw_lower_token=raw,lower_rounding_allowance=allowance(value,raw),
                global_lower=value-allowance(value,raw),clean_return=True,loaded_library_identity_valid=True,
                identities_valid=True,parent_report_identity_valid=True,model_definition_diagnostics=[])

def outcome(kind,new=(),*,upper=None,wall=.5,no_point=False,killed=False):
    report=good_bound()
    if kind=='lp': report.update(scope=LP_SCOPE,bound_status_valid=False,certificate_bound_eligible=False,global_lower=None)
    report['usable_status']=not killed
    return {'wall':wall,'killed':killed,'report':report,'check':None if no_point else dict(kind=kind,primal_present=True,
        matrix_check={'passed':True},new_pairs=[list(p) for p in new],upper_bound_eligible=upper is not None,
        certificate_bound_eligible=False,full_source_primal_pass=upper is not None,checked_upper=upper)}

class MockBackend:
    eligible={(0,1),(2,1)}
    def __init__(self,outcomes): self.outcomes=iter(outcomes);self.calls=[];self.snapshots=[]
    def start(self,state): assert state['initial_pairs']==[]
    def checkpoint(self,state): self.snapshots.append(copy.deepcopy(state))
    def stage(self,kind,active,allocation,debit,record):
        self.calls.append((kind,active,allocation));result=copy.deepcopy(next(self.outcomes))
        debit({'process_wall_seconds':result.pop('wall'),'returncode':0,'hard_watchdog_killed':result.pop('killed')})
        return result

class PrimalTests(unittest.TestCase):
    def test_valid_names_and_duals(self):
        self.assertEqual(read(primal())['values'],{'u':1.,'p':10.})
    def test_none_never_reads_dual(self):
        text='Model status\nTime limit reached\n# Primal solution values\nNone\n# Dual solution values\nFeasible\n# Columns 2\nu 1\np 10\n'
        self.assertIsNone(parse_primal_text(text,['u','p']))
    def test_malformed_variants(self):
        invalid=[primal('u 1\nu 10\n'),primal('u 1\n'),primal('u 1\np 10\nq 2\n'),
                 primal('q 1\np 10\n'),primal('u nan\np 10\n'),primal(objective='inf'),
                 primal().replace('# Columns 2','# Columns 3'),primal().replace('# Primal solution values','# Other'),
                 primal().replace('Feasible','Infeasible'),primal()+'# Primal solution values\nNone\n',
                 primal().split('# Rows')[0].rstrip('\n')]
        for text in invalid:
            with self.subTest(text=text),self.assertRaises(ContractError): parse_primal_text(text,['u','p'])

def read(text): return parse_primal_text(text,['u','p'])

class MatrixTests(unittest.TestCase):
    def setUp(self): self.identity={key:'a'*64 for key in ('source_sha256','model_sha256','expected_sha256','solution_sha256','pair_manifest_sha256')}
    def test_fractional_only_continuous(self):
        e=expected();x={'u':.5,'p':5.}
        self.assertFalse(matrix_check(e,x,'mip',self.identity)['passed'])
        e['integrality']=[0,0]
        r=matrix_check(e,x,'lp',self.identity)
        self.assertTrue(r['passed']);self.assertEqual(r['linear_objective'],5.)
        with self.assertRaises(ContractError): matrix_check(e,x,'mip',self.identity)
    def test_row_bounds_names_and_nonfinite(self):
        e=expected()
        for x in ({'u':1.,'p':9.},{'u':2.,'p':20.}): self.assertFalse(matrix_check(e,x,'mip',self.identity)['passed'])
        for x in ({'u':1.,'q':10.},{'u':1.,'p':math.nan}):
            with self.assertRaises(ContractError): matrix_check(e,x,'mip',self.identity)
    def test_all_field_lp_integer_identity(self):
        e=expected();lp=copy.deepcopy(e);lp['integrality']=[0,0];check_lp_integer_difference(e,lp)
        for key in FIDELITY_FIELDS-{'integrality'}:
            altered=copy.deepcopy(lp)
            if isinstance(altered[key],list): altered[key]=altered[key]+[0]
            else: altered[key]+=1
            with self.subTest(field=key),self.assertRaises(ContractError): check_lp_integer_difference(e,altered)
    def test_fixed_bounds_survive_transform(self):
        e=expected();e['col_lower'][0]=1.;lp=copy.deepcopy(e);lp['integrality']=[0,0]
        check_lp_integer_difference(e,lp)
        self.assertFalse(matrix_check(lp,{'u':0.,'p':0.},'lp',self.identity)['passed'])

class BoundTests(unittest.TestCase):
    def log(self,body='  Model master\n  Status Optimal\n  Dual bound 99.5\n'):
        return 'calling init: '+str(LIBRARY)+'\ncalling init: '+str(EXTRAS_LIBRARY)+'\nSolving report\n'+body
    def report(self,log,kind='mip',**measurement):
        return solver_report(log,dict(returncode=0,hard_watchdog_killed=False,**measurement),kind,'master.mps',LIBRARY,identities_valid=True)
    def test_only_exact_final_top_level_master(self):
        valid=self.report(self.log());self.assertTrue(valid['bound_status_valid'])
        for body in ('  Model child\n  Status Optimal\n  Dual bound 99.5\n','  Model master\n  Status Optimal\n  Dual bound nan\n',
                     '  Model master\n  Status Optimal\n  Dual bound 99.5\n  Dual bound 99.6\n',
                     '  Model master\n  Status Infeasible\n  Dual bound 99.5\n'):
            self.assertFalse(self.report(self.log(body))['bound_status_valid'])
        child=self.log()+'Solving report\n  Model child\n  Status Optimal\n  Dual bound 150\n'
        self.assertFalse(self.report(child)['bound_status_valid'])
    def test_lp_bound_impossible(self):
        r=self.report(self.log()+'Model status : Optimal\n','lp')
        self.assertFalse(r['bound_status_valid']);self.assertIsNone(r['global_lower'])
        self.assertFalse(certificate(100.,[r],Budget().record())['valid'])
    def test_definition_and_dso_fail(self):
        for suffix in ('WARNING: matrix coefficients ignored\n','ERROR: bound missing\n'):
            self.assertFalse(self.report(self.log()+suffix)['bound_status_valid'])
        self.assertFalse(self.report(self.log().replace(str(LIBRARY),'/tmp/other/libhighs.so'))['bound_status_valid'])
        self.assertFalse(self.report(self.log().replace(str(EXTRAS_LIBRARY),'/tmp/other/libhighs_extras.so'))['bound_status_valid'])
        self.assertFalse(self.report(self.log().replace('calling init: '+str(EXTRAS_LIBRARY)+'\n',''))['bound_status_valid'])
        self.assertEqual(definition_diagnostics('P-D objective error : 1e-12'),[])
    def test_allowance_negative_gap_and_budget(self):
        ledger=Budget().record();self.assertTrue(certificate(100.,[good_bound()],ledger)['complete'])
        self.assertFalse(certificate(90.,[good_bound()],ledger)['valid'])
        b=good_bound();b['lower_rounding_allowance']*=2
        self.assertFalse(certificate(100.,[b],ledger)['valid'])
        ledger['in_budget']=False;self.assertFalse(certificate(100.,[good_bound()],ledger)['complete'])
        ledger['in_budget']=True;ledger['lp_policy_valid']=False
        self.assertFalse(certificate(100.,[good_bound()],ledger)['complete'])
    def test_prior_master_provenance_is_retained(self):
        earlier=good_bound(99.8);earlier['master_identity']['stage_directory']='/mock/earlier'
        later=good_bound(99.5)
        c=certificate(100.,[earlier,later],Budget().record())
        self.assertEqual(c['lower_provenance']['master_identity']['stage_directory'],'/mock/earlier')
        del earlier['master_identity']['pair_manifest_sha256']
        self.assertFalse(certificate(100.,[earlier,later],Budget().record())['valid'])

class ApiGateTests(unittest.TestCase):
    def report(self):
        digest='a'*64
        symbols={key:dict(path=str(LIBRARY.resolve()),sha256=digest) for key in
                 ('Highs_create','Highs_readModel','Highs_getLp','Highs_getColName','Highs_getRowName')}
        return dict(source_sha256=digest,mps_sha256=digest,expected_sha256=digest,pair_manifest_sha256=digest,
                    hours=2,kind='lp',library_path=str(LIBRARY.resolve()),library_sha256=digest,checker_sha256=digest,
                    passed=True,read_status=0,failures=[],diagnostics=[],hessian_num_nz=0,optimization_or_presolve_called=False,
                    highs_int_bytes=4,fields={key:{'passed':True} for key in FIDELITY_FIELDS},loaded_symbol_provenance=symbols,
                    log_path=str(Path('/tmp/model.mps.readback.log').resolve()),log_sha256=digest,bound_record_audit={'columns':2})
    def check(self,report):
        with patch('model_stage.sha',return_value='a'*64):
            return accept_api(report,'/tmp/model.mps','/tmp/e.json','/tmp/s.json','/tmp/p.json',2,'lp')
    def test_complete_exact_report(self): self.check(self.report())
    def test_every_field_and_identity_required(self):
        for field in FIDELITY_FIELDS:
            r=self.report();del r['fields'][field]
            with self.subTest(field=field),self.assertRaises(ContractError): self.check(r)
        for key in ('source_sha256','mps_sha256','expected_sha256','pair_manifest_sha256','library_sha256','checker_sha256','hours','kind'):
            r=self.report();r[key]='changed'
            with self.subTest(identity=key),self.assertRaises(ContractError): self.check(r)
    def test_loader_drop_and_symbol_substitution(self):
        variants=[]
        r=self.report();r['diagnostics']=['tiny matrix dropped'];variants.append(r)
        r=self.report();r['read_status']=1;variants.append(r)
        r=self.report();r['loaded_symbol_provenance']['Highs_readModel']['path']='/tmp/other.so';variants.append(r)
        for r in variants:
            with self.assertRaises(ContractError): self.check(r)

class SourceWrapperTests(unittest.TestCase):
    def invoke(self,kind='mip',*,violation=True,fractional=False,nonsecurity=False,numpy_measurements=False):
        digest='a'*64;e=expected()
        if kind=='lp': e['integrality']=[0,0]
        values={'u':.5,'p':5.} if fractional else {'u':1.,'p':10.}
        cost=values['p'];new=[[0,1]] if violation else []
        categories={'emergency_line_limit':1} if violation else {}
        if nonsecurity: categories['ramp_up']=1
        source=dict(violations_by_category=categories,security={'violated_pairs':[(0,1)] if violation else [],'outages_checked':1,
                    'max_violation_after_shared_slack_MW':1. if violation else 0.,'max_unrelaxed_overload_MW':1. if violation else 0.},
                    source_sha256=digest,solution_sha256=digest,hours=2,mode='n1',tolerance=TOLERANCE,
                    pass_primal=not categories,linear_model_cost=cost,true_source_cost=cost,objective_overpayment=0.,total_shed_MWh=0.,
                    max_overflow_MW=0.,base_unrelaxed_overload_MW=0.,max_violation_by_category={'emergency_line_limit':1.} if violation else {})
        if numpy_measurements:
            import numpy as np
            source['base_unrelaxed_overload_MW']=np.float64(4.092726157978177e-12)
            source['max_violation_by_category']['system_balance']=np.float64(2e-12)
        meta=dict(input_sha256=digest,mps_sha256=digest,expected_sha256=digest,pair_manifest_sha256=digest,
                  readback_sha256=digest,hours=2,kind=kind,api_fidelity_verified=True,objective_scope='unchanged_original_source')
        def load(path):
            name=str(path)
            if name.endswith('.meta.json'): return meta
            if name.endswith('.expected.json'): return pack_expected(e)
            if name=='pairs.json': return []
            return {}
        with ExitStack() as stack:
            for name,value in [('runtime_manifest',{}),('sha',digest),('accept_api',{}),('source_data',{}),
                               ('read_primal',dict(values=values,printed_objective=cost,status='Optimal'))]:
                stack.enter_context(patch('model_stage.'+name,return_value=value))
            stack.enter_context(patch('model_stage.read_json',side_effect=load))
            checker=stack.enter_context(patch('model_stage.module',return_value=SimpleNamespace(check=lambda *args:source)))
            stack.enter_context(patch('fractional_separator.source_scope',return_value={'eligible_pairs':[[0,1]],'checked_outage_ids':['c']}))
            stack.enter_context(patch('fractional_separator.source_data_sha256',return_value=digest))
            separation={'violated_pairs':new,'checked_outage_ids':['c']}
            stack.enter_context(patch('fractional_separator.separate',return_value=separation))
            stack.enter_context(patch('fractional_separator.separate_integer_network',return_value=separation))
            result=model_stage.check('source.json',2,'pairs.json',kind,'master.mps','solution.sol')
            return result,checker.call_count
    def test_frozen_tuple_violation_continues_screening(self):
        result,calls=self.invoke()
        self.assertEqual(result['new_pairs'],[[0,1]]);self.assertFalse(result['upper_bound_eligible']);self.assertEqual(calls,1)
    def test_secure_integer_uses_both_checks(self):
        result,calls=self.invoke(violation=False)
        self.assertTrue(result['full_source_primal_pass']);self.assertEqual(result['checked_upper'],10.);self.assertEqual(calls,1)
    def test_fractional_lp_never_integer_checked(self):
        result,calls=self.invoke('lp',fractional=True)
        self.assertFalse(result['upper_bound_eligible']);self.assertEqual(calls,0)
    def test_fractional_mip_and_nonsecurity_fail(self):
        with self.assertRaises(ContractError): self.invoke(fractional=True)
        with self.assertRaises(ContractError): self.invoke(nonsecurity=True)
    def test_trusted_numpy_base_and_residual_cross_boundary(self):
        r,calls=self.invoke(violation=False,numpy_measurements=True)
        self.assertTrue(r['full_source_primal_pass']);self.assertEqual(calls,1)
        self.assertIs(type(r['source_check']['base_unrelaxed_overload_MW']),float)
        self.assertEqual(r['source_check']['base_unrelaxed_overload_MW'],4.092726157978177e-12)
        self.assertIs(type(r['source_check']['max_violation_by_category']['system_balance']),float)
        self.assertEqual(len(r['source_scalar_normalizations']),2)

class TrustedScalarTests(unittest.TestCase):
    def raw(self):
        return dict(linear_model_cost=10.,true_source_cost=10.,objective_overpayment=0.,total_shed_MWh=0.,
                    max_overflow_MW=0.,base_unrelaxed_overload_MW=0.,pass_primal=True,hours=2,
                    max_violation_by_category={'base':0.},security={'outages_checked':1,'violated_pairs':[],
                    'max_violation_after_shared_slack_MW':0.,'max_unrelaxed_overload_MW':0.})
    def test_finite_numpy_real_only_and_no_input_mutation(self):
        import numpy as np
        for value in (np.float64(4.092726157978177e-12),np.float32(.125),np.int64(2)):
            raw=self.raw();raw['base_unrelaxed_overload_MW']=value
            normalized,changes=model_stage.normalize_source_measurements(raw)
            self.assertIs(raw['base_unrelaxed_overload_MW'],value)
            self.assertIs(type(normalized['base_unrelaxed_overload_MW']),float)
            self.assertEqual(normalized['base_unrelaxed_overload_MW'],float(value))
            self.assertIs(normalized['pass_primal'],True);self.assertIs(type(normalized['hours']),int)
            self.assertEqual(len(changes),1)
            self.assertFalse(finite(value))  # External contracts remain exact builtins.
    def test_reject_nonfinite_bool_complex_arrays_and_coercibles(self):
        import numpy as np
        class Coercible:
            def __float__(self): return 1.
        invalid=(True,False,np.bool_(True),np.bool_(False),1+0j,np.complex128(1),np.array(1.),np.array([1.]),
                 '1.0',Coercible(),float('nan'),float('inf'),-float('inf'),np.float64('nan'),np.float64('inf'),np.float64('-inf'))
        for location in ('base','residual','security'):
            for value in invalid:
                raw=self.raw()
                if location=='base': raw['base_unrelaxed_overload_MW']=value
                elif location=='residual': raw['max_violation_by_category']['base']=value
                else: raw['security']['max_unrelaxed_overload_MW']=value
                with self.subTest(location=location,type=type(value)),self.assertRaises(ContractError):
                    model_stage.normalize_source_measurements(raw)

class ControlTests(unittest.TestCase):
    def test_tiny_containment_leaves_production_unchanged(self):
        tiny=RuntimeBackend('/mock','/mock/source',2,0,tiny=True)
        full=RuntimeBackend('/mock','/mock/source',36,0)
        self.assertEqual((tiny.mip_grace,tiny.aux_watchdog),(2.,20.))
        self.assertEqual((full.mip_grace,full.aux_watchdog),(60.,120.))
        ledger=Budget(20.);ledger.debit('lp',10.,{'process_wall_seconds':8.})
        self.assertEqual(ledger.allocation('mip'),12.)
    def test_standalone_comparison_charges_common_setup(self):
        results={name:{'state':{'complete':True},'receipt':{
            'standalone_equivalent_e2e_seconds':elapsed+30.,'solver_process_wall_seconds':solver}}
            for name,elapsed,solver in [('A',100.,100.),('B',75.,75.)]}
        r=compare_pair(results)
        self.assertFalse(r['development_gate_pass'])  # 25% raw-arm gain, only 19.23% with common setup.
        self.assertAlmostEqual(r['metrics']['standalone_equivalent_e2e_seconds']['reduction_fraction'],25/130)
        results['A']['state']['complete']=False
        self.assertFalse(compare_pair(results)['valid_comparison'])
    def test_baseline_is_empty_and_integer_reseparates(self):
        b=MockBackend([outcome('mip',[(0,1)]),outcome('mip',upper=100.)]);r=run_pipeline(b,False)
        self.assertTrue(r['complete']);self.assertEqual(b.calls[0][1],[]);self.assertEqual(b.calls[1][1],[[0,1]])
    def test_candidate_lp_seed_and_mip_must_reseparate(self):
        b=MockBackend([outcome('lp',[(0,1)]),outcome('lp'),outcome('mip',[(2,1)]),outcome('mip',upper=100.)]);r=run_pipeline(b,True)
        self.assertTrue(r['complete']);self.assertEqual(r['lp_seed_pairs'],[[0,1]])
        self.assertEqual(b.calls[-1][1],[[0,1],[2,1]])
    def test_no_primal_lp_falls_back(self):
        b=MockBackend([outcome('lp',no_point=True,wall=3.),outcome('mip',upper=100.)]);r=run_pipeline(b,True)
        self.assertTrue(r['complete']);self.assertEqual(b.calls[1],('mip',[],597.))
    def test_lp_three_solve_limit(self):
        b=MockBackend([outcome('lp',[(0,1)]),outcome('lp',[(2,1)]),outcome('lp'),outcome('mip',upper=100.)]);r=run_pipeline(b,True)
        self.assertEqual(r['budget']['lp_calls'],3);self.assertTrue(r['complete'])
    def test_no_mip_primal_no_upper(self):
        r=run_pipeline(MockBackend([outcome('mip',no_point=True)]),False)
        self.assertFalse(r['complete']);self.assertNotIn('best_integer_point',r)
    def test_fractional_source_upper_rejected(self):
        r=run_pipeline(MockBackend([outcome('lp',upper=100.)]),True)
        self.assertFalse(r['complete']);self.assertIn('Fractional LP',r['reason'])
    def test_active_pair_and_duplicate_fail(self):
        for new in ([(0,1)],[(2,1),(2,1)]):
            r=run_pipeline(MockBackend([outcome('lp',[(0,1)]),outcome('lp',new)]),True)
            self.assertFalse(r['complete'])
    def test_cap_overshoot_is_not_clipped(self):
        b=MockBackend([outcome('lp',no_point=True,wall=10.02,killed=True),outcome('mip',upper=100.)]);r=run_pipeline(b,True)
        self.assertEqual(r['budget']['lp_process_wall_seconds'],10.02);self.assertFalse(r['complete'])
        self.assertAlmostEqual(b.calls[-1][2],589.98)
    def test_global_actual_wall_includes_grace(self):
        r=run_pipeline(MockBackend([outcome('mip',upper=100.,wall=600.01)]),False)
        self.assertFalse(r['complete']);self.assertEqual(r['budget']['solver_process_wall_seconds'],600.01)
    def test_failure_after_debit_preserves_cost(self):
        class Failing(MockBackend):
            def stage(self,k,a,allocation,debit,rec):
                debit({'process_wall_seconds':4.5});raise ContractError('model mutated')
        r=run_pipeline(Failing([]),True)
        self.assertEqual(r['budget']['solver_process_wall_seconds'],4.5);self.assertFalse(r['complete'])
    def test_budget_limits_and_both_mip_options(self):
        b=Budget(12.);self.assertEqual(b.allocation('lp'),10.)
        b.debit('lp',10.,{'process_wall_seconds':8.});self.assertEqual(b.allocation('lp'),4.)
        self.assertIn('mip_initial_root_ipx = false',options_text('mip'))
        self.assertIn('mip_rel_gap = 0.01',options_text('mip'))
    def test_pair_json_and_provenance_guards(self):
        for raw in (None,[[0,1],[0,1]],[[2,1],[0,1]],[[True,1]],[[99,1]]):
            with self.assertRaises(ContractError): pairs(raw,MockBackend.eligible)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'pin';p.write_text('old');pins={str(p):sha(p)};verify(pins);p.write_text('new')
            with self.assertRaises(ContractError): verify(pins)

if __name__=='__main__': unittest.main(verbosity=2)
