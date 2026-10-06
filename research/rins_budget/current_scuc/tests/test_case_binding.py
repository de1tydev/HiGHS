"""Production helper tests with independent tiny arrays; standard library only."""
import ast
import copy
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest

from current_scuc import case_binding as cb
from current_scuc import zero_cost as zero
from current_scuc import preparation

def fixture(cost=-0.0):
    return {'Parameters':{'Time horizon (h)':3},'Generators':{
        'zero':{'Startup costs ($)':[cost],'Startup delays (h)':[1],'Initial status (h)':-2},
        'positive':{'Startup costs ($)':[2.0],'Startup delays (h)':[1],'Initial status (h)':-2}}}

def models():
    names=[f'{k}_{g}_{t}' for g in ('zero','positive') for t in range(3) for k in ('u','sc')]
    e={'num_col':len(names),'num_row':1,'col_names':names,'row_names':['source_name'],
        'col_lower':[0.]*len(names),'integrality':[int(n.startswith('u_')) for n in names]}
    r=copy.deepcopy(e);r['integrality']=[0]*len(names)
    return e,r

def hashes(e): return {'identity':cb.identity(e)}

def authority(source,o,r):
    return dict(source_object_sha256=cb.identity(source,source=True),
        original_model_hashes=hashes(zero.canonical(o)),retained_model_hashes=hashes(zero.canonical(r)))

class Contracts(unittest.TestCase):
    def test_positive_metadata_byte_equal(self):
        data=fixture(4.0);path=cb.source_path('first-start-complete-family-v1/cuts.py')
        nodes=[n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name in ('eligible_units','select')]
        ns=dict(F=Fraction,math=math,require=cb.require);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
        self.assertEqual(cb.identity(ns['select'](data)),cb.identity(zero.positive_rows(data)))

    def test_classification_retains_signed_zero(self):
        result=zero.classify(fixture())
        self.assertEqual((result['eligible_unit_count'],result['unit_count'],result['logical_prefix_count'],result['row_count'],result['zero_prefix_count']),(2,1,6,3,3))
        self.assertEqual(result['zero_units'][0]['C_hex'],'-0x0.0p+0')
        self.assertEqual(result['zero_omission_status'],'pending_independent_model_bound_certificate')

    def test_bad_source_always_fails(self):
        for value in (True,-1.,math.inf,math.nan,'0',None):
            d=fixture(value);d['Generators']['zero']['Initial status (h)']=2
            with self.subTest(value=value),self.assertRaises((ValueError,TypeError)):
                zero.classify(d)
        for value in (0,True,-2.0):
            d=fixture();d['Generators']['zero']['Initial status (h)']=value
            with self.assertRaises(ValueError):zero.classify(d)

    def test_exact_omission_certificate(self):
        d=fixture();o,r=models();a=authority(d,o,r);c=zero.certify(d,o,r,a,hashes)
        self.assertEqual(c['certified_omitted_prefixes'],3)
        self.assertEqual(c['rows'][2]['row_terms'],[[f'sc_zero_{t}',['1','1']] for t in range(3)])
        self.assertEqual(zero.verify_certificate(c,d,o,r,a,hashes),c)
        self.assertTrue(all(not row['has_u_term'] for row in c['rows']))

    def test_authority_and_receipt_tampering(self):
        d=fixture();o,r=models();a=authority(d,o,r);c=zero.certify(d,o,r,a,hashes)
        for value in (1.,-math.nextafter(0.,1.),math.inf):
            bad=copy.deepcopy(o);bad['col_lower'][1]=value
            with self.assertRaises(ValueError):zero.certify(d,bad,r,authority(d,bad,r),hashes)
        bad=copy.deepcopy(r);bad['col_lower'][1]=-0.0
        with self.assertRaises(ValueError):zero.certify(d,o,bad,authority(d,o,bad),hashes)
        bad=copy.deepcopy(r);bad['integrality'][1]=1
        with self.assertRaises(ValueError):zero.certify(d,o,bad,authority(d,o,bad),hashes)
        bad=copy.deepcopy(c);bad['rows'][2]['bounds'].pop()
        with self.assertRaises(ValueError):zero.verify_certificate(bad,d,o,r,a,hashes)
        bad=copy.deepcopy(c);bad['rows'][0]['row_terms'][0][1]=['2','1']
        with self.assertRaises(ValueError):zero.verify_certificate(bad,d,o,r,a,hashes)
        bad=copy.deepcopy(r);bad['col_names'][1]='renamed'
        with self.assertRaises(ValueError):zero.certify(d,o,bad,a,hashes)


    def test_no_native_or_scientific_imports(self):
        import subprocess
        result=subprocess.run([sys.executable,'-B','-c',
            "import sys; from current_scuc import case_binding, zero_cost, preparation, binding, case, heldout; "
            "assert not [n for n in sys.modules if n.split('.')[0] in ('numpy','scipy','ctypes')]"],
            capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_production_horizon_cannot_be_disabled_implicitly(self):
        with self.assertRaisesRegex(ValueError,'Source horizon'):
            cb.source_contract(fixture())

    def test_local_source_record_has_no_historical_root_requirement(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.json';path.write_text('{}')
            self.assertEqual(cb.check_record(cb.record(path)),path)
            path.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError,'File hash changed'):
                cb.check_record({'path':str(path),'sha256':'a'*64})

    def test_duplicate_and_nonfinite_state_json_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            for payload in ('{"a":1,"a":2}','{"value":NaN}','{"value":1e1000}'):
                path.write_text(payload)
                with self.assertRaises(ValueError):cb.read(path)

    def test_preparation_keeps_worker_and_common_caps(self):
        self.assertEqual(cb.CAPS['worker_seconds'],300)
        self.assertEqual(cb.CAPS['preparation_seconds'],600)
        self.assertEqual(cb.CAPS['whole_seconds'],1800)


if __name__=='__main__':unittest.main()
