"""Thin pure per-line map, support-prefix and seed-promotion bridge.

The pinned LP adapter owns all structural edits. Envelopes retain the ledger
BEFORE an evaluation, so replaying seed LP2's support installs batch 2 exactly
once without changing its solved one-batch snapshot or consuming a third point.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import copy
from fractions import Fraction
from pathlib import Path
import numpy as np
from current_scuc.common import ROOT, module, require

PINS = {
    'family_adapter.py': source_sha('heldout-projected-binding-v2/family_adapter.py'),
    'science/native.py': source_sha('adaptive-line-lp-adapter-v1/native.py'),
    'science/support.py': source_sha('adaptive-line-lp-runner-v1/support.py'),
    'science/lp_helpers.py': source_sha('adaptive-line-lp-runner-v1/arm.py'),
}


def pinned(name, relative):
    import hashlib
    path = ROOT / relative
    require(hashlib.sha256(path.read_bytes()).hexdigest() == PINS[relative], 'Adaptive dependency changed: '+relative)
    return module(name, path)


def adapter():
    return pinned('adapter', 'family_adapter.py')


def support():
    return pinned('_adaptive_integer_support', 'science/support.py')


def lp_policy():
    policy = pinned('_adaptive_integer_lp_policy', 'science/lp_helpers.py')
    from current_scuc.common import bounded_bundle, bounded_json
    policy.bundle, policy.write_json = bounded_bundle, bounded_json
    return policy


def native():
    adapter()
    return pinned('_adaptive_integer_lp_native', 'science/native.py')


def snapshot(state):
    return dict(nret=state.nret, hours=state.hours, rated=list(state.rated),
        source_identity=state.source_identity, scope_identity=state.scope_identity,
        active=list(state.active), evaluations=state.evaluations,
        admitted=state.admitted, cut_nnz=state.cut_nnz)


def hydrate_metadata(metadata):
    meta=copy.deepcopy(metadata)
    meta['original_to_retained']={int(j):int(i) for j,i in meta['original_to_retained'].items()}
    meta['exact_pairs']=tuple(tuple(pair) for pair in meta['exact_pairs'])
    return meta


def activation(metadata):
    a=adapter(); saved=metadata['activation']
    require(set(saved)=={'nret','hours','rated','source_identity','scope_identity','active','evaluations','admitted','cut_nnz'}, 'Activation snapshot fields')
    state=a.emitter.Activation(saved['nret'],saved['hours'],saved['rated'],saved['source_identity'],saved['scope_identity'])
    for key in ('evaluations','admitted','cut_nnz'):
        require(type(saved[key]) is int and saved[key]>=0,'Invalid activation count')
        setattr(state,key,saved[key])
    state.active=tuple(saved['active'])
    require(state.nret==len(metadata['retained_original_columns']) and state.hours==metadata['hours']
        and state.rated==tuple(metadata['rated']) and state.source_identity==metadata['source_identity']
        and state.scope_identity==metadata['scope_identity'] and state.map_hash==metadata['map_hash'], 'Activation map/source/scope mismatch')
    require(state.admitted<=state.evaluations<=a.emitter.MAX_EVALUATIONS and state.admitted<=a.emitter.MAX_BATCHES
        and len(state.active)<=a.emitter.ACTIVE_CAP and len(set(state.active))==len(state.active)
        and set(state.active).issubset(state.rated), 'Activation limits')
    return state


def sync(expected, metadata, state, caps=None):
    a=adapter(); meta=copy.deepcopy(metadata)
    meta['activation']=snapshot(state)
    meta['projected_num_col']=expected['num_col']
    meta['projected_hashes']=a.model.model_hashes(expected)
    meta['canonical_continuous_hashes']=a.model.model_hashes(dict(expected,row_names=[f'R{i}' for i in range(expected['num_row'])]))
    meta['map_hash']=state.map_hash
    if caps is not None: meta['line_caps']=[[l,t,float(caps[l,t])] for l,t in state.columns]
    meta['matrix_identity']=a.matrix_identity(expected,meta,state)
    a._check_context(expected,meta,state)
    return meta


def make_base(original, source, hours, pairs, lodf, source_identity, scope):
    a=adapter(); expected,meta,state=a.make_base(original,source,hours,pairs,lodf,source_identity,scope)
    # Capture the original network boundary before appending the fixed family.
    removed_row_range = [meta['base_row_count']-hours, original['num_row']]
    import current_scuc.first_start as first_start
    expected, meta = first_start.install(expected, meta, original, source, a.model)
    import current_scuc.no_shedding as no_shedding
    expected, meta = no_shedding.install(expected, meta, original, a.model)
    # Derive original column maps from source-checked names, without another factor.
    names={name:j for j,name in enumerate(original['col_names'])}
    lines=scope['ordered_line_ids']
    over=np.full((hours,len(lines)),-1,dtype=np.int32)
    for t in range(hours):
        for l in meta['rated']:
            over[t,l]=names[f'over_{lines[l]}_{t}']
    meta.update(source_maps={'overload':over},
        retained_original_columns_sha256=a.model.digest(meta['retained_original_columns']),
        original_to_projected_sha256=a.model.digest(meta['original_to_projected']),
        removed_row_range=removed_row_range, line_caps=[])
    meta=sync(expected,meta,state)
    return expected,meta,state


def validate_current(expected, metadata, original, *, canonical=False):
    a=adapter(); state=activation(metadata); e=a.model.validate_model(expected)
    require(a.model.model_hashes(original)==metadata['original_hashes'],'Original model identity drift')
    import current_scuc.no_shedding as no_shedding
    no_shedding.validate_retained(e, metadata, original, a.model)
    continuous=dict(e,integrality=np.zeros(e['num_col'],dtype=np.int32))
    hashes=metadata['canonical_continuous_hashes'] if canonical else metadata['projected_hashes']
    require(a.model.model_hashes(continuous)==hashes,'Current adaptive matrix/caps/prefix mismatch')
    import current_scuc.first_start as first_start
    first_start.validate(e, metadata['first_start_family'], a.model, canonical=canonical)
    if not canonical:a._check_context(continuous,metadata,state)
    retained=np.asarray(metadata['retained_original_columns'],dtype=np.int32)
    require(e['num_col']==state.num_col and e['col_names']==[original['col_names'][j] for j in retained]
        +['aggregate_one_plus','aggregate_one_minus']
        +[f'eta_line_{l}_MW_{t}' for l in state.active for t in range(state.hours)],'Current adaptive column names/order')
    caps=metadata['line_caps']
    require(len(caps)==len(state.columns) and [(l,t) for l,t,v in caps]==list(state.columns),'Current cap inventory/order')
    for l,t,value in caps:
        j=state.columns[l,t]
        require(e['col_upper'][j]==value and e['col_lower'][j]==0. and e['col_cost'][j]==5000.,'Current eta caps/costs')
    for j in state.fixed:
        require(e['col_lower'][j]==e['col_upper'][j]==1. and e['col_cost'][j]==0.,'Current fixed-one encoding')
    return state


def envelope(expected, metadata, emitted, caps, debit):
    a=adapter(); state=activation(metadata)
    token=state.preflight(emitted['supports'],admit=True) if state.admitted<4 else state.preflight(emitted['supports'],admit=False)
    require(token['support_hash']==emitted['token']['support_hash'] and token['before']==emitted['token']['before'],'Support emission/install mismatch')
    # Rows retain their exact certificates in the support artifact; replay uses
    # only these numeric matrix fields and the complete original selected rows.
    rows=[{k:copy.deepcopy(row[k]) for k in ('line','hour','original_indices','coefficients','eta_coefficient','upper')} for row in emitted['rows']]
    result=dict(schema='adaptive-integer-support-envelope/v1',
        before_activation=snapshot(state), before_matrix_identity=metadata['matrix_identity'],
        before_hashes=a.model.model_hashes(expected), before_map_hash=state.map_hash,
        source_identity=state.source_identity,scope_identity=state.scope_identity,
        supports=copy.deepcopy(emitted['supports']), rows=rows,
        caps=[[l,t,float(caps[l,t])] for l in token['active'] for t in range(state.hours)],
        nnz=emitted['actual_cut_nnz'],support_hash=token['support_hash'],
        anchor_gap_dollars=a.emitter.rat(emitted['anchor_gap_dollars']),
        bank_debit_dollars=a.emitter.rat(debit['debit_dollars']))
    require(Fraction(*map(int,result['anchor_gap_dollars']))<=100
        and Fraction(*map(int,result['bank_debit_dollars']))<=100,'Support dollar budget')
    return result


def stage(expected, metadata, saved):
    a=adapter(); state=activation(metadata)
    require(saved['schema']=='adaptive-integer-support-envelope/v1','Support envelope schema')
    require(saved['before_activation']==snapshot(state) and saved['before_matrix_identity']==metadata['matrix_identity']
        and saved['before_hashes']==a.model.model_hashes(expected) and saved['before_map_hash']==state.map_hash
        and saved['source_identity']==state.source_identity and saved['scope_identity']==state.scope_identity,'Stale support/prefix/pre-install ledger')
    token=state.preflight(saved['supports'],admit=True)
    require(token['support_hash']==saved['support_hash'],'Support serialization changed')
    caps={(l,t):v for l,t,v in saved['caps']}
    require(len(caps)==len(saved['caps']) and saved['nnz']==sum(len(r['coefficients'])+1 for r in saved['rows']),'Support cap/nnz inventory')
    for field in ('anchor_gap_dollars','bank_debit_dollars'):
        require(0<=Fraction(*map(int,saved[field]))<=100,'Support allowance changed')
    edit=a.stage_batch(expected,metadata,state,token,saved['rows'],caps)
    # Keep adapter-owned staged metadata intact for its full verify_edit;
    # adopt bridge snapshots only after the native structural call succeeds.
    bridge_meta=sync(edit['final'],edit['next_metadata'],edit['next_state'],caps)
    return edit,bridge_meta


def install(expected, metadata, saved, *, lp=None):
    edit,next_meta=stage(expected,metadata,saved)
    receipt=lp.apply_batch(edit) if lp is not None else None
    if lp is not None:require(adapter().model.model_hashes(lp.expected)==adapter().model.model_hashes(edit['final']),'Native installed matrix mismatch')
    return edit['final'],next_meta,receipt


def terminal(expected, metadata, saved):
    a=adapter(); state=activation(metadata)
    require(saved['before_activation']==snapshot(state) and saved['before_matrix_identity']==metadata['matrix_identity'],'Stale terminal evaluation')
    token=state.preflight(saved['supports'],admit=False)
    require(token['support_hash']==saved['support_hash'],'Terminal support mismatch')
    state.commit(token,actual_cut_nnz=saved['nnz'],balance_nnz=metadata['balance_nnz'])
    return sync(expected,metadata,state)


def replay(base, base_metadata, envelopes):
    require(0<=len(envelopes)<=4,'Support replay count')
    expected,metadata=copy.deepcopy(base),copy.deepcopy(base_metadata)
    for saved in envelopes:expected,metadata,_=install(expected,metadata,saved)
    return expected,metadata


class RequestBudget:
    def __init__(self,cache,owner):self._cache,self.owner=cache,owner
    def __getattr__(self,name):return getattr(self._cache,name)
    def get(self,*args,**kwargs):
        require(self.owner.prior_requests+self._cache.requests<adapter().emitter.MAX_ADJOINTS,'Combined fresh-process request ceiling before adjoint')
        return self._cache.get(*args,**kwargs)


class Runtime:
    def __init__(self, oracle, metadata, out):
        self.prior_requests=0
        self.cache=RequestBudget(support().fresh_cache(oracle,metadata,out),self)
        self.bank=[]

    def check_requests(self):
        used=self.prior_requests+self.cache.requests
        require(used<=adapter().emitter.MAX_ADJOINTS,'Combined fresh-process elementary request ceiling')
        return used

    def adopt(self,saved):
        require(len(self.bank)<4,'Support bank limit')
        self.bank.append(dict(rows=copy.deepcopy(saved['rows']),supports=copy.deepcopy(saved['supports'])))
