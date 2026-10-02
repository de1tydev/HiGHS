import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cold_screen_pair as pair

class PairPolicyTests(unittest.TestCase):
    def test_only_budget_boolean_differs_in_mip_options(self):
        off=pair.options_text('mip',False).splitlines();on=pair.options_text('mip',True).splitlines()
        difference=[(a,b) for a,b in zip(off,on) if a!=b]
        self.assertEqual(len(off),len(on));self.assertEqual(difference,[('mip_heuristic_near_target_root_budget = false','mip_heuristic_near_target_root_budget = true')])
        self.assertIn('mip_heuristic_near_target_root_budget_log = true',off)
        self.assertEqual(pair.options_text('lp',False),pair.options_text('lp',True))
        for bad in ('false',0,1,None):
            with self.assertRaises(pair.ContractError):pair.options_text('mip',bad)

    def test_real_arm_entries_use_fixed_lp_discovery(self):
        seen=[]
        class Backend:
            def __init__(self,out,source,hours,seed,*,tiny,arm):
                self.out=out;self.aux=[];self.tracked={};seen.append(('arm',arm))
            def checkpoint(self,state):
                (self.out/'summary.json').write_text(json.dumps(state))
        def pipeline(backend,discover,*,total):
            seen.append(('discovery',discover))
            return {'complete':False,'trace':[],'budget':{'lp_process_wall_seconds':0.,'solver_process_wall_seconds':0.}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(pair,'RuntimeBackend',Backend),patch.object(pair,'run_pipeline',pipeline):
            for arm in ('A','B'):pair.run_arm(Path(tmp)/arm,Path('/mock'),2,0,tiny=True,total=20.,arm=arm)
        self.assertEqual(seen,[('arm','A'),('discovery',False),('arm','B'),('discovery',True)])

    def test_math_completion_does_not_invent_mechanism(self):
        result={'B':{'state':{'complete':True,'trace':[]}},'A':{'state':{'complete':True,'trace':[]}}}
        self.assertFalse(pair.mechanism_summary(result)['candidate_mechanism_activated'])
        result['B']['state']['trace']=[{'kind':'mip','root_child_credit':{'call_count':2,'applied_caps':1,'applied_skips':0,'root_origins_observed':['root-reduced-cost','root-RENS']}}]
        self.assertTrue(pair.mechanism_summary(result)['candidate_mechanism_activated'])

    def test_cancelled_debit_survives_later_diagnostic_error(self):
        class Backend:
            eligible=set()
            def start(self,state):pass
            def checkpoint(self,state):pass
            def stage(self,kind,active,allocation,debit,record):
                debit({'process_wall_seconds':4.5,'interrupted':True})
                raise ValueError('Incomplete main credit call')
        state=pair.run_pipeline(Backend(),True,total=20.)
        self.assertFalse(state['complete']);self.assertTrue(state['interrupted'])
        self.assertEqual(state['budget']['solver_process_wall_seconds'],4.5)
        self.assertEqual(len(state['trace']),1)

    def test_stop_suppresses_counterpart_but_ordinary_incomplete_does_not(self):
        for flag,expected in (({'interrupted':True},1),({'stop_campaign':True},1),({},2)):
            state={'complete':False,'trace':[],**flag}
            with tempfile.TemporaryDirectory() as tmp,patch.object(pair,'runtime_manifest',return_value={'artifact_sha256':{}}),patch.object(pair,'sha',return_value='a'*64),patch.object(pair,'run_arm',return_value=(state,{})) as run:
                saved=pair.run_pair(Path(tmp)/'pair','tiny',0,'AB',tiny=True)
                self.assertEqual(run.call_count,expected);self.assertFalse(saved['comparison']['valid_comparison'])

if __name__=='__main__':unittest.main()
