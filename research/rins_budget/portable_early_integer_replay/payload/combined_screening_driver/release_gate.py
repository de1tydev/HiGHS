"""Explicit final release gate; no target execution is implied by source staging."""
import hashlib
import json
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(path):
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate release key')
            result[key]=value
        return result
    def reject(v):raise ValueError('Nonfinite release value')
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=reject)

def validate_schedule(plan):
    schedule=plan.get('confirmation')
    if type(schedule) is not list or not schedule:raise ValueError('No finite reviewed schedule')
    seen=set()
    for sequence,item in enumerate(schedule,1):
        if (set(item)!={'sequence','case','seed','arm_order'} or item['sequence']!=sequence
            or item['case'] not in plan.get('cases',{}) or type(item['seed']) is not int or item['seed']<0
            or type(item['arm_order']) is not list or sorted(item['arm_order'])!=['A','B','C']):
            raise ValueError('Malformed reviewed three-arm block')
        identity=(item['case'],item['seed'])
        if identity in seen:raise ValueError('Duplicate reviewed case/seed block')
        seen.add(identity)
        source=plan['cases'][item['case']]
        record=plan.get('allowed_sources',{}).get(source,{})
        if record.get('kind')!='reserved' or not record.get('scope') or not record.get('dimensions'):
            raise ValueError('Missing exact source-only scope reservation')
    phase=plan.get('phase')
    if phase=='development':
        if len(schedule)!=1 or schedule[0]['seed']!=0 or schedule[0]['arm_order']!=['A','B','C']:
            raise ValueError('Development must be exact seed0 ABC block')
    elif phase in ('confirmation','diagnostic'):
        cases=list(dict.fromkeys(item['case'] for item in schedule))
        seeds=[211,212,213] if phase=='confirmation' else [0,1,2]
        expected=[]
        for case in cases:
            expected.extend((case,seed,list(order)) for seed,order in zip(seeds,('ABC','BCA','CAB')))
        actual=[(item['case'],item['seed'],item['arm_order']) for item in schedule]
        if actual!=expected:raise ValueError('Reserved cyclic seed/date blocks changed or interleaved')
    else:raise ValueError('No performance release for this phase')
    return schedule

def require_target_release(here):
    here=Path(here).resolve();plan=read(here/'CAMPAIGN_PLAN.json');bindings=read(here/'BINDINGS.json')
    path=here/'TARGET_RELEASE.json'
    if not path.is_file():raise ValueError('Seed measurements remain unreleased; missing final reviewed TARGET_RELEASE.json')
    expected={'schema':'reviewed-constructive-seed-release-v1',
              'package_sha256':bindings['release_sha256'],'runtime_sha256':digest(here/'RUNTIME_MANIFEST.json'),
              'plan_sha256':digest(here/'CAMPAIGN_PLAN.json'),
              'protocol_sha256':digest(here/'FINAL_PROTOCOL.json'),
              'measurement_authorized':True}
    if read(path)!=expected:raise ValueError('Final source/runtime/protocol release does not match exact candidate')
    protocol=read(here/'FINAL_PROTOCOL.json')
    if (not protocol.get('measurement_authorized') or not plan.get('confirmation') or plan.get('phase')!=protocol.get('phase')
        or protocol.get('schedule')!=plan['confirmation'] or not plan.get('cases')):
        raise ValueError('No final frozen case/schedule release')
    validate_schedule(plan)
    return {'path':str(path),'sha256':digest(path),**expected}
