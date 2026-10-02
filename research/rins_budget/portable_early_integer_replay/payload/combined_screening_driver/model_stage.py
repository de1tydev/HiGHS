#!/usr/bin/env python3
"""Watchdog child: fresh source construction, canonical v2/API gate, or primal checks.

There is no optimizer entry point. Construction/readback/checking requires an
explicit invocation; importing this module performs no numerical work.
"""
import argparse
import gzip
import math
import numbers
from pathlib import Path
from contracts import *
from pair_codec import PackedPairs
from resource_guard import projected_master, actual_master, guard_storage
from primal_and_bound import matrix_check, objective_consistent, read_primal, unpack_expected

def normalize_source_measurements(raw):
    """Normalize only real-valued measurements returned by the trusted checker.

    The frozen checker can retain NumPy real scalars after direct-flow maxima.
    Counts, booleans, identifiers and external input contracts stay unchanged.
    There is no tolerance adjustment or arbitrary float-coercion acceptance.
    """
    result=dict(raw)
    result['security']=dict(raw['security'])
    result['max_violation_by_category']=dict(raw['max_violation_by_category'])
    converted=[]
    def measurement(value,path):
        if isinstance(value,bool) or not isinstance(value,numbers.Real):
            raise ContractError('Non-real trusted source measurement: '+path+' ('+type(value).__name__+')')
        normalized=float(value)
        if not math.isfinite(normalized): raise ContractError('Nonfinite trusted source measurement: '+path)
        if type(value) not in (int,float):
            converted.append({'field':path,'original_type':type(value).__module__+'.'+type(value).__name__,
                              'normalized_type':'builtins.float','value':normalized})
        return normalized
    for key in ('linear_model_cost','true_source_cost','objective_overpayment','total_shed_MWh',
                'max_overflow_MW','base_unrelaxed_overload_MW'):
        result[key]=measurement(raw[key],key)
    for key,value in raw['max_violation_by_category'].items():
        result['max_violation_by_category'][key]=measurement(value,'max_violation_by_category.'+key)
    for key in ('max_violation_after_shared_slack_MW','max_unrelaxed_overload_MW'):
        result['security'][key]=measurement(raw['security'][key],'security.'+key)
    return result,converted

def source_data(path):
    # Source permits +Infinity only in ratings. Separator performs full schema validation.
    def unique(items):
        result = {}
        for key,value in items:
            if key in result: raise ContractError('Duplicate source key: '+key)
            result[key]=value
        return result
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as stream:
        return json.load(stream, object_pairs_hook=unique)

def api_modules():
    return module(EXPORTER/'export_v2.py','export_v2'), module(EXPORTER/'readback.py','readback')

def pack_expected(expected):
    result={}
    for field,value in expected.items():
        if hasattr(value,'tolist'): value=value.tolist()
        if isinstance(value,list): value=['+inf' if v==math.inf else '-inf' if v==-math.inf else v for v in value]
        result[field]=value
    return result

def accept_api(report, model, expected_path, source, pair_path, hours, kind):
    identity={'source_sha256':sha(source),'mps_sha256':sha(model),'expected_sha256':sha(expected_path),
              'pair_manifest_sha256':sha(pair_path),'hours':hours,'kind':kind,
              'library_path':str(LIBRARY.resolve()),'library_sha256':sha(LIBRARY),
              'checker_sha256':sha(EXPORTER/'readback.py')}
    if any(report.get(k)!=v for k,v in identity.items()): raise ContractError('API identity mismatch')
    if (report.get('passed') is not True or report.get('read_status') != 0 or report.get('failures') != []
        or report.get('diagnostics') != [] or report.get('hessian_num_nz')!=0
        or report.get('optimization_or_presolve_called') is not False or report.get('highs_int_bytes')!=4):
        raise ContractError('Actual loaded model is not exactly original')
    fields=report.get('fields',{})
    if set(fields)!=FIDELITY_FIELDS or any(v.get('passed') is not True for v in fields.values()):
        raise ContractError('Missing/failed actual API field equality')
    symbols=report.get('loaded_symbol_provenance',{})
    if set(symbols)!={'Highs_create','Highs_readModel','Highs_getLp','Highs_getColName','Highs_getRowName'} or any(
        v.get('path')!=identity['library_path'] or v.get('sha256')!=identity['library_sha256'] for v in symbols.values()):
        raise ContractError('Actual loaded DSO differs from solver library')
    log=Path(str(model)+'.readback.log')
    if report.get('log_path')!=str(log.resolve()) or report.get('log_sha256')!=sha(log) or not report.get('bound_record_audit'):
        raise ContractError('Missing/changed API diagnostic or bound audit')
    return identity

def generate(source,hours,pair_path,kind,out):
    runtime_manifest()
    if sha(source)==TARGET_SHA256:
        from release_gate import require_target_release
        require_target_release(HERE)
    if not __debug__: raise ContractError('Frozen source assertions must remain enabled')
    from fractional_separator import source_scope, source_data_sha256
    data=source_data(source); scope=source_scope(data,hours,source_sha256=sha(source))
    active=pairs(read_json(pair_path),scope)
    exporter,reader=api_modules()
    generator,lineage=exporter.load_generator(GENERATOR)
    # Explicit empty/list input: None would accidentally construct static N-1.
    allocation = projected_master(data,hours,scope,active)
    allocation['storage']=guard_storage(Path(out).parent.parent,3*allocation['estimated_model_file_bytes']+5*1024**3)
    model,network=generator.build(data,hours,'n1',active)
    allocation['actual']=actual_master(model,allocation)
    expected=exporter.intended_model(model)
    if kind=='lp':
        # All immutable numerical arrays are reused; only integrality is copied.
        integer_expected=dict(expected)
        expected=dict(expected,integrality=expected['integrality'].copy())
        expected['integrality'][:]=0
        check_lp_integer_difference(integer_expected,expected)
        model.binary=[False]*len(model.binary)
        del integer_expected
    elif kind!='mip': raise ContractError('Unknown generation scope')
    out=Path(out); expected_path=Path(str(out)+'.expected.json')
    write_json(expected_path,pack_expected(expected),fresh=True)
    meta=exporter.write_model(model,out,{'input_sha256':sha(source),'source_data_sha256':source_data_sha256(data),
        'generator_sha256':sha(GENERATOR),'hours':hours,'mode':'n1','kind':kind,'network':network,
        'pair_manifest_sha256':sha(pair_path),'active_pairs':read_json(pair_path),'allocation':allocation,
        'integrality_scope':'continuous' if kind=='lp' else 'original_integer',
        'lp_only_integrality_changed':kind=='lp','integer_source_restored':kind=='mip',
        'expected_sha256':sha(expected_path),'objective_scope':'unchanged_original_source'}, expected=expected)
    report=reader.verify_expected(expected,out,LIBRARY,str(out)+'.readback.log')
    report.update(source_sha256=sha(source),expected_sha256=sha(expected_path),pair_manifest_sha256=sha(pair_path),hours=hours,kind=kind)
    write_json(str(out)+'.readback.json',report,fresh=True)
    accept_api(report,out,expected_path,source,pair_path,hours,kind)
    meta.update(api_fidelity_verified=True,readback_sha256=sha(str(out)+'.readback.json'),
                checked_outage_ids=scope['checked_outage_ids'],eligible_pair_count=scope['eligible_pair_count'])
    write_json(str(out)+'.meta.json',meta,fresh=True)
    runtime_manifest()
    return meta

def check(source,hours,pair_path,kind,model,solution):
    runtime_manifest()
    if sha(source)==TARGET_SHA256:
        from release_gate import require_target_release
        require_target_release(HERE)
    from fractional_separator import source_scope, source_data_sha256, separate, separate_integer_network
    meta=read_json(str(model)+'.meta.json'); expected_path=Path(str(model)+'.expected.json')
    report_path=Path(str(model)+'.readback.json'); report=read_json(report_path)
    accept_api(report,model,expected_path,source,pair_path,hours,kind)
    required={'input_sha256':sha(source),'mps_sha256':sha(model),'expected_sha256':sha(expected_path),
              'pair_manifest_sha256':sha(pair_path),'readback_sha256':sha(report_path),'hours':hours,'kind':kind,
              'api_fidelity_verified':True,'objective_scope':'unchanged_original_source'}
    if any(meta.get(k)!=v for k,v in required.items()): raise ContractError('Metadata identity mismatch')
    expected=unpack_expected(read_json(expected_path))
    primal=read_primal(solution,expected['col_names'])
    if primal is None: return {'primal_present':False,'kind':kind,'solution_sha256':sha(solution),
                               'upper_bound_eligible':False,'certificate_bound_eligible':False}
    values=primal['values']; data=source_data(source); scope=source_scope(data,hours,source_sha256=sha(source))
    active=pairs(read_json(pair_path),scope)
    identity=dict(source_sha256=sha(source),source_data_sha256=source_data_sha256(data),model_sha256=sha(model),
                  expected_sha256=sha(expected_path),solution_sha256=sha(solution),pair_manifest_sha256=sha(pair_path),
                  hours=hours,active_pairs_sha256=active.content_sha256())
    matrix=matrix_check(expected,values,kind,identity)
    if matrix['passed'] is not True: raise ContractError('Current source matrix/bound/integrality check failed: '+str(matrix))
    if not objective_consistent(matrix['linear_objective'],primal['printed_objective']): raise ContractError('Printed objective inconsistent with original linear cost')
    identity['matrix_check']=matrix
    separation=(separate if kind=='lp' else separate_integer_network)(data,values,hours,active,identity=identity,witness_directory=Path(str(solution)+'.witnesses'))
    violated=pairs(separation['violated_pairs'],scope)
    if separation['checked_outage_ids']!=scope['checked_outage_ids'] or separation['checked_pair_hours']!=scope['eligible_pair_hours'] or violated.intersects(active):
        raise ContractError('Outage coverage mismatch or active-pair violation')
    result=dict(primal_present=True,kind=kind,matrix_check=matrix,separation=separation,identity=identity,
                solution_sha256=sha(solution),status=primal['status'],new_pairs=separation['violated_pairs'],
                upper_bound_eligible=False,certificate_bound_eligible=False,full_source_primal_pass=False)
    if kind=='mip':
        # Only the original-integer audit above permits calling this unaltered checker.
        source=module(CHECKER,'frozen_cold_scuc_checker').check(source,solution,'n1',hours,TOLERANCE,True)
        source,scalar_normalizations=normalize_source_measurements(source)
        categories=source['violations_by_category']
        # The frozen Python checker returns sorted tuples before JSON serialization.
        # Normalize only this trusted in-memory return, never external pair input.
        source_pairs=PackedPairs(scope,source['security']['violated_pairs'])
        source['security']['violated_pairs']=separation['violated_pairs']
        if source_pairs!=violated or source['security']['outages_checked']!=len(scope['checked_outage_ids']):
            raise ContractError('Frozen source checker disagrees with independent direct separator')
        if (source['source_sha256']!=identity['source_sha256'] or source['solution_sha256']!=identity['solution_sha256'] or
            source['hours']!=hours or source['mode']!='n1' or source['tolerance']!=TOLERANCE or
            source['pass_primal'] is not (not bool(categories))): raise ContractError('Source checker identity/status mismatch')
        if not all(finite(source[k]) for k in ('linear_model_cost','true_source_cost','total_shed_MWh','max_overflow_MW','base_unrelaxed_overload_MW')) or not all(finite(v) for v in source['max_violation_by_category'].values()):
            raise ContractError('Nonfinite source residual or objective')
        if set(categories)-{'emergency_line_limit'} or (bool(categories)!=bool(violated)):
            raise ContractError('Nonsecurity source failure is fatal')
        if not objective_consistent(source['linear_model_cost'],matrix['linear_objective']): raise ContractError('Source/matrix objective mismatch')
        full=source['pass_primal'] is True and not violated
        result.update(source_check=source,source_scalar_normalizations=scalar_normalizations,
                      full_source_primal_pass=full,upper_bound_eligible=full,
                      checked_upper=max(source['linear_model_cost'],matrix['linear_objective']) if full else None)
    runtime_manifest()
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['generate','check']);p.add_argument('--source',required=True)
    p.add_argument('--hours',type=int,required=True);p.add_argument('--pairs',required=True)
    p.add_argument('--kind',choices=['lp','mip'],required=True);p.add_argument('--model',required=True)
    p.add_argument('--solution');p.add_argument('--result',required=True);a=p.parse_args()
    try:
        result=generate(a.source,a.hours,a.pairs,a.kind,a.model) if a.action=='generate' else check(a.source,a.hours,a.pairs,a.kind,a.model,a.solution)
        write_json(a.result,result,fresh=True)
        return 0
    except Exception as exc:
        write_json(a.result,{'error':f'{type(exc).__name__}: {exc}'},fresh=True)
        return 2

if __name__=='__main__': raise SystemExit(main())
