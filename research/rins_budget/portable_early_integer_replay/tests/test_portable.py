import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'payload/combined_screening_driver'))
sys.path.insert(0,str(ROOT/'payload/canonical_mps_export'))
from io_announcements import filter_known_io,READ,WRITE,SET_SOLUTION
from consumer_launch import arm_order,compare
from verify_run import persisted_check,stage_evidence
from common import ContractError,sha,write_json,BINARY

class Tests(unittest.TestCase):
    def test_fixed_pair_orders_and_no_incomplete_ratios(self):
        orders=[arm_order(d,s,'pair') for d in ['2017-05-01','2017-06-01','2017-09-01'] for s in [211,212,213]]
        self.assertEqual(orders,[['A','early_candidate'] if i%2==0 else ['early_candidate','A'] for i in range(9)])
        self.assertEqual(arm_order(None,0,'pair',tiny=True),['A','early_candidate'])
        self.assertFalse(compare({'A':{'complete':True}})['valid_pair'])
        self.assertFalse(compare({'A':{'complete':True},'early_candidate':{'complete':False}})['valid_pair'])

    def test_exact_keyword_io_only_and_absent_point_transition(self):
        with tempfile.TemporaryDirectory(prefix='integer_warning_') as tmp:
            model=Path(tmp)/'master.mps';solution=Path(tmp)/'solution.sol';model.write_text('model');solution.write_text('point')
            text=READ+str(model)+'\nStatus unchanged\n'+WRITE+str(solution)+'\n'
            filtered,evidence=filter_known_io(text,model,solution,solver=True)
            self.assertEqual(filtered,'Status unchanged\n');self.assertEqual(len(evidence['excluded_lines']),2)
            solution.unlink()
            self.assertEqual(filter_known_io(READ+str(model)+'\nTime limit reached\n',model,solution,solver=True)[0],'Time limit reached\n')
            self.assertEqual(filter_known_io('Time limit reached\n',model,solution,solver=True)[0],'Time limit reached\n')
            with self.assertRaises(ValueError):filter_known_io(text,model,solution,solver=True)

    def test_duplicate_foreign_prefixed_suffixed_and_real_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'master.mps';solution=Path(tmp)/'solution.sol';model.write_text('m');solution.write_text('s')
            read=READ+str(model);write=WRITE+str(solution)
            for text in [read+'\n'+read+'\n',write+'\n'+write+'\n',read+' extra\n','WARNING: '+write+'\n',WRITE+str(solution)+'-foreign\n']:
                with self.assertRaises(ValueError):filter_known_io(text,model,solution,solver=True)
            text=read+'\nWARNING: model error\nERROR: invalid row\n'+write+'\n'
            filtered,_=filter_known_io(text,model,solution,solver=True)
            self.assertIn('WARNING: model error',filtered);self.assertIn('ERROR: invalid row',filtered)
            # C API readback does not require/write a solution; its remaining broad scan still sees errors.
            filtered,_=filter_known_io(read+'\nWARNING: coefficient dropped\n',model)
            self.assertEqual(filtered,'WARNING: coefficient dropped\n')
            with self.assertRaises(ValueError):filter_known_io(write+'\n',model)


    def test_exact_option_echo_does_not_assert_point_exists(self):
        with tempfile.TemporaryDirectory(prefix='integer_warning_error_') as tmp:
            model=Path(tmp)/'master.mps';model.write_text('model');solution=Path(tmp)/'absent.sol'
            echo=SET_SOLUTION+'"'+str(solution)+'"'
            self.assertEqual(filter_known_io(echo+'\nTime limit reached\n',model,solution,solver=True)[0],'Time limit reached\n')
            for text in [echo+'\n'+echo+'\n', 'WARNING: '+echo+'\n', echo+' suffix\n', SET_SOLUTION+'"'+str(solution)+'-foreign"\n']:
                with self.assertRaises(ValueError):filter_known_io(text,model,solution,solver=True)
            filtered,_=filter_known_io(echo+'\nWARNING: integer model invalid\n',model,solution,solver=True)
            self.assertEqual(filtered,'WARNING: integer model invalid\n')
            with self.assertRaises(ValueError):filter_known_io(echo+'\n',model)

    def test_raw_check_not_mutable_summary_supplies_upper(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd=Path(tmp);raw=dict(primal_present=True,checked_upper=100.,upper_bound_eligible=True,certificate_bound_eligible=False,full_source_primal_pass=True)
            write_json(rd/'check.json',raw,fresh=True);artifact=dict(path=str(rd/'check.json'),sha256=sha(rd/'check.json'))
            stage=dict(role='integer_proof',check=dict(raw,check_artifact=artifact))
            self.assertEqual(persisted_check(stage,rd),raw)
            bad=copy.deepcopy(stage);bad['check']['checked_upper']=200.
            with self.assertRaises(ContractError):persisted_check(bad,rd)
            discovery=dict(role='integer_discovery',check=dict(raw,check_artifact=artifact,role='integer_discovery',
                upper_bound_eligible=False,certificate_bound_eligible=False,checked_upper=None,discovery_source_secure=True))
            self.assertEqual(persisted_check(discovery,rd),raw)
            discovery['check']['upper_bound_eligible']=True
            with self.assertRaises(ContractError):persisted_check(discovery,rd)

    def test_measurement_and_before_solve_seed_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            arm=Path(tmp);rd=arm/'01_integer_proof';rd.mkdir();role='integer_proof';model=rd/'master.mps';sol=rd/'solution.sol';options=arm/(role+'.options')
            command=[str(BINARY),str(model),'--options_file',str(options),'--time_limit','600','--random_seed','211','--solution_file',str(sol)]
            before=dict(role=role,allocation=600.,solver_command=command)
            write_json(rd/'record.before_solve.json',before,fresh=True)
            measured={'process_wall_seconds':.1};write_json(rd/'measurement.json',measured,fresh=True)
            stage=dict(before,solver=measured,record_sha256_before_solve=sha(rd/'record.before_solve.json'),record_before_solve_path=str(rd/'record.before_solve.json'))
            write_json(rd/'record.json',stage,fresh=True);stage_evidence(stage,rd,arm,{'seed':211})
            changed=copy.deepcopy(stage);changed['solver']={'process_wall_seconds':.2}
            with self.assertRaises(ContractError):stage_evidence(changed,rd,arm,{'seed':211})
            with self.assertRaises(ContractError):stage_evidence(stage,rd,arm,{'seed':212})

    def test_readback_math_unchanged_and_filter_is_narrow(self):
        # API fidelity still compares all sixteen fields; compatibility adds diagnostic evidence only.
        source=(ROOT/'payload/canonical_mps_export/readback.py').read_text()
        self.assertIn('np.array_equal(a, b)',source)
        self.assertIn('if loaded["read_status"] != 0:',source)
        self.assertIn('diagnostic_text,io_evidence=io_filter.filter_known_io(log,path)',source)
        self.assertIn('"io_announcement_filter": loaded["io_announcement_filter"]',source)

if __name__=='__main__':unittest.main()
