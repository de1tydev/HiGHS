"""Generic nonnegative first-start classification and exact zero-row receipt.

Source classification is not an omission certificate. A production certificate
requires the two independently API-read original and retained authorities.
"""
from __future__ import annotations
import ast
from fractions import Fraction as F
import math
from pathlib import Path
import struct
from . import case_binding as cb

PROPOSAL_SHA='a414c8f5dd658d327a2026c1a55e074760f0a37efde100fa557cdcbdca8c1991'
MANIFEST_SHA='83a6f63efb00c8cdb6d73d20291ba10e183ea84a537a3b59ea2b46fc7bdafab1'
require=cb.require

def eligibility(source):
    # Only the source-only eligibility definition is loaded; no diagnostic
    # module or numerical dependency is imported for source classification.
    path=cb.source_path('first-start-complete-family-v1/cuts.py')
    require(cb.sha(path)==cb.PINS['first-start-complete-family-v1/cuts.py'],'Eligibility source changed')
    nodes=[n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='eligible_units']
    require(len(nodes)==1,'Eligibility definition inventory')
    ns=dict(require=require,math=math)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns['eligible_units'](source)

def classify(source):
    hours=source['Parameters']['Time horizon (h)']
    require(type(hours) is int and hours>0,'Invalid horizon')
    units=[]
    for unit in eligibility(source):
        literal=source['Generators'][unit]['Startup costs ($)'][-1]; C=F(literal)
        require(C>=0,'Negative cold coefficient')
        units.append(dict(unit=unit,C_hex=float(literal).hex(),C_exact=[str(C.numerator),str(C.denominator)],
            source_cost_type=type(literal).__name__,classification='positive' if C>0 else 'zero'))
    positive=[{k:u[k] for k in ('unit','C_hex','C_exact')} for u in units if u['classification']=='positive']
    zero=[u for u in units if u['classification']=='zero']
    return dict(hours=hours,eligible_units=units,eligible_unit_count=len(units),logical_prefix_count=len(units)*hours,
        units=positive,unit_count=len(positive),row_count=len(positive)*hours,
        nonzeros=len(positive)*hours*(hours+3)//2,zero_units=zero,zero_prefix_count=len(zero)*hours,
        zero_omission_status='pending_independent_model_bound_certificate',selection_uses_point=False)

def positive_rows(source):
    info=classify(source)
    return [dict(unit=u['unit'],prefix_end=t,C_hex=u['C_hex'],C_exact=u['C_exact'],nonzeros=t+2)
        for u in info['units'] for t in range(info['hours'])]

def canonical(expected):
    return dict(expected,row_names=[f'R{i}' for i in range(expected['num_row'])])

def _bound_evidence(source,original,retained):
    info=classify(source); maps=[]
    for e in (original,retained):
        names=list(e['col_names']); require(len(names)==len(set(names))==e['num_col'],'Duplicate/invalid authority names')
        maps.append({n:j for j,n in enumerate(names)})
    all_rows=[]
    for unit in info['zero_units']:
        refs=[]
        for s in range(info['hours']):
            name=f"sc_{unit['unit']}_{s}"; require(all(name in ix for ix in maps),'Missing zero-prefix authority column')
            oi,ri=(ix[name] for ix in maps); a=float(original['col_lower'][oi]); b=float(retained['col_lower'][ri])
            require(math.isfinite(a) and F(a)==0,'Original sc bound must be exact mathematical zero')
            require(struct.pack('<d',a)==struct.pack('<d',b),'Retained sc bound bits changed')
            require(int(original['integrality'][oi])==original['integrality'][oi]==0 and
                int(retained['integrality'][ri])==retained['integrality'][ri]==0,'sc authority must be continuous')
            refs.append(dict(original_index=oi,retained_index=ri,name=name,lower_hex=a.hex(),domain=0,multiplier_exact=['1','1']))
            all_rows.append(dict(unit=unit['unit'],prefix_end=s,time_origin=0,C_hex=unit['C_hex'],C_exact=['0','1'],
                source_cost_type=unit['source_cost_type'],bounds=[dict(r) for r in refs],
                row_terms=[[r['name'],['1','1']] for r in refs],row_lower_exact=['0','1'],has_u_term=False))
    require(len(all_rows)==info['zero_prefix_count'],'Complete zero logical prefix inventory')
    return info,all_rows

def certify(source,original,retained,authority,model_hashes):
    """Pure exact receipt from independently supplied trusted model identities.

The production wrapper below establishes these identities from frozen artifacts
and readback reports; caller-written identities alone are not production proof.
"""
    info,rows=_bound_evidence(source,original,retained)
    current=dict(source_object_sha256=cb.identity(source,source=True),
        original_model_hashes=model_hashes(canonical(original)),retained_model_hashes=model_hashes(canonical(retained)))
    require(all(authority[k]==v for k,v in current.items()),'Independent bound authority identity mismatch')
    result=dict(schema='zero-cold-prefix-bound-combination/v1',proposal_sha256=PROPOSAL_SHA,manifest_sha256=MANIFEST_SHA,
        authority=authority,eligible_unit_count=info['eligible_unit_count'],logical_prefix_count=info['logical_prefix_count'],
        emitted_positive_rows=info['row_count'],certified_omitted_prefixes=len(rows),rows=rows,
        exact_nonnegative_bound_combination=True,objective_or_domain_changed=False,selection_uses_point=False)
    result['identity_sha256']=cb.identity(result)
    return result

def verify_certificate(receipt,source,original,retained,authority,model_hashes):
    require(receipt==certify(source,original,retained,authority,model_hashes),'Zero omission receipt/authority changed')
    return receipt

def authority(case,model):
    """Verify original and retained artifact identities plus all 16 API fields."""
    from .preparation import accept_readback, unpack_expected
    for role in ('mps','expected','readback','retained_mps','retained_expected','retained_readback'):
        cb.check_record(case['model'][role])
    original=model.validate_model(unpack_expected(cb.read(case['model']['expected']['path'])))
    retained=model.validate_model(unpack_expected(cb.read(case['model']['retained_expected']['path'])))
    config=cb.read(cb.check_record(case['runtime']['config']))
    for prefix in ('','retained_'):
        accept_readback(cb.read(case['model'][prefix+'readback']['path']),
            case['model'][prefix+'mps']['path'],case['model'][prefix+'expected']['path'],
            case['source']['path'],case['model']['pairs']['path'],config)
    value=dict(source_sha256=case['source']['sha256'],source_object_sha256=case['provenance']['source_object_sha256'],
        generator_sha256=cb.PINS['primal-cache-replay-v4.1/core/scuc/generate.py'],
        original_model_hashes=model.model_hashes(original),retained_model_hashes=model.model_hashes(retained),
        original_readback_sha256=case['model']['readback']['sha256'],retained_readback_sha256=case['model']['retained_readback']['sha256'])
    require(value['original_model_hashes']==case['provenance']['original_model_hashes'] and
        value['retained_model_hashes']==case['provenance']['retained_model_hashes'],'Frozen model authority mismatch')
    return value

def certify_for_case(source,original,retained,case,model):
    return certify(source,original,retained,authority(case,model),model.model_hashes)

def verify_family_certificate(certificate,case):
    path=cb.check_record(case['model']['zero_certificate'])
    require(certificate==cb.read(path),'Family zero omission differs from frozen authority certificate')
    require(certificate['identity_sha256']==cb.identity({k:v for k,v in certificate.items() if k!='identity_sha256'}),'Omission certificate identity')
    require(certificate['certified_omitted_prefixes']==case['first_start']['zero_prefix_count'],'Incomplete zero prefix certificates')
    return certificate
