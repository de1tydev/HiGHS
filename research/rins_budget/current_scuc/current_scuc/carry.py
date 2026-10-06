#!/usr/bin/env python3
"""One contained fresh-incumbent mapping. No optimizer, presolve or factorization."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import time
START = time.monotonic()
import argparse
from fractions import Fraction as F
import math
import copy
from pathlib import Path
import subprocess
import sys
BASE = PACKAGE_ROOT
import numpy as np
import current_scuc.containment as g
from current_scuc.common import ROOT, require, finite, module, storage, native_limits, bounded_write, start_output_phase, native_shape_guard

HELPER_SOURCE_SHA256 = 'b7cd24d5852080cde20e2d0e269783090bfc004fa2f82fb30f92c9b3ecc73d4a'
SCHEMA = 'adaptive-line-incumbent-carry/v1'


def checked_solver_random_seed(state, arm=None):
    """Bind typed worker, LP and every recorded native call to one run seed."""
    from current_scuc.native_exec import validate_solver_random_seed, parse_solver_random_seed
    selected=validate_solver_random_seed(state['solver_random_seed'])
    seed=state['seed']
    require(validate_solver_random_seed(seed['solver_random_seed'])==selected and
        validate_solver_random_seed(seed['native_options']['random_seed'])==selected,
        'carry state/LP solver seed mismatch')
    if arm is not None:
        require(validate_solver_random_seed(arm['solver_random_seed'])==selected,
            'carry arm/state solver seed mismatch')
    for row in state['trace']:
        require(validate_solver_random_seed(row['solver_random_seed'])==selected,
            'carry trace solver seed mismatch')
        command=row['command']
        require(command.count('--random_seed')==1 and
            parse_solver_random_seed(command[command.index('--random_seed')+1])==selected,
            'carry command solver seed mismatch')
        require(row['native_limit_request']['argv']==command,
            'carry native request/command mismatch')
    return selected


def same_transition_master(source, destination):
    """Only fresh export metadata and one non-installed evaluation may differ."""
    fields=('master_hashes','canonical_master_hashes','model_sha256','expected_sha256',
        'row_sidecar_sha256','integer_target','integer_target_identity_sha256','hard_zero_subset',
        'network_oracle_identity_sha256','source_binary_inventory','adaptive_map_hash',
        'adaptive_matrix_identity','adaptive_line_caps','first_start_family')
    for key in fields:
        require(key in source and source[key]==destination.get(key),'transition changed master '+key)
    before=source['adaptive_activation'];after=destination['adaptive_activation']
    require(before['evaluations']==2 and before['admitted']==2 and
        after==dict(before,evaluations=3),'transition changed activation beyond one evaluation')


def transition_evidence(state, *, production=True, checked=None):
    """Revalidate the checked discovery source, including its actual saved bytes."""
    module('binding',ROOT/'binding.py')
    import current_scuc.options as options; import current_scuc.process_runner as process_runner; import current_scuc.no_shedding as no_shedding
    solver_random_seed=checked_solver_random_seed(state)
    run=Path(state['run_directory']).resolve();row=state['trace'][0];rd=run/'mip-01'
    require(state.get('quality_failed') is False and state.get('mechanism_failed') is False,
        'transition after quality/mechanism failure')
    require(row['call']==1 and type(row['call']) is int and row['role']=='discovery' and
        row.get('incumbent_input') is None and row.get('no_basis_or_search_state_input') is True and
        'inserted_batch_artifact' not in row,'transition requires cold uninserted call-1 discovery')
    process_runner.require_clean(row['process'])
    require(finite(row['native_limit_seconds']) and 0<row['native_limit_seconds']<=120. and
        finite(row['allocation_seconds']) and row['allocation_seconds']<=180.,'transition source allocation changed')
    report=row['report']
    require(report.get('role')=='discovery' and report.get('status')=='Solution limit reached' and
        report.get('discovery_stop_activated') is True and report.get('model_definition_diagnostics')==[] and
        all(report.get(k) is True for k in ('clean_return','loaded_library_identity_valid',
            'identities_valid','parent_report_identity_valid')),'transition requires clean SolutionLimit discovery')
    require(report.get('bound_status_valid') is False and report.get('certificate_bound_eligible') is False and
        report.get('global_lower') is None,'discovery bound must remain diagnostic')
    require(row['master_quality'].get('passed') is True and row['master_quality'].get('point_rounded') is False,
        'transition missing unrounded current-master check')
    select_point({'trace':[row]},2)
    span=row['selected_endpoint_interval'];support=row['continuation_support']
    from current_scuc.diagnostics import interval
    require(span==interval(span.get('lower'),span.get('upper')) and span['passed'] is True and
        span['qualified'] is False and span['gap']>.01 and row['selected_endpoint_call']==1 and
        span['upper']==row['evaluation']['provisional_upper'],'transition requires checked open selected interval')
    require(support.get('passed') is False and support.get('materially_violated_rows')==0 and
        support.get('threshold_MW')==1e-5 and finite(support.get('maximum_positive_residual_MW')) and
        0<=support['maximum_positive_residual_MW']<=1e-5,'transition has materially violated or unchecked support')
    identity=row['master_identity'];ev=row['evaluation']
    require(identity['integer_target_identity_sha256']==state['integer_target_identity_sha256'] and
        ev['full_scope_identity_sha256']==identity['network_oracle_identity_sha256'] and
        ev['target_subset_quality']['subset_identity_sha256']==identity['hard_zero_subset']['identity_sha256'],
        'transition target/scope/subset mismatch')
    files={}
    def read(path,digest):
        p=local(path,run)
        require(p.is_file() and not p.is_symlink() and g.sha(p)==digest,'transition artifact changed '+str(p))
        files[str(p)]=digest
        if checked is not None:checked(p,digest,inside=True)
        return p
    for key in ('model','expected','api_report','row_sidecar'):
        read(identity[key+'_path'],identity[key+'_sha256'])
    require(Path(identity['model_path']).resolve()==rd/'master.mps','transition foreign source master')
    binding=row['options_artifacts']
    opt=read(binding['options_path'],binding['options_sha256'])
    readback=read(binding['readback_path'],binding['readback_sha256'])
    require(opt==rd/'solver.options' and readback==rd/'options-readback.json' and
        opt.read_text()==options.option_text('discovery'),'transition source option path/bytes')
    probe=g.strict(readback)
    expected=options.expected_options('discovery',row['native_limit_seconds'],start=None,solver_random_seed=solver_random_seed)
    from current_scuc.native_exec import validate_solver_random_seed
    require(validate_solver_random_seed(probe['solver_random_seed'])==solver_random_seed and
        validate_solver_random_seed(probe['options']['random_seed'])==solver_random_seed and
        probe.get('passed') is True and probe.get('role')=='discovery' and
        probe['options_sha256']==binding['options_sha256'] and
        probe['options']=={k:v for values in expected.values() for k,v in values.items()},'transition discovery readback changed')
    native_path=rd/'native-exec.json';read(native_path,g.sha(native_path))
    require(native_limits().verify_receipt(native_path,row['native_limit_request'],process_receipt=row['process'])==
        row['native_limit_receipt'],'transition native receipt changed')
    for artifact in (state['seed']['batches_artifact'],):
        for key in ('document','arrays'):
            if key in artifact:read(run/'seed'/artifact[key]['path'],artifact[key]['sha256'])
    for name in ('adaptive_support_artifact','stored_lift_artifact','oracle_artifact',
                 'full_source_quality_artifact','source_quality_artifact'):
        for key in ('document','arrays'):
            if key in ev[name]:read(rd/ev[name][key]['path'],ev[name][key]['sha256'])
    if production:
        stage=bind_checked_stage(row['checked_archive'],run,1,state['source_manifest_sha256'],expected_row=row)
        require(stage==row['checked_stage_binding'],'transition checked-stage binding changed')
        for path,digest in stage['metadata_files_sha256'].items():read(path,digest)
    else:
        stage=row['checked_stage_binding']
        require(Path(stage['path']).resolve()==rd/'tiny-point-check.json' and
            Path(row['checked_archive']).resolve()==Path(stage['path']).resolve(),'transition tiny checked-point path')
        read(stage['path'],stage['sha256'])
    return dict(source_call=1,destination_call=2,source_role='discovery',destination_role='proof',
        solver_random_seed=solver_random_seed,
        source_manifest_sha256=state['source_manifest_sha256'],arm_manifest_sha256=state['arm_manifest_sha256'],
        source_row_sha256=no_shedding.digest(row),source_master_identity=copy.deepcopy(identity),
        installed_cut_prefix=[dict(source='seed',artifact=copy.deepcopy(state['seed']['batches_artifact']))],
        evaluated_support_artifact=copy.deepcopy(ev['adaptive_support_artifact']),
        source_options_artifacts=copy.deepcopy(binding),checked_stage_binding=copy.deepcopy(stage),files_sha256=files)


def schedule_transition(state, cut_prefix, *, carry_allocation, proof_allocation, production=True):
    """Consume the only exception before preparation; failure never restores it."""
    require('discovery_proof_transition' not in state and state.get('carry_preparations')==[] and
        len(state['trace'])==1,'transition already used or prior attempt exists')
    require(finite(carry_allocation) and 1<carry_allocation<=30. and finite(proof_allocation) and
        60.<proof_allocation<=180.,'transition lacks carry/proof resource window')
    evidence=transition_evidence(state,production=production)
    require(state['cut_batches']==2 and cut_prefix==evidence['installed_cut_prefix'],'transition requires exact two-seed prefix')
    if production:
        ledger=state['ledger']
        require(ledger['in_budget'] is True and ledger['ceiling_seconds']==600. and
            ledger['remaining']>=carry_allocation+proof_allocation and
            [r['stage'] for r in ledger['calls']]==['seed','mip'] and
            all(r['within_allocation'] is True for r in ledger['calls']),'transition ledger chronology')
    record=dict(schema='discovery-proof-transition/v1',consumed=True,outcome='scheduled',
        carry_allocation_at_schedule=carry_allocation,proof_allocation_at_schedule=proof_allocation,evidence=evidence)
    state['discovery_proof_transition']=record
    return record


def validate_transition(state, target_call, *, stage='preparation', production=True, checked=None):
    record=state['discovery_proof_transition']
    require(record.get('schema')=='discovery-proof-transition/v1' and record.get('consumed') is True,
        'missing consumed discovery/proof transition')
    require(type(target_call) is int and target_call in (2,3) and
        all(type(r['call']) is int for r in state['trace']) and
        [r['call'] for r in state['trace']]==list(range(1,target_call)), 'transition malformed call chronology')
    require(record['evidence']==transition_evidence(state,production=production,checked=checked),
        'transition source evidence changed')
    preparations=state['carry_preparations']
    expected=list(range(2,target_call+1)) if stage!='scheduled' else []
    require(all(type(r['target_call']) is int for r in preparations) and
        [r['target_call'] for r in preparations]==expected,'transition missing/duplicate preparation')
    if stage=='preparation':require('preparation' not in preparations[-1] and 'process' not in preparations[-1],
        'transition preparation already attempted')
    if target_call==2:
        require(record['outcome']=='scheduled','transition proof already attempted')
    else:
        proof=state['trace'][1]
        require(stage!='scheduled' and record['outcome']=='proof_checked' and proof['role']=='proof' and
            preparations[0].get('preparation',{}).get('passed') is True and
            preparations[0]['preparation'].get('result_complete') is True and
            proof.get('start_admission',{}).get('passed') is True and
            proof.get('continuation_support',{}).get('passed') is True and
            proof['continuation_support'].get('threshold_MW')==1e-5 and
            proof['continuation_support'].get('materially_violated_rows',0)>0 and
            finite(proof['continuation_support'].get('maximum_positive_residual_MW')) and
            proof['continuation_support']['maximum_positive_residual_MW']>1e-5 and
            proof.get('inserted_batch_artifact')==proof['evaluation']['adaptive_support_artifact'],
            'transition call3 requires checked proof and real support insertion')
        same_transition_master(record['evidence']['source_master_identity'],proof['master_identity'])
        binding=record['proof_options_artifacts']
        require({k:v for k,v in binding.items() if k!='incumbent_input'}==proof['options_artifacts'] and
            binding['incumbent_input']==proof['incumbent_input'],'transition proof options/start binding changed')
        for prefix in ('options','readback'):
            path=local(binding[prefix+'_path'],Path(state['run_directory']).resolve())
            require(g.sha(path)==binding[prefix+'_sha256'],'transition proof option artifact changed')
            if checked is not None:checked(path,binding[prefix+'_sha256'],inside=True)
    return record


def verify_transition_proof(state, identity, probe, start, *, production=True):
    """Called after preparation and saved option readback, immediately prelaunch."""
    import current_scuc.options as options
    record=validate_transition(state,2,stage='prepared',production=production)
    same_transition_master(record['evidence']['source_master_identity'],identity)
    prepared=state['carry_preparations'][0]['preparation']
    require(prepared['passed'] is True and Path(start).resolve()==Path(prepared['start']['path']).resolve(),
        'transition actual proof start differs from preparation')
    solver_random_seed=checked_solver_random_seed(state)
    from current_scuc.native_exec import validate_solver_random_seed
    require(validate_solver_random_seed(prepared['solver_random_seed'])==solver_random_seed,
        'transition prepared solver seed mismatch')
    expected=options.expected_options('proof',probe['options']['time_limit'],start=start,solver_random_seed=solver_random_seed)
    rd=Path(identity['model_path']).parent;opt=rd/'solver.options';readback=rd/'options-readback.json'
    require(validate_solver_random_seed(probe['solver_random_seed'])==solver_random_seed and
        validate_solver_random_seed(probe['options']['random_seed'])==solver_random_seed and
        probe.get('passed') is True and probe.get('role')=='proof' and
        probe['options']=={k:v for values in expected.values() for k,v in values.items()} and
        opt.read_text()==options.option_text('proof') and g.sha(opt)==probe['options_sha256'] and
        g.strict(readback)==probe,'transition proof option/readback mismatch')
    record['proof_options_artifacts']=dict(options_path=str(opt),options_sha256=g.sha(opt),
        readback_path=str(readback),readback_sha256=g.sha(readback),incumbent_input=str(Path(start).resolve()))
    return record


def replay_transition_prefix(base, metadata, seeds, discovery, proof=None):
    """The one allowed skipped install still consumes its exact evaluation."""
    import current_scuc.adaptive as adaptive
    require(len(seeds)==2,'transition needs exactly two seed installs')
    current,metadata=adaptive.replay(base,metadata,seeds)
    require(metadata['activation']['admitted']==metadata['activation']['evaluations']==2,
        'transition seed counts')
    metadata=adaptive.terminal(current,metadata,discovery)
    if proof is not None:current,metadata,_=adaptive.install(current,metadata,proof)
    expected=2+(proof is not None)
    require(metadata['activation']['admitted']==expected and metadata['activation']['evaluations']==expected+1,
        'transition replay counts')
    return current,metadata


def local(path, run):
    p=Path(path).resolve()
    require(p.is_relative_to(run),'carry artifact outside current fresh run')
    return p


def select_point(state, target_call):
    """Select by checked original U, with exact ties resolved by earlier call."""
    require(target_call in (2,3),'carry only for calls 2/3')
    eligible=[]
    for row in state['trace']:
        call=row['call']
        require(type(call) is int and 1<=call<target_call,'invalid prior call chronology')
        ev=row.get('evaluation')
        if ev is None: continue
        require(finite(ev.get('provisional_upper')),'nonfinite checked original upper')
        require(ev.get('target_subset_quality',{}).get('passed') is True,'prior point lacks target-subset check')
        require(ev['original_integer_quality']['passed'] is True and
            ev['original_integer_quality']['point_rounded'] is False and
            ev['source_quality']['passed'] is True and ev['full_source_quality']['passed'] is True and
            ev['full_source_quality']['zero_radius'] is True and
            ev['full_source_quality']['full_scope_coverage_complete'] is True,'prior point lacks complete checks')
        require(row.get('checked_archive'),'prior checked archive missing')
        eligible.append(row)
    require(eligible and len({r['call'] for r in eligible})==len(eligible),'missing/duplicate prior checked points')
    return min(eligible,key=lambda r:(r['evaluation']['provisional_upper'],r['call']))


def bind_checked_stage(receipt_path, run, call, source_manifest_sha256, *, expected_row):
    """Bind this checked point to LOCAL retained archive/state; never claim cloud ACK."""
    local_checkpoints=module('_heldout_local_checkpoint',ROOT/'receipts.py')
    return local_checkpoints.bind_checked_stage(receipt_path,run,call,source_manifest_sha256,expected_row)


def read_start(path,names,x,objective):
    """Fail closed on the actual full column-only file before either native entry."""
    require(len(names)==len(x) and len(set(names))==len(names),'duplicate/missing column')
    require(np.isfinite(x).all() and finite(float(objective)),'nonfinite point/objective')
    lines=Path(path).read_text().splitlines()
    header=['Model status','Not Set','','# Primal solution values','Feasible',
        'Objective '+format(float(objective),'.17g'),'# Columns '+str(len(x))]
    require(lines[:7]==header and len(lines)==7+len(x),'incomplete/extra start columns or sections')
    actual_names=[];values=[]
    for line in lines[7:]:
        parts=line.split();require(len(parts)==2,'malformed start column')
        actual_names.append(parts[0]);values.append(float(parts[1]))
    require(actual_names==names and len(set(actual_names))==len(names),'unknown/duplicate/missing start names')
    actual=np.asarray(values,dtype=np.float64)
    require(np.isfinite(actual).all(),'nonfinite start column')
    g.same(actual,x,'start readback point bits mismatch')
    return dict(path=str(Path(path).resolve()),sha256=g.sha(path),point_values_sha256=g.bits(actual),
        columns=len(names),format='raw column-only .17g',complete=True)


def verify_prepared(record, request_path, request_sha256, identity):
    """Parent rehashes the actual input and all carry evidence immediately prelaunch."""
    require(g.sha(request_path)==request_sha256 and record['request_sha256']==request_sha256,'carry request changed')
    require(record['passed'] is True and record['result_complete'] is True,'incomplete carry preparation')
    require(record['target_master_identity']==identity,'carry destination changed')
    request=g.strict(Path(request_path))
    arm_path=Path(request['arm_manifest_path'])
    require(g.sha(arm_path)==request['arm_manifest_sha256'],'carry arm changed')
    from current_scuc.native_exec import validate_solver_random_seed
    require(validate_solver_random_seed(record['solver_random_seed'])==
        validate_solver_random_seed(g.strict(arm_path)['solver_random_seed']),
        'prepared carry solver seed mismatch')
    for path,digest in {**record['consumed_files_sha256'],**record['evidence_files_sha256']}.items():
        require(g.sha(path)==digest,'carry consumed artifact changed: '+path)
    require(g.sha(record['start']['path'])==record['start']['sha256'],'prepared start changed')
    require(g.sha(runtime_path('projected-start-containment-build-v1/native_assess'))==runtime_sha('native_assess') and g.sha(runtime_path('projected-start-containment-v3/native_assess.cpp'))==HELPER_SOURCE_SHA256,'assessment helper changed')
    return Path(record['start']['path'])


def assess(current,x,activities,mps,start,out,library,library_sha256,deadline,model):
    require(g.sha(runtime_path('projected-start-containment-build-v1/native_assess'))==runtime_sha('native_assess') and g.sha(runtime_path('projected-start-containment-v3/native_assess.cpp'))==HELPER_SOURCE_SHA256,'assessment helper identity')
    native_shape_guard(current)
    command=[str(runtime_path('projected-start-containment-build-v1/native_assess').resolve()),str(Path(mps).resolve()),str(Path(start).resolve()),str((out/'native.bin').resolve()),str((out/'native.log').resolve())]
    budget=storage()
    start_output_phase(out,'native carry assessment',[budget.WriteBound(out/name,budget.NATIVE_FILE_LIMIT,
        'three fixed standalone assessment outputs','native exec64MiB file limit') for name in ('native-process.log','native.log','native.bin')])
    native_limit=native_limits()
    wrapped,limit_evidence=native_limit.build_command(command,cwd=out,receipt_path=out/'native-exec.json',
        executable_sha256=runtime_sha('native_assess'),python=sys.executable,solver=False,expected_library_path=str(Path(library).resolve()),
        expected_library_sha256=library_sha256)
    remaining=deadline-time.monotonic();require(remaining>0,'no native assessment window')
    with (out/'native-process.log').open('x') as log:
        with subprocess.Popen(wrapped,stdout=log,stderr=subprocess.STDOUT) as child:
            try:child.communicate(timeout=remaining)
            except BaseException:
                child.kill();child.wait();raise
            helper_pid,helper_returncode=child.pid,child.returncode
    require(helper_returncode==0,'native assessment process failure')
    native_limit_record=native_limit.verify_receipt(out/'native-exec.json',limit_evidence,expected_pid=helper_pid)
    loaded,loaded_x,native_rows,native=g.read_native(out/'native.bin')
    loaded_library=Path(native['loaded_library_path']).resolve()
    require(loaded_library==Path(library).resolve() and g.sha(loaded_library)==library_sha256,'native loaded library provenance')
    compare=model.compare_models(current,loaded,infinity=native['infinity'])
    require(compare['passed'],'native sixteen-field model mismatch')
    representations=[]
    for field in model.ARRAY_FIELDS:
        expected=current[field]
        if field in ('col_lower','col_upper','row_lower','row_upper'):
            expected=np.where(expected==np.inf,native['infinity'],np.where(expected==-np.inf,-native['infinity'],expected))
        if field in ('row_lower','row_upper'):
            representations.append(g.row_bound_equivalence(expected,loaded[field],field))
        else:g.same(expected,loaded[field],'native exact field bits '+field)
    g.same(loaded_x,x,'native point column bits mismatch')
    require(np.isfinite(native_rows).all(),'native row activity nonfinite')
    difference=max((abs(F(float(a))-F(float(b))) for a,b in zip(native_rows,activities)),default=F(0))
    require(difference<=F(1e-7),'native/exact-rounded row disagreement')
    require(native['mip_tolerance']==1e-6 and native['primal_row_consistency_tolerance']==1e-7,'native tolerances changed')
    require(native['status']==0 and all(native[k] is True for k in ('valid','integral','feasible','value_valid')),'native assessment rejected full start')
    require(g.sha(runtime_path('projected-start-containment-build-v1/native_assess'))==runtime_sha('native_assess'),'assessment executable changed')
    return dict(native=g.native_json_metadata(native),native_matrix_exact_readback=compare,
        row_bound_representation=representations,native_point_bits_equal=True,
        exact_rounded_vs_native_max_row_difference=g.rat(difference),native_command=command,native_limit_request=limit_evidence,native_limit_receipt=native_limit_record,native_helper_pid=helper_pid,native_helper_returncode=helper_returncode)


def prepare_point(original,current,metadata,oracle,lift,ev,bridge,out,*,production=True):
    """Shared exact mapping/serializer gate; every failure precedes native entry."""
    model=bridge.helpers().model
    x,mapping=g.mapping_point(original,current,metadata,oracle,lift,ev,bridge,production=production)
    exact,activities=g.exact_check(current,x,model)
    require(exact['passed'],'current master exact containment failed')
    import current_scuc.first_start as first_start
    first_start.validate(current,metadata['first_start_family'],model,canonical=True)
    exact['first_start_family']=first_start.check_point(current,metadata['first_start_family'],x,tolerance=g.TOL)
    require(g.unrat(exact['projected_objective_exact'])==g.unrat(mapping['original_point_exact_objective'])-
        g.unrat(mapping['inactive_canonical_penalty_dollars'])+g.unrat(mapping['eta_total_rounding_excess_dollars']),'original/projected exact objective bridge')
    budget=storage()
    start=out/'point.sol'
    start_max=sum(len(name.encode())+33 for name in current['col_names'])+65536
    rows_max=sum(len(name.encode())+33 for name in current['row_names'])+65536
    start_output_phase(out,'carry point serialization',[
        budget.WriteBound(start,start_max,'one finite17g line per current column plus fixed headers','source-derived serializer size'),
        budget.WriteBound(out/'current-rows.txt',rows_max,'one finite17g line per current row','source-derived serializer size')])
    g.serialize(start,current['col_names'],x,exact['projected_objective'])
    start_record=read_start(start,current['col_names'],x,exact['projected_objective'])
    with (out/'current-rows.txt').open('x') as stream:
        for name,value in zip(current['row_names'],activities):stream.write(name+' '+format(float(value),'.17g')+'\n')
    require(start.stat().st_size<=start_max and (out/'current-rows.txt').stat().st_size<=rows_max,'Carry serializer bound exceeded')
    return x,activities,mapping,exact,start_record


def prepare(request, out, deadline, *, production=True):
    """The production preparation path also accepts the fixed tiny scope explicitly."""
    run=Path(request['run_directory']).resolve();out=local(out,run)
    require(not run.is_relative_to(ROOT) and run.is_dir(), 'Carry requires this fresh local run outside package')
    require(out.is_dir() and not any(out.iterdir()),'fresh empty preparation output required')
    require(request['schema']==SCHEMA and finite(deadline),'carry request schema/window')
    consumed={}
    def checked(path,digest,*,inside=False):
        p=local(path,run) if inside else Path(path).resolve()
        require(p.is_file() and g.sha(p)==digest,'carry input changed '+str(p));consumed[str(p)]=digest
        return p
    state=g.strict(checked(request['state_path'],request['state_sha256'],inside=True))
    require(state['run_directory']==str(run) and state['source_manifest_sha256']==request['source_manifest_sha256'] and
        state['arm_manifest_sha256']==request['arm_manifest_sha256'],'fresh state/source identity')
    checked(request['source_manifest_path'],request['source_manifest_sha256'])
    arm=g.strict(checked(request['arm_manifest_path'],request['arm_manifest_sha256']))
    solver_random_seed=checked_solver_random_seed(state,arm)
    pending=state['pending_master'];target_call=request['target_call']
    require(pending==request['pending_master'] and pending['call']==target_call,'pending target identity')
    selected=select_point(state,target_call);source_call=selected['call'];ev=selected['evaluation']
    if production:
        rebound=bind_checked_stage(selected['checked_archive'],run,source_call,request['source_manifest_sha256'],expected_row=selected)
        require(rebound==selected.get('checked_stage_binding'),'checked-stage retained metadata changed')
        for path,digest in rebound['metadata_files_sha256'].items():checked(path,digest,inside=True)
    source_dir=local(run/f'mip-{source_call:02d}',run);current_dir=local(run/f'mip-{target_call:02d}',run)
    require(source_dir.is_dir() and current_dir.is_dir(),'missing fresh call directory')
    seed_path=checked(request['seed_result_path'],request['seed_result_sha256'],inside=True)
    require(seed_path==run/'seed/result.json','foreign seed path')
    seed=g.strict(seed_path);require(seed==state['seed'],'seed state binding')
    def bundle(directory,receipt):
        for key in ('document','arrays'):
            if key in receipt:checked(directory/receipt[key]['path'],receipt[key]['sha256'],inside=True)
        return g.bundle(directory,receipt)
    import current_scuc.adaptive as adaptive
    metadata=adaptive.hydrate_metadata(bundle(run/'seed',seed['projection_artifact']))
    base=bundle(run/'seed',seed['base_matrix_artifact'])
    bridge=module('_integer_master',BASE/'master.py');model=bridge.helpers().model
    expected_input=arm['inputs']['expected'];source_input=arm['inputs']['source'];library_input=arm['inputs']['library']
    original=model.load_expected(checked(expected_input['path'],expected_input['sha256']),expected_input['sha256'])
    source=g.strict(checked(source_input['path'],source_input['sha256']))
    checked(library_input['path'],library_input['sha256'])
    require(bridge.source_binary_authority(source,metadata['hours'])==metadata['source_binary_authority'],'source-derived binary authority')
    require(model.model_hashes(original)==seed['original_model_hashes']==metadata['original_hashes'],'original source identity')
    if production:
        from current_scuc.common import helpers
        for role in ('source','expected','library'):
            require(arm['inputs'][role]['sha256']==helpers().INPUT_PINS[role],'unapproved production '+role)
    identity=pending['identity']
    require(selected['master_identity']['integer_target_identity_sha256']==identity['integer_target_identity_sha256']==
        state['integer_target_identity_sha256'],'source/target integer identity')
    require(ev['full_scope_identity_sha256']==metadata['full_scope_identity_sha256'],'source/target full scope identity')
    for prefix in ('model','expected','api_report','row_sidecar'):
        checked(identity[prefix+'_path'],identity[prefix+'_sha256'],inside=True)
    require(Path(identity['model_path']).resolve()==current_dir/'master.mps','wrong destination MPS path')
    meta_path=current_dir/'master.mps.meta.json';consumed[str(meta_path)]=g.sha(meta_path)
    require(g.strict(meta_path)['identity']==identity,'destination persisted identity')
    current=model.load_expected(identity['expected_path'],identity['expected_sha256'])
    require(model.model_hashes(current)==identity['canonical_master_hashes'],'canonical current matrix identity')
    rows=g.strict(Path(identity['row_sidecar_path']))['rows']
    require(len(rows)==current['num_row'] and all(r['index']==i and r['native']==current['row_names'][i] for i,r in enumerate(rows)),'row sidecar mapping')
    # Replay this invocation's complete immutable per-line prefix from the
    # initial empty seed matrix. No oracle, factor, optimizer or point evaluation.
    batches=bundle(run/'seed',seed['batches_artifact']);require(len(batches)==2,'fresh seed support prefix')
    prefix=[dict(source='seed',artifact=seed['batches_artifact'])]
    if 'discovery_proof_transition' in state:
        transition=validate_transition(state,target_call,production=production,checked=checked)
        discovery=bundle(run/'mip-01',transition['evidence']['evaluated_support_artifact'])
        proof=None
        if target_call==2:same_transition_master(transition['evidence']['source_master_identity'],identity)
        else:
            artifact=state['trace'][1]['inserted_batch_artifact']
            proof=bundle(run/'mip-02',artifact)
            prefix.append(dict(source_call=2,artifact=artifact))
            require(identity['master_hashes']!=state['trace'][1]['master_identity']['master_hashes'],
                'unchanged call3 forbidden')
        require(prefix==pending['cut_prefix'] and pending['cut_batches']==target_call,
            'transition current support-prefix identity')
        replayed,metadata=replay_transition_prefix(base,metadata,batches,discovery,proof)
    else:
        for row in state['trace']:
            if row['call']<target_call and 'inserted_batch_artifact' in row:
                batches.append(bundle(run/f"mip-{row['call']:02d}",row['inserted_batch_artifact']))
                prefix.append(dict(source_call=row['call'],artifact=row['inserted_batch_artifact']))
        require(prefix==pending['cut_prefix'] and len(batches)==pending['cut_batches']==target_call+1,'current support-prefix identity')
        replayed,metadata=adaptive.replay(base,metadata,batches)
    lp=dict(current,row_names=[r['original'] for r in rows],integrality=np.zeros(current['num_col'],dtype=np.int32))
    require(model.model_hashes(lp)==model.model_hashes(replayed),'destination differs from complete current support replay')
    restored=bridge.restore_integrality(lp,metadata,original)
    require(restored['identity']['master_hashes']==identity['master_hashes'] and
        restored['identity']['integer_target_identity_sha256']==identity['integer_target_identity_sha256'] and
        restored['source_binary_inventory']==identity['source_binary_inventory'] and
        restored['identity']['adaptive_map_hash']==identity['adaptive_map_hash'] and
        restored['identity']['adaptive_matrix_identity']==identity['adaptive_matrix_identity'] and
        restored['identity']['adaptive_activation']==identity['adaptive_activation'] and
        restored['identity']['adaptive_line_caps']==identity['adaptive_line_caps'] and
        restored['identity']['first_start_family']==identity['first_start_family'],'original/current adaptive mapping')
    g.same(restored['expected']['integrality'],current['integrality'],'current native binary flags')
    lift=bundle(source_dir,ev['stored_lift_artifact'])['values'];oracle=bundle(source_dir,ev['oracle_artifact'])
    require(bundle(source_dir,ev['full_source_quality_artifact'])==ev['full_source_quality'],'stored literal check authority')
    source_quality=bundle(source_dir,ev['source_quality_artifact']);source_quality.pop('activities',None)
    require(source_quality==ev['source_quality'],'stored original matrix check authority')
    x,activities,mapping,exact,start_record=prepare_point(original,current,metadata,oracle,lift,ev,bridge,out,production=production)
    start=Path(start_record['path'])
    native=assess(current,x,activities,identity['model_path'],start,out,library_input['path'],library_input['sha256'],deadline,model)
    require(g.sha(start)==start_record['sha256'],'start changed during assessment')
    require(time.monotonic()<deadline,'carry preparation deadline exceeded')
    for path,digest in consumed.items():require(g.sha(path)==digest,'carry source changed during preparation')
    return dict(schema=SCHEMA,passed=True,result_complete=True,solver_random_seed=solver_random_seed,
        run_directory=str(run),source_call=source_call,
        target_call=target_call,selected_original_provisional_upper=ev['provisional_upper'],
        eligible_calls=[r['call'] for r in state['trace'] if 'evaluation' in r],selection_rule='minimum checked original provisional_upper among target-valid starts; earliest exact tie',
        production_quality_eligible=ev['negligible_slack_quality']['passed'],
        source_manifest_sha256=request['source_manifest_sha256'],arm_manifest_sha256=request['arm_manifest_sha256'],
        source_master_identity=selected['master_identity'],source_lift_artifact=ev['stored_lift_artifact'],source_oracle_artifact=ev['oracle_artifact'],
        target_master_identity=identity,cut_prefix=prefix,mapping=mapping,exact_check=exact,start=start_record,
        consumed_files_sha256=consumed,evidence_files_sha256={str(p):g.sha(p) for p in out.iterdir() if p.is_file()},optimizer_calls=0,topology_factorizations=0,full_network_scans=0,
        nested_helper_charged_once_in_parent_process_wall=True,**native)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('request','request-sha256','out'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--deadline',type=float,required=True)
    args=parser.parse_args(argv)
    require(sys.dont_write_bytecode and __debug__,'require Python -B and assertions')
    out=Path(args.out).resolve();require(not out.exists(),'fresh preparation directory required');out.mkdir()
    record=dict(schema=SCHEMA,passed=False,result_complete=False,request_sha256=args.request_sha256)
    try:
        require(g.sha(args.request)==args.request_sha256,'carry request hash')
        record.update(prepare(g.strict(Path(args.request)),out,min(args.deadline,START+30.)))
    except BaseException as exc:
        record.update(passed=False,error=type(exc).__name__+': '+str(exc),
            error_type=type(exc).__name__,
            storage_admission_failure=getattr(exc,'receipt',{}))
    record.update(result_complete=True,actual_worker_seconds=time.monotonic()-START,
        parent_process_start_through_reap_is_authoritative=True)
    bounded_write(out/'result.json',record,fresh=True)
    bounded_write(out/'completion.json',dict(result_sha256=g.sha(out/'result.json'),passed=record['passed']))
    return 0 if record['passed'] else 2


if __name__=='__main__':
    budget=storage()
    with budget.active_writer_reservations([budget.WriteBound(Path('/proc/self/fd/1').resolve(),512*1024**2,
            'Python carry stdout','prospective512MiB process file limit')]):
        raise SystemExit(main())
