#!/usr/bin/env python3
"""Watchdog child: fresh source construction, canonical v2/API gate, or primal checks.

There is no optimizer entry point. Construction/readback/checking requires an
explicit invocation; importing this module performs no numerical work.
"""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import argparse
import gzip
import math
import numbers
from pathlib import Path
from current_scuc.contracts import *
from current_scuc.core.driver.pair_codec import PackedPairs
from current_scuc.core.driver.resource_guard import projected_master, actual_master, guard_storage
from current_scuc.core.driver.primal_and_bound import matrix_check, objective_consistent, read_primal, unpack_expected

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







