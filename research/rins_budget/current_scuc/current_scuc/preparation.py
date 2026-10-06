"""Bounded common input construction and readback; no optimizer entry point.

Every numerical import/call is inside an explicitly released worker. Main
enforces 300 seconds per worker and 600 seconds for the complete phase.
"""
from __future__ import annotations
import argparse
import ast
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import struct
import subprocess
import sys
import time
from types import SimpleNamespace
from . import case_binding as cb

require=cb.require
def configure(source,out,runtime_manifest):
    from . import binding
    return binding.configure(source,runtime_manifest,out)

def pack_expected(expected):
    out={}
    for k,v in expected.items():
        if hasattr(v,'tolist'): v=v.tolist()
        if isinstance(v,list):v=['+inf' if x==math.inf else '-inf' if x==-math.inf else x for x in v]
        out[k]=v
    return out

def unpack_expected(value):
    import numpy as np
    ints={'integrality','a_start','a_index'}
    arrays={'col_lower','col_upper','col_cost','row_lower','row_upper','integrality','a_start','a_index','a_value'}
    require(set(value)==cb.FIDELITY_FIELDS,'Exactly16 expected fields required')
    return {k:np.asarray([math.inf if x=='+inf' else -math.inf if x=='-inf' else x for x in v],
        dtype=np.int32 if k in ints else np.float64) if k in arrays else v for k,v in value.items()}

def accept_readback(report,mps,expected,source,pairs,cfg):
    library=Path(cfg['library']).resolve(); mps=Path(mps)
    identity=dict(source_sha256=cb.sha(source),mps_sha256=cb.sha(mps),expected_sha256=cb.sha(expected),
        pair_manifest_sha256=cb.sha(pairs),hours=36,library_path=str(library),library_sha256=cb.sha(library),
        checker_sha256=cb.PINS['primal-cache-replay-v4.1/core/canonical_mps_export/readback.py'])
    require(all(report.get(k)==v for k,v in identity.items()),'API current identity mismatch')
    require(report.get('passed') is True and report.get('read_status')==0 and report.get('failures')==[] and
        report.get('diagnostics')==[] and report.get('hessian_num_nz')==0 and
        report.get('optimization_or_presolve_called') is False and report.get('highs_int_bytes')==4,'Exact API readback failed')
    fields=report.get('fields',{})
    require(set(fields)==cb.FIDELITY_FIELDS and all(v.get('passed') is True for v in fields.values()),'Incomplete16-field equality')
    symbols=report.get('loaded_symbol_provenance',{})
    require(set(symbols)=={'Highs_create','Highs_readModel','Highs_getLp','Highs_getColName','Highs_getRowName'} and
        all(v.get('path')==str(library) and v.get('sha256')==identity['library_sha256'] for v in symbols.values()),'Loaded symbol provenance mismatch')
    log=Path(str(mps)+'.readback.log')
    require(report.get('log_path')==str(log.resolve()) and report.get('log_sha256')==cb.sha(log) and
        log.stat().st_size<=cb.CAPS['native_file_bytes'] and report.get('bound_record_audit'),'Native diagnostic/bound audit mismatch')
    return identity

def writer_planner():
    from . import preparation_writer
    return preparation_writer

def model_view(e,model):
    senses=[]; rhs=[]
    for lo,hi in zip(e['row_lower'],e['row_upper']):
        if lo==hi and math.isfinite(lo):senses.append('E');rhs.append(float(lo))
        elif lo==-math.inf and math.isfinite(hi):senses.append('L');rhs.append(float(hi))
        elif hi==math.inf and math.isfinite(lo):senses.append('G');rhs.append(float(lo))
        else:raise cb.ContractError('Unsupported canonical row')
    coo=model.matrix(e).tocoo()
    return SimpleNamespace(names=e['col_names'],lb=e['col_lower'],ub=e['col_upper'],obj=e['col_cost'],
        binary=[bool(v) for v in e['integrality']],sense=senses,rhs=rhs,ri=coo.row.tolist(),ci=coo.col.tolist(),val=coo.data.tolist())

def _serialize(view,e,path,exporter,model):
    planner=writer_planner(); planned=planner.canonical_mps_reservation(view,e)
    cb.write(str(path)+'.expected.json',pack_expected(e))
    meta=exporter.write_model(view,path,{'hours':36,'mode':'n1','active_pairs':[]},expected=e)
    planned['readback']=planner.verify_written_mps(path,planned)
    return dict(writer_reservation=planned,canonical_metadata=meta,model_hashes=model.model_hashes(e))

def _runtime(request):
    cfgpath=cb.check_record(request['runtime_config']); os.environ['PRIMAL_CACHE_CONFIG']=str(cfgpath)
    os.environ['PRIMAL_CACHE_CONFIG_SHA256']=request['runtime_config']['sha256']
    from . import binding
    runtime=binding.verify_freeze(); return binding.config(),runtime

def generate(request,out):
    cfg,runtime=_runtime(request); cb.verify_pinned_sources()
    source=request['source']['path'];data=cb.read_source(source); derived=cb.source_contract(data)
    cb.write(out/'prospective-source.json',{k:v for k,v in derived.items() if k not in ('column_names','universe')})
    cb.write(out/'pairs.json',[])
    guard=cb.module('heldout_resource_guard',cb.CORE/'driver/resource_guard.py')
    allocation=guard.projected_master(data,36,derived['universe'],[])
    require(shutil.disk_usage(out).free>2*1024**3+cb.CAPS['raw_artifact_bytes'],'Disk headroom before generation')
    exporter=cb.module('export_v2',cb.CORE/'canonical_mps_export/export_v2.py')
    generator,lineage=exporter.load_generator(cb.CORE/'scuc/generate.py')
    tick=time.monotonic(); built,network=generator.build(data,36,'n1',[])
    allocation['actual']=guard.actual_master(built,allocation)
    model=cb.module('model',cb.source_path('network-projection-lp-core-v1/model.py'))
    original=model.validate_model(exporter.intended_model(built))
    shapes,scope=cb.model_contract(original,data,derived)
    original_record=_serialize(built,original,out/'original.mps',exporter,model)
    del built
    common_generation_seconds=time.monotonic()-tick
    retained_tick=time.monotonic()
    # Fresh factors bind current topology; factors are not serialized or reused by arms.
    buses,lines,A,w,outages,lodf,minden=generator.factors(data)
    require(buses==derived['topology']['ordered_bus_ids'] and lines==derived['topology']['ordered_line_ids'] and
        outages==derived['topology']['ordered_outage_indices'],'Fresh factor order differs from source')
    topology=dict(derived['topology'],lodf_binary64_C_sha256=hashlib.sha256(lodf.astype('<f8',copy=False).tobytes(order='C')).hexdigest(),minimum_outage_denominator=minden)
    adapter=cb.module('heldout_frozen_family_adapter',cb.source_path('first-start-adaptive-integer-v1/family_model_adapter.py'))
    retained,metadata=adapter.make_base(original,data,36,[],lodf,cb.sha(source),'preparation-only-no-search')
    import numpy as np
    retained=dict(retained,integrality=np.zeros(retained['num_col'],dtype=np.int32),row_names=[f'R{i}' for i in range(retained['num_row'])])
    retained=model.validate_model(retained)
    require({k:retained[k] for k in ('num_col','num_row','num_nz')}==shapes['projected_base'],'Independent projected shape mismatch')
    require(all(shapes['projected_first_start'][key]<=cb.CAPS[cap] for key,cap in
        [('num_col','candidate_columns'),('num_row','candidate_rows'),('num_nz','candidate_nonzeros')]),'Prospective candidate base exceeds unchanged caps')
    retained_record=_serialize(model_view(retained,model),retained,out/'retained.mps',exporter,model)
    cb.write(out/'generation.json',dict(passed=True,allocation=allocation,network=network,lineage=lineage,shapes=shapes,scope=scope,
        topology=topology,original=original_record,retained=retained_record,generation_seconds=time.monotonic()-tick,
        common_original_generation_seconds=common_generation_seconds,
        candidate_specific_retained_projection_serialization_seconds=time.monotonic()-retained_tick,
        retained_artifacts_role='candidate-specific verification authority only; never input model/state for either timed arm',
        runtime_source_manifest_sha256=runtime['source_manifest_sha256'],optimization_or_presolve_called=False))
    _runtime(request)

def readback(request,out):
    cfg,_=_runtime(request)
    times={}
    exporter=cb.module('export_v2',cb.CORE/'canonical_mps_export/export_v2.py')
    reader=cb.module('readback',cb.CORE/'canonical_mps_export/readback.py')
    native=cb.module('heldout_native_limits',cb.ROOT/'native_exec.py')
    from . import runtime
    tick=time.monotonic()
    with native.native_output_guard() as native_limit:
        qualification=runtime.qualify_capi(runtime.discover_runtime(cfg['binary'],cfg['runtime_manifest']))
    qualification['native_output_limit']=native_limit
    cb.write(out/'native-qualification.json',qualification)
    times['native_runtime_qualification_seconds']=time.monotonic()-tick
    for name in ('original','retained'):
        tick=time.monotonic()
        mps=out/(name+'.mps'); expected=Path(str(mps)+'.expected.json')
        e=unpack_expected(cb.read(expected))
        with native.native_output_guard() as native_limit:
            report=reader.verify_expected(e,mps,cfg['library'],str(mps)+'.readback.log')
        report['native_output_limit']=native_limit
        report.update(source_sha256=request['source']['sha256'],expected_sha256=cb.sha(expected),
            pair_manifest_sha256=cb.sha(out/'pairs.json'),hours=36,kind='mip' if name=='original' else 'retained_continuous_authority')
        accept_readback(report,mps,expected,request['source']['path'],out/'pairs.json',cfg)
        cb.write(str(mps)+'.readback.json',report)
        times['common_original_api_readback_seconds' if name=='original' else 'candidate_specific_retained_api_readback_seconds']=time.monotonic()-tick
    cb.write(out/'readback-timings.json',times)
    _runtime(request)

def verify_request(request_path,request_sha):
    require(sys.dont_write_bytecode and __debug__,'Require Python -B and assertions')
    require(cb.sha(request_path)==request_sha,'Preparation request changed')
    request=cb.read(request_path)
    require(request['schema']=='current-scuc-preparation-request/v1' and request['case']==cb.CASE and
        request['mapping_pairs']==[],'Preparation request case/scope')
    require(request['generation_and_api_readback_allowed'] is True and request['optimizer_allowed'] is False,
        'Preparation request scope changed')
    cb.check_record(request['source']); cb.check_record(request['runtime_config'])
    cfg,_=_runtime(request)
    require(cfg['inputs']=={'current':request['source']},'Preparation source differs from runtime binding')
    cb.verify_pinned_sources()
    return request

def _usage(out,pid=None):
    files=[p for p in out.rglob('*') if p.is_file()]; sizes=[p.stat().st_size for p in files]
    require(len(files)<=1024 and sum(sizes)<=cb.CAPS['raw_artifact_bytes'],'Common artifact storage ceiling')
    for path,size in zip(files,sizes):
        cap=cb.CAPS['native_file_bytes'] if path.name.endswith('.readback.log') else cb.CAPS['python_file_bytes']
        require(size<=cap,'Common output file ceiling: '+str(path))
    require(shutil.disk_usage(out).free>=2*1024**3,'Disk headroom lost')
    if pid is not None:
        try:status=Path(f'/proc/{pid}/status').read_text()
        except FileNotFoundError:return
        match=re.search(r'^VmRSS:\s+(\d+) kB$',status,re.M)
        if match: require(int(match[1])*1024<=cb.CAPS['rss_bytes'],'Common worker RSS cap')
    mem=Path('/proc/meminfo').read_text(); available=int(re.search(r'^MemAvailable:\s+(\d+) kB$',mem,re.M)[1])*1024
    require(available>=cb.CAPS['physical_headroom_bytes'],'Physical memory headroom lost')

def run_worker(kind,args,cfg,out,deadline):
    started=time.monotonic(); limit=min(deadline,started+cb.CAPS['worker_seconds'])
    require(limit>started,'No preparation allocation remains')
    from . import binding
    env=binding.environment(out)
    command=[cfg['python'],'-B','-m','current_scuc.preparation','--worker',kind,'--request',args.request,
        '--request-sha256',args.request_sha256,'--out',str(out)]
    with (out/(kind+'.log')).open('xb') as log:
        child=subprocess.Popen(command,env=env,cwd=str(cb.ROOT.parent),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while child.poll() is None:
                require(time.monotonic()<limit,'Common preparation worker/phase deadline')
                _usage(out,child.pid);time.sleep(.05)
            require(child.returncode==0,'Common '+kind+' worker failed; retained log: '+str(out/(kind+'.log')))
        finally:
            if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
            child.wait()
    elapsed=time.monotonic()-started
    require(elapsed<=limit-started,'Worker returned after its effective preparation allocation')
    return dict(kind=kind,actual_start_through_reap_seconds=elapsed,exit_code=child.returncode,
        worker_ceiling_seconds=cb.CAPS['worker_seconds'],effective_allocation_seconds=limit-started)

def finalize(request,out):
    """Only runs after both contained workers finish and all readbacks pass."""
    cfg,_=_runtime(request)
    gen=cb.read(out/'generation.json'); derived=cb.read(out/'prospective-source.json')
    ledger=cb.read(out/'worker-ledger.json');timings=ledger['workers'];elapsed=ledger['elapsed_before_certificate_worker_seconds']
    cfg=cb.read(request['runtime_config']['path'])
    model={}
    for name,prefix in [('original',''),('retained','retained_')]:
        for key,suffix in [('mps',''),('expected','.expected.json'),('readback','.readback.json')]:
            model[prefix+key]=cb.record(out/(name+'.mps'+suffix))
    model.update(pairs=cb.record(out/'pairs.json'),metadata=cb.record(out/'generation.json'))
    value=dict(schema=cb.SCHEMA,case=cb.CASE,source=request['source'],model=model,mapping_pairs=[],
        runtime=dict(config=request['runtime_config'],upstream_commit=cb.COMMIT),scope=gen['scope'],topology=gen['topology'],
        first_start=derived['first_start'],hard_zero=derived['hard_zero'],shapes=gen['shapes'],caps=cb.CAPS,
        provenance=dict(production_scope=True,optimization_or_presolve_called=False,
            **{k:derived[k] for k in ('source_object_sha256','source_ordered_sha256','source_names_sha256','binary_names_sha256')},
            original_model_hashes=gen['original']['model_hashes'],retained_model_hashes=gen['retained']['model_hashes'],
            source_manifest=cfg['source_manifest'],acquisition=request['acquisition'],
            setup_elapsed_before_certificate_worker_seconds=elapsed,workers=timings,
            common_original_generation_seconds=gen['common_original_generation_seconds'],
            candidate_specific_retained_projection_serialization_seconds=gen['candidate_specific_retained_projection_serialization_seconds'],
            **cb.read(out/'readback-timings.json'),
            retained_artifacts_role=gen['retained_artifacts_role'],
            timed_candidate_rebuilds_fresh_projection_factors_and_pays_certificate_comparison=True,
            identical_original_serialized_input_for_both_arms=True))
    # This post-readback operation only reads arrays/bounds and verifies an exact
    # certificate. It never generates another model or opens a native library.
    mm=cb.module('model',cb.source_path('network-projection-lp-core-v1/model.py'))
    from . import zero_cost
    original=mm.validate_model(unpack_expected(cb.read(model['expected']['path'])))
    retained=mm.validate_model(unpack_expected(cb.read(model['retained_expected']['path'])))
    certificate=zero_cost.certify_for_case(cb.read_source(request['source']['path']),original,retained,value,mm)
    cb.write(out/'zero-certificate.json',certificate);value['model']['zero_certificate']=cb.record(out/'zero-certificate.json')
    cb.validate(value);cb.verify_inputs(value);cb.write(out/'CASE.json',value)
    _runtime(request)
    return value

def prepare(instance,runtime_config_path,workdir):
    """Build fresh original/retained authorities under one 600-second deadline.

    runtime_config_path accepts a local native runtime manifest or an already
    bound current-scuc driver config. No prior prepared matrix is accepted.
    """
    started=time.monotonic()
    from . import binding
    binding.source_only()
    source=Path(instance).resolve(); require(source.is_file(),'Local instance file is required')
    out=binding.fresh_directory(workdir)
    supplied=Path(runtime_config_path).resolve()
    cfg_value=cb.read(supplied)
    if cfg_value.get('schema')=='current-scuc-runtime-binding/v1':
        cfgpath=supplied
    else:
        cfgpath=out/'runtime.config.json'
        configure(source,cfgpath,supplied)
    os.environ['PRIMAL_CACHE_CONFIG']=str(cfgpath)
    os.environ['PRIMAL_CACHE_CONFIG_SHA256']=cb.sha(cfgpath)
    cfg=binding.config()
    os.environ['CURRENT_SCUC_RUNTIME_MANIFEST']=cfg['runtime_manifest']
    request=dict(schema='current-scuc-preparation-request/v1',case=cb.CASE,source=cb.record(source),
        runtime_config=cb.record(cfgpath),mapping_pairs=[],generation_and_api_readback_allowed=True,optimizer_allowed=False,
        acquisition=dict(kind='user_supplied_local_instance',source=cb.record(source)))
    request_path=out/'request.json';cb.write(request_path,request)
    args=SimpleNamespace(request=str(request_path),request_sha256=cb.sha(request_path))
    verify_request(args.request,args.request_sha256)
    timings=[]
    with Path(cfg['numerical_lock']).open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            _usage(out)
            deadline=started+cb.CAPS['preparation_seconds']
            for kind in ('generate','readback'):timings.append(run_worker(kind,args,cfg,out,deadline))
            require(time.monotonic()<deadline,'Common preparation phase deadline')
            cb.write(out/'worker-ledger.json',dict(workers=timings,elapsed_before_certificate_worker_seconds=time.monotonic()-started))
            timings.append(run_worker('finalize',args,cfg,out,deadline))
            require(time.monotonic()<=deadline,'Common preparation finalization phase cap')
            _usage(out)
            cb.write(out/'COMPLETE.json',dict(passed=True,case=cb.record(out/'CASE.json'),workers=timings,
                complete_preparation_seconds=time.monotonic()-started,optimization_or_presolve_called=False,optimizer_released=False))
        except BaseException as exc:
            cb.write(out/'FAILURE.json',dict(passed=False,error=type(exc).__name__+': '+str(exc),workers=timings,
                complete_preparation_seconds=time.monotonic()-started,optimizer_released=False))
            raise
    return out/'CASE.json'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--worker',choices=('generate','readback','finalize'))
    for name in ('request','request-sha256','out','instance','runtime-manifest','workdir'):ap.add_argument('--'+name)
    args=ap.parse_args()
    if args.worker:
        require(args.request and args.request_sha256 and args.out,'Explicit worker request/hash/output required')
        resource.setrlimit(resource.RLIMIT_AS,(cb.CAPS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_FSIZE,(cb.CAPS['python_file_bytes'],)*2)
        request=verify_request(args.request,args.request_sha256);out=Path(args.out).resolve()
        require(out.is_dir() and not out.is_relative_to(cb.HERE),'External preparation output required')
        globals()[args.worker](request,out)
    else:
        require(args.instance and args.runtime_manifest and args.workdir,'Explicit instance, runtime manifest and fresh workdir required')
        print(prepare(args.instance,args.runtime_manifest,args.workdir))

if __name__=='__main__':main()
