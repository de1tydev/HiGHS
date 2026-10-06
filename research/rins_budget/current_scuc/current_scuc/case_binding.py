"""A fresh local case with source-derived identity and strict production guards.

Importing this module does not read a case, import scientific modules, construct
a model, factor a network, load a DSO, or launch a process.
"""
from __future__ import annotations
import ast
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
from fractions import Fraction

from collections.abc import Mapping
from ._paths import ROOT, source_path, source_sha, module

HERE = ROOT
CORE = ROOT/'core'
SCHEMA = 'current-scuc-case-binding/v1'
CASE = dict(system='case1354pegase', hours=36, seed=0)
COMMIT = 'd547a3ad8af5399651187fb0e133cf0e42615b82'
# Proof identifiers are attribution, not historical runtime inputs.
PROOF_IDENTITIES = {
    'first-start-cut-proof-v1/MANIFEST.json': 'e9f2619089f65a6b3faf559a6d66b6ca760676d7461c7f2b7b480bc48255183a',
    'first-start-zero-cost-proof-v1/PROPOSAL.md': 'a414c8f5dd658d327a2026c1a55e074760f0a37efde100fa557cdcbdca8c1991',
    'first-start-zero-cost-proof-v1/MANIFEST.json': '83a6f63efb00c8cdb6d73d20291ba10e183ea84a537a3b59ea2b46fc7bdafab1',
}
SOURCE_ROLES = (
    'primal-cache-replay-v4.1/core/scuc/generate.py',
    'primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py',
    'primal-cache-replay-v4.1/core/canonical_mps_export/readback.py',
    'first-start-complete-family-v1/cuts.py',
)
class _SourcePins(Mapping):
    def __getitem__(self,key): return PROOF_IDENTITIES[key] if key in PROOF_IDENTITIES else source_sha(key)
    def __iter__(self): return iter((*SOURCE_ROLES,*PROOF_IDENTITIES))
    def __len__(self): return len(SOURCE_ROLES)+len(PROOF_IDENTITIES)
PINS = _SourcePins()
CAPS = dict(worker_seconds=300, preparation_seconds=600, address_space_bytes=7*1024**3,
    rss_bytes=6*1024**3, physical_headroom_bytes=2*1024**3,
    python_file_bytes=512*1024**2, state_file_bytes=128*1024**2, native_file_bytes=64*1024**2,
    raw_artifact_bytes=1024**3, campaign_bytes=24*1024**3, metadata_bytes=512*1024**2,
    active_lines=8, candidate_batches=4, added_nonzeros=1048576,
    candidate_columns=142094, candidate_rows=164080, candidate_nonzeros=1756901,
    whole_seconds=1800, solver_process_seconds=600, stage_ack_seconds=120)
FIDELITY_FIELDS = frozenset(('num_col','num_row','num_nz','sense','offset','col_names','row_names',
    'col_lower','col_upper','col_cost','row_lower','row_upper','integrality','a_start','a_index','a_value'))

class ContractError(ValueError): pass

def require(ok, message):
    if not ok: raise ContractError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''): h.update(block)
    return h.hexdigest()

def identity(value, *, sorted_keys=True, source=False):
    return hashlib.sha256(json.dumps(value,sort_keys=sorted_keys,separators=(',',':'),allow_nan=source).encode()).hexdigest()

def unique(items):
    result={}
    for k,v in items:
        require(k not in result,'Duplicate JSON key: '+k); result[k]=v
    return result

def read(path):
    def reject(v): raise ContractError('Nonfinite JSON: '+v)
    def number(v):
        value=float(v); require(math.isfinite(value),'Nonfinite JSON float'); return value
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=reject,parse_float=number)

def read_source(path):
    # Source +Infinity is allowed only where the pinned source validator permits it.
    with gzip.open(path,'rt') if str(path).endswith('.gz') else Path(path).open() as f:
        return json.load(f,object_pairs_hook=unique)

def write(path, value, *, fresh=True):
    path=Path(path); require(not path.is_symlink(),'Symlink output')
    require(not fresh or not path.exists(),'Output already exists: '+str(path))
    payload=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    require(len(payload)<=CAPS['state_file_bytes'],'JSON state cap')
    with path.open('xb' if fresh else 'wb') as f:
        f.write(payload); f.flush(); os.fsync(f.fileno())
    require(path.read_bytes()==payload,'Durable JSON readback mismatch')

def record(path): return dict(path=str(Path(path).resolve()),sha256=sha(path))

def check_record(item, *, local=True):
    require(type(item) is dict and set(item)=={'path','sha256'},'File record schema')
    path=Path(item['path'])
    require(path.is_absolute() and path.resolve()==path and not path.is_symlink(),'Noncanonical file path')
    require(path.is_file(),'Missing input artifact: '+str(path))
    require(type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}',item['sha256']) and sha(path)==item['sha256'],'File hash changed: '+str(path))
    return path

def verify_pinned_sources():
    # The per-run source snapshot is the mutation authority. Here, only the
    # required local source roles are checked, without loading numerical code.
    for relative in SOURCE_ROLES:
        require(source_path(relative).is_file(),'Missing local source: '+relative)

def source_helpers():
    verify_pinned_sources()
    from .core.driver import fractional_separator
    return fractional_separator

def first_start_inventory(data):
    """Classify all eligible units; zero omission remains pending model readback."""
    from . import zero_cost as zero
    result=zero.classify(data); ceiling=0
    for item in result['units']:
        name,cost=item['unit'],float.fromhex(item['C_hex'])
        for t in range(result['hours']):
            ceiling += 12+len(f'    u_{name}_{t}  ')+7+2+len(format(-cost,'.17g'))+1
            ceiling += sum(len(f'    sc_{name}_{s}  ')+7+2+1+1 for s in range(t+1))
    result.update(additive_mps_bytes=ceiling,implementation_sha256=PINS['first-start-complete-family-v1/cuts.py'],
        proof_manifest_sha256=PINS['first-start-cut-proof-v1/MANIFEST.json'],
        amendment_proposal_sha256=zero.PROPOSAL_SHA,amendment_manifest_sha256=zero.MANIFEST_SHA,
        empty_applicability=not result['eligible_units'])
    return result


def array_hash(values, fmt='d'):
    h=hashlib.sha256()
    for v in values: h.update(struct.pack('<'+fmt,v))
    return h.hexdigest()

def source_contract(data, *, production=True):
    helper=source_helpers(); hours=data['Parameters']['Time horizon (h)']
    require(type(hours) is int and hours==36 if production else type(hours) is int and hours>0,'Source horizon')
    universe=helper.source_scope(data,hours)
    names=helper.expected_column_names(data,hours,universe)
    buses,lines,gens=(list(data[k]) for k in ('Buses','Transmission lines','Generators'))
    rated,outages=universe['rated_line_indices'],universe['outage_indices']; outset=set(outages)
    if production:
        require((len(buses),len(gens),len(lines),len(rated),len(outages))==(1354,260,1991,1432,1288),'Supported PEGASE1354 production scope mismatch')
    normal=[]; emergency=[]; coverage=[]
    at=lambda v,t:float(v[t] if isinstance(v,list) else v)
    for t in range(hours):
        n=[at(d.get('Normal flow limit (MW)',math.inf),t) for d in data['Transmission lines'].values()]
        e=[at(d.get('Emergency flow limit (MW)',math.inf),t) for d in data['Transmission lines'].values()]
        require(all(not math.isnan(v) and v>=0 for v in n+e),'Invalid source rating')
        normal.extend(n); emergency.extend(e)
        nn=sum(math.isfinite(n[l]) for l in rated); el=[l for l in rated if math.isfinite(e[l])]
        pairs=sum(len(outages)-(l in outset) for l in el)
        coverage.append(dict(hour=t,normal_monitored_lines=nn,emergency_monitored_lines=len(el),listed_outages=len(outages),
            unsigned_security_pairs=pairs,signed_normal_rows=2*nn,signed_security_rows=2*pairs,
            conceptual_signed_rows=2*(nn+pairs),self_excluded_pairs=sum(l in outset for l in el)))
    scope=dict(hours=hours,buses=len(buses),generators=len(gens),lines=len(lines),finite_rated_lines=len(rated),
        distinct_listed_single_line_outages=len(outages),rated_outage_intersection=len(set(rated)&outset),
        allowed_pairs_per_hour=len(rated)*len(outages)-len(set(rated)&outset),
        unsigned_security_pair_hours=sum(r['unsigned_security_pairs'] for r in coverage),
        signed_normal_rows=sum(r['signed_normal_rows'] for r in coverage),
        signed_security_rows=sum(r['signed_security_rows'] for r in coverage))
    scope['signed_soft_rows']=scope['signed_normal_rows']+scope['signed_security_rows']
    bi={b:i for i,b in enumerate(buses)}
    endpoints=[[bi[d['Source bus']],bi[d['Target bus']]] for d in data['Transmission lines'].values()]
    weights=[float(d['Susceptance (S)']) for d in data['Transmission lines'].values()]
    require(all(math.isfinite(v) and v>0 for v in weights),'Positive source weights required')
    topology=dict(source_object_sha256=identity(data,source=True),ordered_bus_ids=buses,ordered_line_ids=lines,ordered_generator_ids=gens,
        ordered_monitored_indices=rated,ordered_outage_indices=outages,
        ordered_monitored_ids=[lines[i] for i in rated],ordered_outage_ids=[lines[i] for i in outages],
        ordered_contingency_ids=list(data['Contingencies']),ordered_endpoints=endpoints,
        weights_binary64_sha256=array_hash(weights),endpoints_int32_sha256=array_hash((i for p in endpoints for i in p),'i'),
        normal_limit_binary64_sha256=array_hash(normal),emergency_limit_binary64_sha256=array_hash(emergency),
        normal_finite_mask_sha256=array_hash((int(math.isfinite(v)) for v in normal),'B'),
        emergency_finite_mask_sha256=array_hash((int(math.isfinite(v)) for v in emergency),'B'),coverage_by_hour=coverage)
    index={n:i for i,n in enumerate(names)}; shed=[]; delta=[]; reserves=[]
    for b in buses:
        for t in range(hours):
            name=f'shed_{b}_{t}'; j=index[name]; upper=at(data['Buses'][b]['Load (MW)'],t); shed.append([j,name])
            if upper>0: delta.append([j,name,upper,0.])
    for r,d in data.get('Reserves',{}).items():
        for t in range(hours):
            require(at(d.get('Shortfall penalty ($/MW)',-1),t)<0,'Source reserve shortfall is not already fixed zero')
            name=f'short_{r}_{t}'; reserves.append([index[name],name])
    zero=dict(shed_columns=len(shed),changed_shed_upper_bounds=len(delta),already_zero_shed_columns=len(shed)-len(delta),
        reserve_shortfall_columns=len(reserves),reserve_shortfall_already_fixed_zero=True,
        shed_inventory_sha256=identity(shed),reserve_inventory_sha256=identity(reserves),
        exact_changed_upper_bound_records_sha256=identity(delta))
    binary=[f'{k}_{g}_{t}' for g in gens for t in range(hours) for k in ('u','y','z')]
    return dict(scope=scope,topology=topology,first_start=first_start_inventory(data),hard_zero=zero,
        source_object_sha256=identity(data,source=True),source_ordered_sha256=identity(data,sorted_keys=False,source=True),
        source_names_sha256=identity(names),binary_count=len(binary),binary_names_sha256=identity(binary),
        column_names=names,universe=universe)

def model_contract(expected,data,derived):
    """Derive mapping inventory and empty adaptive-base shape independently."""
    require(set(expected)==FIDELITY_FIELDS,'Expected model must contain exactly sixteen fields')
    names=list(expected['col_names']); require(names==derived['column_names'],'Every original source column/order required')
    hours=derived['scope']['hours']; scope=dict(derived['scope'])
    original={k:int(expected[k]) for k in ('num_col','num_row','num_nz')}
    binary=[n for n,i in zip(names,expected['integrality']) if i==1]
    require(identity(binary)==derived['binary_names_sha256'] and len(binary)==derived['binary_count'],'Original binary authority mismatch')
    require(all(i in (0,1) for i in expected['integrality']),'Unexpected integrality type')
    removed=[j for j,n in enumerate(names) if n.startswith(('theta_','f_','over_'))]; retained=[j for j,n in enumerate(names) if not n.startswith(('theta_','f_','over_'))]
    network_rows=hours*(scope['lines']+scope['buses'])+scope['signed_normal_rows']
    first=original['num_row']-network_rows; require(first>=0,'Missing empty-pair network rows')
    kept_nnz=0; removed_set=set(removed)
    for j in range(original['num_col']):
        count=sum(int(r)<first for r in expected['a_index'][expected['a_start'][j]:expected['a_start'][j+1]])
        require(j not in removed_set or count==0,'Removed network column enters retained temporal rows')
        kept_nnz+=count
    idx={n:j for j,n in enumerate(names)}; balance_nnz=0
    for t in range(hours):
        balance=[idx[f'p_{g}_{t}'] for g in data['Generators']]+[idx[f'shed_{b}_{t}'] for b in data['Buses']]
        balance_nnz+=2+sum(not(expected['col_lower'][j]==expected['col_upper'][j]==0.) for j in balance)
    base=dict(num_col=len(retained)+2,num_row=first+hours,num_nz=kept_nnz+balance_nnz)
    fs=derived['first_start']; family=dict(num_col=base['num_col'],num_row=base['num_row']+fs['row_count'],num_nz=base['num_nz']+fs['nonzeros'])
    scope['virtual_full_rows']=original['num_row']+scope['signed_security_rows']
    return dict(original=original,conventional_cold=original,projected_base=base,projected_first_start=family,
        retained_columns=len(retained),binary_count=len(binary),retained_nonnetwork_row_prefix_end=first,
        retained_matrix_nnz=kept_nnz,balance_nnz=balance_nnz,mapping_rows=0,mapping_nonzeros=0),scope

def validate(value):
    keys={'schema','case','source','model','mapping_pairs','runtime','scope','topology','first_start','hard_zero','shapes','caps','provenance'}
    require(type(value) is dict and set(value)==keys,'Case binding schema keys')
    require(value['schema']==SCHEMA and value['case']==CASE,'Only supported 36-hour PEGASE1354 production case is admitted')
    require(value['mapping_pairs']==[],'Historical/security mapping pairs forbidden')
    require(value['caps']==CAPS,'Unchanged caps required')
    require(set(value['source'])=={'path','sha256'},'Local source identity fields')
    require(set(value['model'])=={'mps','expected','readback','pairs','metadata','retained_mps','retained_expected','retained_readback','zero_certificate'},'Model artifact inventory')
    require(value['runtime']['upstream_commit']==COMMIT,'Runtime source commit changed')
    require(value['provenance']['production_scope'] is True and value['provenance']['optimization_or_presolve_called'] is False,'Preparation scope')
    require(value['shapes']['mapping_rows']==value['shapes']['mapping_nonzeros']==0,'Nonempty mapping row inventory')
    fs=value['first_start']; h=CASE['hours']; k=fs['unit_count']
    require(k==len(fs['units']) and fs['hours']==h and fs['row_count']==k*h and fs['nonzeros']==k*h*(h+3)//2,'First-start derived inventory')
    require(value['shapes']['binary_count']==3*h*value['scope']['generators'],'Binary inventory')
    return value

def load(path=None,sha256=None):
    path=path or os.environ.get('HELDOUT_CASE_BINDING'); digest=sha256 or os.environ.get('HELDOUT_CASE_BINDING_SHA256')
    require(path and digest,'Explicit current case descriptor and SHA256 required')
    require(sha(path)==digest,'Case descriptor hash changed')
    return validate(read(path))

def verify_inputs(value):
    validate(value); verify_pinned_sources()
    source=value['source']; check_record({k:source[k] for k in ('path','sha256')})
    for item in value['model'].values(): check_record(item)
    require(read(value['model']['pairs']['path'])==[],'Empty pair manifest required')
    data=read_source(source['path']); d=source_contract(data)
    for key in ('first_start','hard_zero'):
        require(d[key]==value[key],'Current source contract mismatch: '+key)
    require(d['scope']=={k:v for k,v in value['scope'].items() if k!='virtual_full_rows'},'Current coverage mismatch')
    require(d['topology']=={k:v for k,v in value['topology'].items() if k not in ('lodf_binary64_C_sha256','minimum_outage_denominator')},'Current ordered topology mismatch')
    for k in ('source_object_sha256','source_ordered_sha256','source_names_sha256','binary_names_sha256'):
        require(value['provenance'][k]==d[k],'Current source identity mismatch: '+k)
    return dict(passed=True,source_sha256=source['sha256'],expected_sha256=value['model']['expected']['sha256'],mps_sha256=value['model']['mps']['sha256'])

def verify_runtime(value):
    validate(value); item=value['runtime']['config']; path=check_record(item)
    os.environ['PRIMAL_CACHE_CONFIG']=str(path); os.environ['PRIMAL_CACHE_CONFIG_SHA256']=item['sha256']
    from . import binding
    result=binding.verify_freeze(); cfg=binding.config()
    require(cfg['inputs']=={'current':value['source']},'Runtime current source differs')
    return result
