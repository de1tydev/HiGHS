#!/usr/bin/env python3
"""Bounded resource-only tests; no optimizer/model/physical modules are loaded."""
import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_AS, (7*1024**3,)*2)
resource.setrlimit(resource.RLIMIT_FSIZE, (512*1024**2,)*2)
assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import struct
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',required=True,type=Path)
parser.add_argument('--saved-physical',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args()
PUBLIC=args.baseline.resolve(); SAVED=args.saved_physical.resolve(); HERE=args.out.resolve()
assert not HERE.is_relative_to(ROOT), 'Test outputs must be outside the source bundle'
HERE.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT))
from current_scuc.core.driver import witness_store as proposed
from current_scuc.core.driver import pair_codec
from tests.fixed_triangle import fixture, FULL_TINY_PAIRS

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

original = load('current_scuc.core.driver._baseline_witness', PUBLIC/'current_scuc/core/driver/witness_store.py')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
started = time.monotonic()
WORK = HERE/'sqlite-tests-run01'
WORK.mkdir(exist_ok=False)
report = dict(schema='current-scuc-resource-revision-sqlite-equivalence/v1', source_revision='portable-resource-v2',
              physical_or_optimizer_executed=False, tests=[], sources={})
for role, path in [('original', Path(original.__file__)), ('proposed', Path(proposed.__file__)), ('fixed_tiny', ROOT/'tests/fixed_triangle.py')]:
    report['sources'][role] = dict(path=str(path), sha256=sha(path))

def check(name, result):
    assert result, name
    report['tests'].append(dict(name=name, passed=True))

def normalized(manifest):
    return {k: {field:value for field,value in row.items() if field != 'path'} for k,row in manifest.items()}

# Serialization-only records over the pre-existing fixed triangle scope; none
# claim to have been produced by a physical calculation or an optimizer.
data, unused = fixture()
scope = pair_codec.descriptor(dict(lines=list(data['Transmission lines']), rated_line_indices=[0,1],
    outage_indices=[0,1,2], checked_outage_ids=list(data['Contingencies']), outage_line_ids=['l0','l1','l2'],
    hours=2, eligible_pair_count=4, source_data_sha256=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()), [2,2,0])
values=[(-0.0, 1.2345678901234567, .25, 0., 1.2345678901234567),
        (1e-12, -1e100, .125, 0., 1e100), (1e-5, 1e-300, .25, -0.0, 1e-300),
        (2., -2.25, .25, .25, 2.)]
records=[]
for j,(i,k) in enumerate(FULL_TINY_PAIRS):
    records.append(dict(pair=[i,k], monitored_line_id=f'l{i}', outage_id=f'c{k}', outage_line_id=f'l{k}', hour=j%2,
        **dict(zip(original._NUMERIC_FIELDS,values[j]))))
report['tiny_input'] = dict(scope=scope, records=records, nature='Fixed serialization records, not numerical physical results')

for case, seq in [('empty',[]),('complete_outage_major',[records[j] for j in [2,0,1,3]]),('complete_reverse',list(reversed(records))),('subset',[records[3],records[0]])]:
    results=[]; query_results=[]
    for mode,module in [('file',original),('memory',proposed)]:
        sink=module.WitnessSink(WORK/f'{case}-{mode}',scope)
        readback={p:sink._connection.execute('PRAGMA '+p).fetchall() for p in ['temp_store','journal_mode','auto_vacuum','page_size','cache_size','mmap_size','synchronous','max_page_count']}
        check(case+' '+mode+' mode', readback['temp_store']==[(1 if mode=='file' else 2,)])
        for row in seq:sink.add(row)
        queries=[sink._connection.execute(sql).fetchall() for sql in ['SELECT q FROM witnesses ORDER BY q','SELECT q, payload FROM witnesses ORDER BY q']]
        query_results.append(queries)
        result=sink.finalize()
        module.validate_witnesses(result,scope)
        results.append(result)
        report.setdefault('tiny_readbacks',{})[case+'-'+mode] = readback
    check(case+' exact two SQL query results',query_results[0]==query_results[1])
    check(case+' complete manifest equality except exclusive path',normalized(results[0])==normalized(results[1]))
    for artifact in ['witnesses.jsonl','violated_pairs.bin']:
        check(case+' exact '+artifact,(WORK/f'{case}-file'/artifact).read_bytes()==(WORK/f'{case}-memory'/artifact).read_bytes())
    expected=b''.join(original._encode(row,original.MAX_RECORD_BYTES) for row in sorted(seq,key=lambda r:tuple(r['pair'])))
    check(case+' exact original values and canonical order',(WORK/f'{case}-memory/witnesses.jsonl').read_bytes()==expected)
    report.setdefault('outputs',{})[case]=normalized(results[1])

# Saved raw data is zero rows. Qualify exactly that fact, with no inferred
# physical rerun or search for a more favorable nonempty historical outcome.
saved_result=json.loads((SAVED/'result.json').read_text())['separation']
saved_files={name:dict(path=str(SAVED/'direct-witnesses'/name),sha256=sha(SAVED/'direct-witnesses'/name),bytes=(SAVED/'direct-witnesses'/name).stat().st_size) for name in ['spill.sqlite3','witnesses.jsonl','violated_pairs.bin']}
for key,name in [('per_pair_worst','witnesses.jsonl'),('violated_pairs','violated_pairs.bin')]:
    manifest=saved_result[key]
    check('saved '+name+' receipt hash/count',manifest['sha256']==saved_files[name]['sha256'] and manifest['bytes']==saved_files[name]['bytes']==0 and manifest['count']==0)
con=sqlite3.connect('file:'+str(SAVED/'direct-witnesses/spill.sqlite3')+'?mode=ro&immutable=1',uri=True)
rows=con.execute('SELECT q, payload FROM witnesses ORDER BY q').fetchall()
check('saved exact row count',rows==[])
saved_sql_schema=con.execute("SELECT sql FROM sqlite_schema WHERE type='table'").fetchall()
check('saved exact schema',saved_sql_schema==[('CREATE TABLE witnesses (q INTEGER PRIMARY KEY, payload BLOB NOT NULL)',)])
con.close()
saved_outputs=[]
for mode in ['file','memory']:
    path=WORK/f'saved-{mode}.sqlite3'; con=sqlite3.connect(path,isolation_level=None)
    for sql in ['PRAGMA page_size=4096','PRAGMA journal_mode=OFF','PRAGMA synchronous=FULL','PRAGMA mmap_size=0','PRAGMA cache_size=-4096', 'PRAGMA temp_store='+mode.upper(),'PRAGMA max_page_count=1048575']:
        con.execute(sql)
    if mode=='memory':proposed._require_sqlite_storage(con,1048575)
    con.execute(saved_sql_schema[0][0])
    for row in rows:con.execute('INSERT INTO witnesses (q, payload) VALUES (?, ?)',row)
    actual=[con.execute(sql).fetchall() for sql in ['SELECT q FROM witnesses ORDER BY q','SELECT q, payload FROM witnesses ORDER BY q']]
    saved_outputs.append(actual); con.close()
check('saved exact FILE and MEMORY queries',saved_outputs==[[[],[]],[[],[]]])
report['saved_case']=dict(files=saved_files, count=0, schema=saved_sql_schema, old_result_sha256=sha(SAVED/'result.json'),coverage='Retained empty December physical witness dataset only')

# Reject malformed, missing, overridden, unknown or differently compiled modes.
class Rows:
    def __init__(self,value):self.value=value
    def fetchall(self):return self.value
valid={'compile_options':[('TEMP_STORE=1',)],'temp_store':[(2,)],'journal_mode':[('off',)],'auto_vacuum':[(0,)],
       'page_size':[(4096,)],'cache_size':[(-4096,)],'mmap_size':[(0,)],'synchronous':[(2,)],'max_page_count':[(1048575,)]}
class Fake:
    def __init__(self,override=None):self.values={**valid,**(override or {})}
    def execute(self,sql):return Rows(self.values[sql.removeprefix('PRAGMA ')])
proposed._require_sqlite_storage(Fake(),1048575)
faults=[]
for value in [[], [('TEMP_STORE=0',)], [('TEMP_STORE=2',)], [('TEMP_STORE=3',)], [('TEMP_STORE=unknown',)], [('TEMP_STORE=1',),('TEMP_STORE=1',)], [('TEMP_STORE=1',),('TEMP_STORE_OMIT',)], [(1,)], [('TEMP_STORE=1','extra')]]:
    faults.append(('compile_options',value))
for name in valid:
    if name=='compile_options':continue
    for value in [[],[(None,)],[(valid[name][0][0],),(valid[name][0][0],)],[(valid[name][0][0],0)]]:faults.append((name,value))
for name,value in [('temp_store',[(1,)]),('journal_mode',[('wal',)]),('auto_vacuum',[(1,)]),('temp_store',[(True,)]),('page_size',[(8192,)]),('mmap_size',[(4096,)]),('cache_size',[(-8192,)]),('synchronous',[(0,)]),('max_page_count',[(1048576,)])]:faults.append((name,value))
for index,(name,value) in enumerate(faults):
    try:proposed._require_sqlite_storage(Fake({name:value}),1048575)
    except proposed.WitnessStoreError:pass
    else:raise AssertionError(('accepted invalid storage mode',name,value))
check('all '+str(len(faults))+' qualification/readback faults rejected',True)
report['negative_readbacks']=[dict(pragma=p,value=v) for p,v in faults]

# The real initialization/add/finalize catches must poison the sink. OOM is
# injected, not induced by large allocations; successful return is forbidden.
for stage,error in [('initialize',sqlite3.OperationalError('out of memory')),('initialize',MemoryError('injected allocation failure')),
                    ('add',sqlite3.OperationalError('out of memory')),('add',MemoryError('injected allocation failure')),
                    ('finalize',sqlite3.OperationalError('out of memory')),('finalize',MemoryError('injected allocation failure'))]:
    out=WORK/f'failure-{stage}-{type(error).__name__}'
    if stage=='initialize':
        with patch.object(proposed,'_require_sqlite_storage',side_effect=error):
            try:proposed.WitnessSink(out,scope)
            except proposed.WitnessStoreError:pass
            else:raise AssertionError('initialize returned success on OOM')
    else:
        sink=proposed.WitnessSink(out,scope)
        if stage=='finalize':sink.add(records[0])
        real=sink._connection
        class FailingConnection:
            def execute(self,*args,**kwargs):raise error
            def close(self):return real.close()
        sink._connection=FailingConnection()
        try:sink.add(records[0]) if stage=='add' else sink.finalize()
        except proposed.WitnessStoreError:pass
        else:raise AssertionError(stage+' returned success on OOM')
        check(stage+' '+type(error).__name__+' poisoned',sink._state=='failed' and sink._connection is None)
        try:sink.finalize()
        except proposed.WitnessStoreError:pass
        else:raise AssertionError('failed sink re-finalized')
    check(stage+' '+type(error).__name__+' retained failure', (out/'FAILED.json').is_file())

for mode,module in [('file',original),('memory',proposed)]:
    for failure in ['duplicate','witness_cap']:
        out=WORK/f'{failure}-{mode}'
        kwargs={} if failure=='duplicate' else {'max_witness_bytes':1}
        sink=module.WitnessSink(out,scope,**kwargs)
        if failure=='duplicate':sink.add(records[0])
        try:sink.add(records[0])
        except module.WitnessStoreError:pass
        else:raise AssertionError('expected failure was accepted')
        check(failure+' '+mode+' fail closed',sink._state=='failed' and not (out/'violated_pairs.bin').exists())

# Source proof: every old method except initializer is AST-identical; all SQL
# schema/INSERT/SELECT text and constants are unchanged except temp-store mode.
a=ast.parse(Path(original.__file__).read_text()); b=ast.parse(Path(proposed.__file__).read_text())
def functions(tree):
    return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name!='WitnessSink'}
fa,fb=functions(a),functions(b);fb.pop('_require_sqlite_storage')
check('all original helper ASTs unchanged',fa==fb)
for method in next(n for n in a.body if isinstance(n,ast.ClassDef) and n.name=='WitnessSink').body:
    if isinstance(method,ast.FunctionDef) and method.name!='__init__':
        peer=next(n for n in next(n for n in b.body if isinstance(n,ast.ClassDef) and n.name=='WitnessSink').body if isinstance(n,ast.FunctionDef) and n.name==method.name)
        check('unchanged method '+method.name,ast.dump(method)==ast.dump(peer))
for name in ['MAX_WITNESS_BYTES','MAX_INTERMEDIATE_BYTES','MAX_PAIR_BYTES','MAX_RECORD_BYTES','SQLITE_CACHE_KIB','SQLITE_PAGE_BYTES','FAILURE_RESERVE_BYTES']:
    check('unchanged cap '+name,getattr(original,name)==getattr(proposed,name))
for sql in ['CREATE TABLE witnesses (q INTEGER PRIMARY KEY, payload BLOB NOT NULL)','INSERT INTO witnesses (q, payload) VALUES (?, ?)','SELECT q FROM witnesses ORDER BY q','SELECT q, payload FROM witnesses ORDER BY q']:
    check('unchanged SQL '+sql,sql in Path(original.__file__).read_text() and sql in Path(proposed.__file__).read_text())

con=sqlite3.connect(':memory:')
report['runtime']=dict(python=sys.version,executable=sys.executable,sqlite_version=sqlite3.sqlite_version,
    sqlite_source_id=con.execute('SELECT sqlite_source_id()').fetchone()[0],compile_options=[r[0] for r in con.execute('PRAGMA compile_options')],
    limits={str(kind):resource.getrlimit(kind) for kind in [resource.RLIMIT_CORE,resource.RLIMIT_AS,resource.RLIMIT_FSIZE]})
con.close()
report['loaded_modules']=sorted(sys.modules)
check('no numerical/model/physical/native modules imported',not any(n=='numpy' or n=='scipy' or n.startswith('numpy.') or n.startswith('scipy.') or n.startswith('highspy') or n.startswith('current_scuc.science') or n in ['current_scuc.physical','current_scuc.core.driver.fractional_separator','current_scuc.core.driver.model_stage'] for n in sys.modules))
report['elapsed_seconds']=time.monotonic()-started
report['all_passed']=True
report['work_files']=[dict(path=str(p.relative_to(WORK)),bytes=p.stat().st_size,allocated_bytes=p.stat().st_blocks*512) for p in sorted(WORK.rglob('*')) if p.is_file()]
report['retained_test_bytes']=sum(row['bytes'] for row in report['work_files'])
report['test_script_sha256']=sha(__file__)
(HERE/'sqlite-test-results.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
print(json.dumps(dict(all_passed=True,test_count=len(report['tests']),retained_test_bytes=report['retained_test_bytes'],elapsed_seconds=report['elapsed_seconds']),sort_keys=True))
