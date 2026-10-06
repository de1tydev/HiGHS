"""Pinned public C API only: one persistent LP object, supported row additions.

No setBasis, private/internal API, manual basis mapping, or clock reset exists.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import ctypes as C
import importlib.util
import math
from pathlib import Path
import re
import sys
import time
import numpy as np
from current_scuc.science.model import require, sha256, validate_model, compare_models, append_rows

ROOT = PACKAGE_ROOT
HEADER_SHA='b1ca641440b94750d2a867f1ebc2d1e760ab392da2731072cbd0e297eced814a'
READBACK_SHA=source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/readback.py')
EXPORT_SHA=source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py')
ADVISORY_SOURCE_SHA='62aeb110a4dcbb26f6e73932fba3b924c546ee5902520f0e1fa3cb42decca0d1'
OPTIONS={'solver':'simplex','simplex_strategy':1,'presolve':'on','parallel':'off','threads':2,'random_seed':0,'use_warm_start':True,
         'primal_feasibility_tolerance':1e-7,'dual_feasibility_tolerance':1e-7,'optimality_tolerance':1e-7}
INT_INFO=('primal_solution_status','dual_solution_status','basis_validity','num_primal_infeasibilities','num_dual_infeasibilities',
          'simplex_iteration_count','ipm_iteration_count','pdlp_iteration_count','num_primal_residual_errors','num_dual_residual_errors')
DOUBLE_INFO=('objective_function_value','max_primal_infeasibility','max_dual_infeasibility','primal_dual_objective_error',
             'max_primal_residual_error','max_dual_residual_error')


class NativeError(RuntimeError):pass


def checked(status, action):
    if status!=0:raise NativeError(f'{action}: non-OK C API status {status}')


def _helper():
    directory = ROOT/'core/canonical_mps_export'
    require(sha256(directory/'readback.py') == READBACK_SHA and sha256(directory/'export_v2.py') == EXPORT_SHA,
        'Provenance helper/dependency identity changed')
    return load_module('readback', directory/'readback.py')


def classify_diagnostics(text, *, source_guard, model_path=None):
    """Only exact source-guarded scale advice is advisory; diagnostics stay fatal."""
    known=[];fatal=[]
    patterns=(
      r'WARNING: Problem has some excessively (?:small|large) (?:costs|bounds on variables|bounds on constraints)',
      r'WARNING:    Consider scaling the (?:objective|   bounds) by 1e[+-][0-9]+, or setting the user_(?:objective|bound)_scale option to -?[0-9]+',
      r'WARNING:    Consider setting the user_(?:objective|bound)_scale option to -?[0-9]+',
      r'WARNING: Problem is badly scaled, which may compromise the speed, accuracy and reliability of solvers in HiGHS')
    for line in text.splitlines():
        if model_path and line=='readMPS: Trying to open file '+str(model_path):continue
        if re.search(r'warning|error|ignored|dropped',line,re.I):
            # Normal summary field is a metric, not a numerical/model diagnostic.
            if re.fullmatch(r'\s*(?:Primal-dual|P-D) objective error\s*:\s*[0-9.eE+\-]+\s*',line):continue
            if source_guard and any(re.fullmatch(p,line) for p in patterns):known.append(line)
            else:fatal.append(line)
    return {'fatal':fatal,'scaling_advisories':known,'source_guard_verified':source_guard,
            'scaling_advisory_source':'pristine-source/highs/lp_data/HighsSolve.cpp:538-716',
            'qualification':'Advice classification does not waive any API status or numerical QA requirement'}


class PersistentLP:
    def __init__(self, library_path, log_path):
        self.handle=None;self.expected=None;self.model_path=None;self.last_run=None;self.version=0;self.events=[];self.run_records=[]
        self.library_path=Path(library_path).resolve();self.log_path=Path(log_path).resolve()
        require(not self.log_path.exists(),'Native log must be a fresh output path')
        require(sha256(self.library_path)==runtime_sha('library'),'Actual library hash not the pinned pristine DSO')
        require(sha256(runtime_path('pristine-source/highs/interfaces/highs_c_api.h'))==HEADER_SHA,'Pinned C API source changed')
        self.source_guard=sha256(runtime_path('pristine-source/highs/lp_data/HighsSolve.cpp'))==ADVISORY_SOURCE_SHA
        require(self.source_guard,'Scaling advisory source guard changed')
        I,D,P=C.c_int32,C.c_double,C.c_void_p;IP,DP=C.POINTER(I),C.POINTER(D)
        self.I,self.D,self.IP,self.DP=I,D,IP,DP
        self.lib=C.CDLL(str(self.library_path))
        sig={
          'Highs_create':(P,[]),'Highs_destroy':(None,[P]),'Highs_getSizeofHighsInt':(I,[P]),'Highs_version':(C.c_char_p,[]),
          'Highs_readModel':(I,[P,C.c_char_p]),'Highs_clearIntegrality':(I,[P]),'Highs_run':(I,[P]),'Highs_getRunTime':(D,[P]),
          'Highs_getModelStatus':(I,[P]),'Highs_getNumCol':(I,[P]),'Highs_getNumRow':(I,[P]),'Highs_getNumNz':(I,[P]),
          'Highs_getPresolvedNumCol':(I,[P]),'Highs_getPresolvedNumRow':(I,[P]),'Highs_getPresolvedNumNz':(I,[P]),
          'Highs_getHessianNumNz':(I,[P]),'Highs_getInfinity':(D,[P]),
          'Highs_passLp':(I,[P,I,I,I,I,I,D,DP,DP,DP,DP,DP,IP,IP,DP]),
          'Highs_passMip':(I,[P,I,I,I,I,I,D,DP,DP,DP,DP,DP,IP,IP,DP,IP]),
          'Highs_getLp':(I,[P,I,IP,IP,IP,IP,DP,DP,DP,DP,DP,DP,IP,IP,DP,IP]),
          'Highs_getColName':(I,[P,I,C.c_char_p]),'Highs_getRowName':(I,[P,I,C.c_char_p]),
          'Highs_passColName':(I,[P,I,C.c_char_p]),'Highs_passRowName':(I,[P,I,C.c_char_p]),
          'Highs_getSolution':(I,[P,DP,DP,DP,DP]),'Highs_getBasis':(I,[P,IP,IP]),
          'Highs_getIntInfoValue':(I,[P,C.c_char_p,IP]),'Highs_getDoubleInfoValue':(I,[P,C.c_char_p,DP]),
          'Highs_addRows':(I,[P,I,DP,DP,I,IP,IP,DP])}
        for kind,typ in [('Bool',I),('Int',I),('Double',D),('String',C.c_char_p)]:
            sig['Highs_set'+kind+'OptionValue']=(I,[P,C.c_char_p,typ])
            sig['Highs_get'+kind+'OptionValue']=(I,[P,C.c_char_p,C.c_char_p if kind=='String' else C.POINTER(typ)])
        for name,(result,args) in sig.items():
            fun=getattr(self.lib,name);fun.restype=result;fun.argtypes=args
        provenance=_helper().symbol_provenance(self.lib,tuple(sig))
        require(all(v['path']==str(self.library_path) and v['sha256']==runtime_sha('library') for v in provenance.values()),'C API symbol DSO mismatch')
        self.identity={'library_path':str(self.library_path),'library_sha256':runtime_sha('library'),'loaded_symbol_provenance':provenance,
                       'header_sha256':HEADER_SHA,'provenance_helper_sha256':READBACK_SHA,'provenance_dependency_sha256':EXPORT_SHA,'scaling_advisory_source_sha256':ADVISORY_SOURCE_SHA,'version':self.lib.Highs_version().decode()}
        self.handle=self.lib.Highs_create()
        require(bool(self.handle),'Highs_create failed')
        try:
            width=self.lib.Highs_getSizeofHighsInt(self.handle);require(width==4,'HighsInt32 ABI mismatch')
            self.identity['highs_int_bytes']=width
            self.set_option('log_to_console',False);self.set_option('output_flag',True);self.set_option('log_file',str(self.log_path))
            # Confirm defaults first: assigning them cannot conceal a mismatching native default.
            self.defaults={k:self.get_option(k,type(v)) for k,v in OPTIONS.items() if k.endswith('_tolerance')}
            require(all(v==1e-7 for v in self.defaults.values()),'Pinned default tolerance changed')
            for name,value in OPTIONS.items():self.set_option(name,value)
            self.options={name:self.get_option(name,type(value)) for name,value in OPTIONS.items()}
            require(self.options==OPTIONS,'Fixed option readback mismatch')
        except BaseException:
            self.destroy();raise

    def __enter__(self):return self
    def __exit__(self,*_):self.destroy()
    def _ptr(self,a):return a.ctypes.data_as(self.IP if a.dtype==np.int32 else self.DP)
    def _call(self,name,*args):
        result=getattr(self.lib,name)(self.handle,*args);self.events.append({'action':name,'status':int(result)})
        checked(result,name);return result
    def _alive(self):require(bool(self.handle),'Object destroyed')

    def set_option(self,name,value):
        self._alive();kind='Bool' if type(value) is bool else 'Int' if type(value) is int else 'Double' if type(value) is float else 'String' if type(value) is str else None
        require(kind is not None,'Unsupported option type')
        if self.run_records and name in OPTIONS:require(value==OPTIONS[name],'Cannot change frozen options after solving')
        self._call('Highs_set'+kind+'OptionValue',name.encode(),value.encode() if kind=='String' else value)
        require(self.get_option(name,type(value))==value,'Option readback mismatch '+name)

    def get_option(self,name,kind):
        self._alive();label={bool:'Bool',int:'Int',float:'Double',str:'String'}[kind]
        if kind is str:
            val=C.create_string_buffer(512);self._call('Highs_getStringOptionValue',name.encode(),val);return val.value.decode()
        val=(self.D if kind is float else self.I)();self._call('Highs_get'+label+'OptionValue',name.encode(),C.byref(val));return kind(val.value)

    def diagnostics(self):
        text=self.log_path.read_text() if self.log_path.exists() else ''
        return classify_diagnostics(text,source_guard=self.source_guard,model_path=self.model_path)

    def _check_diagnostics(self):
        d=self.diagnostics()
        if d['fatal']:raise NativeError('Native diagnostic: '+' | '.join(d['fatal']))
        return d

    def readback(self):
        self._alive();n,m,nz=(int(getattr(self.lib,'Highs_getNum'+k)(self.handle)) for k in ('Col','Row','Nz'))
        require(min(n,m,nz)>=0 and self.lib.Highs_getHessianNumNz(self.handle)==0,'Invalid dimensions or non-LP')
        arrays={k:np.zeros(size,dtype=np.int32 if k in ('integrality','a_start','a_index') else np.float64) for k,size in
                (('col_cost',n),('col_lower',n),('col_upper',n),('row_lower',m),('row_upper',m),('integrality',n),('a_start',n+1),('a_index',nz),('a_value',nz))}
        ni,mi,nzi,sense,offset=self.I(),self.I(),self.I(),self.I(),self.D()
        self._call('Highs_getLp',1,C.byref(ni),C.byref(mi),C.byref(nzi),C.byref(sense),C.byref(offset),*(self._ptr(arrays[k]) for k in ('col_cost','col_lower','col_upper','row_lower','row_upper','a_start','a_index','a_value','integrality')))
        require((ni.value,mi.value,nzi.value)==(n,m,nz),'Readback dimensions drifted');arrays['a_start'][n]=nz
        out={'num_col':n,'num_row':m,'num_nz':nz,'sense':sense.value,'offset':offset.value,**arrays}
        for field,count,api in (('col_names',n,'Highs_getColName'),('row_names',m,'Highs_getRowName')):
            names=[];fun=getattr(self.lib,api)
            # Every getter status is checked, but avoid hundreds of thousands of redundant event records.
            for j in range(count):
                buf=C.create_string_buffer(4096);checked(fun(self.handle,j,buf),api);names.append(buf.value.decode())
            out[field]=names
            self.events.append({'action':api,'status':0,'checked_calls':count})
        return out

    def _verify(self,intended):
        got=self.readback();result=compare_models(intended,got,self.lib.Highs_getInfinity(self.handle))
        require(result['passed'],'Exact native input readback mismatch: '+','.join(result['failures']))
        self._check_diagnostics();return result

    def _clear_and_verify(self,e):
        self._call('Highs_clearIntegrality');continuous=dict(e);continuous['integrality']=np.zeros(e['num_col'],dtype=np.int32)
        result=self._verify(continuous);self.expected=continuous;self.version+=1;self.last_run=None
        return result

    def pass_model(self,intended):
        self._alive();require(self.expected is None,'One model load per fresh object')
        e=validate_model(intended)
        args=(e['num_col'],e['num_row'],e['num_nz'],1,e['sense'],e['offset'],*(self._ptr(e[k]) for k in ('col_cost','col_lower','col_upper','row_lower','row_upper','a_start','a_index','a_value')))
        if np.any(e['integrality']):self._call('Highs_passMip',*args,self._ptr(e['integrality']))
        else:self._call('Highs_passLp',*args)
        for field,api in (('col_names','Highs_passColName'),('row_names','Highs_passRowName')):
            fun=getattr(self.lib,api)
            for j,name in enumerate(e[field]):checked(fun(self.handle,j,name.encode()),api)
            self.events.append({'action':api,'status':0,'checked_calls':len(e[field])})
        before=self._verify(e);after=self._clear_and_verify(e)
        return {'before_clear':before,'after_clear':after,'integer_columns_cleared':int(np.count_nonzero(e['integrality']))}

    def load_mps(self,path,intended):
        self._alive();require(self.expected is None,'One model load per fresh object')
        e=validate_model(intended);self.model_path=Path(path).resolve()
        with self.model_path.open('rb') as f:
            for line in f:require(all(len(t)<4096 for t in line.split()),'Unsafe MPS name token')
        self._call('Highs_readModel',str(self.model_path).encode())
        before=self._verify(e);after=self._clear_and_verify(e)
        return {'before_clear':before,'after_clear':after,'mps_sha256':sha256(path),'integer_columns_cleared':int(np.count_nonzero(e['integrality']))}

    def get_runtime(self):
        self._alive();v=float(self.lib.Highs_getRunTime(self.handle));require(math.isfinite(v) and v>=0,'Invalid cumulative runtime');return v

    def run_with_cumulative_limit(self,deadline,*,native_total_cap=240.,reserve_seconds=5.):
        """deadline is absolute monotonic wall; hard kill remains the parent's duty."""
        self._alive();require(self.expected is not None,'No loaded continuous model')
        require(math.isfinite(deadline) and math.isfinite(native_total_cap) and 0<native_total_cap<=240 and math.isfinite(reserve_seconds) and reserve_seconds>=0,'Invalid cumulative budget')
        require(all(self.get_option(k,type(v))==v for k,v in OPTIONS.items()),'Frozen option drift')
        require(np.count_nonzero(self.expected['integrality'])==0,'Integrality not cleared')
        before=self.get_runtime();remaining=deadline-time.monotonic()-reserve_seconds
        limit=min(native_total_cap,before+remaining)
        if remaining<=0 or limit<=before:raise NativeError('Cumulative native/wall budget exhausted before run')
        self.set_option('time_limit',float(limit));start=time.monotonic()
        status=int(self.lib.Highs_run(self.handle));end=time.monotonic();after=self.get_runtime()
        require(after>=before,'Cumulative runtime decreased')
        result={'run_status':status,'model_status':int(self.lib.Highs_getModelStatus(self.handle)),'version':self.version,
                'monotonic_start':start,'monotonic_end':end,'actual_call_wall_seconds':end-start,'cumulative_before':before,'cumulative_after':after,
                'native_increment':after-before,'requested_cumulative_limit':limit,'native_total_cap':native_total_cap,
                'declared_final_reserve_seconds':reserve_seconds,'remaining_wall_before_reserve':remaining+reserve_seconds,
                'native_limit_overshoot_seconds':max(0.,after-limit),'process_deadline_overshoot_seconds':max(0.,end-deadline),
                'presolved_dimensions':{k:int(getattr(self.lib,'Highs_getPresolvedNum'+api)(self.handle)) for k,api in [('columns','Col'),('rows','Row'),('nonzeros','Nz')]},
                'diagnostics':self.diagnostics()}
        self.last_run=result;self.run_records.append(result);self.events.append({'action':'Highs_run','status':status})
        return result

    def get_solution(self):
        """Return copied point/status arrays even on failure; QA decides admission."""
        self._alive();require(self.expected is not None,'No model')
        n,m=self.expected['num_col'],self.expected['num_row']
        out={k:np.full(size,np.nan) for k,size in [('col_value',n),('col_dual',n),('row_value',m),('row_dual',m)]}
        out['solution_status']=int(self.lib.Highs_getSolution(self.handle,*(self._ptr(out[k]) for k in ('col_value','col_dual','row_value','row_dual'))))
        out['col_basis']=np.full(n,-1,dtype=np.int32);out['row_basis']=np.full(m,-1,dtype=np.int32)
        out['basis_status']=int(self.lib.Highs_getBasis(self.handle,self._ptr(out['col_basis']),self._ptr(out['row_basis'])))
        info={};returns={};nonfinite={}
        for name in INT_INFO+DOUBLE_INFO:
            value=self.I(-1) if name in INT_INFO else self.D(math.nan)
            api='Highs_getIntInfoValue' if name in INT_INFO else 'Highs_getDoubleInfoValue'
            status=int(getattr(self.lib,api)(self.handle,name.encode(),C.byref(value)));returns[name]=status;v=value.value if status==0 else None
            if isinstance(v,float) and not math.isfinite(v):nonfinite[name]=repr(v);v=None
            info[name]=v
        out.update(info=info,info_returns=returns,info_nonfinite=nonfinite,model_status=int(self.lib.Highs_getModelStatus(self.handle)),
                   run_status=self.last_run['run_status'] if self.last_run and self.last_run['version']==self.version else None,
                   diagnostics=self.diagnostics(),version=self.version,cumulative_runtime=self.get_runtime())
        return out

    def add_rows(self,lower,upper,starts,index,value,names=None):
        self._alive();require(self.expected is not None and self.last_run is not None,'Rows require an existing solved model')
        intended=append_rows(self.expected,lower,upper,starts,index,value,names)
        lo=np.ascontiguousarray(lower,dtype=np.float64);up=np.ascontiguousarray(upper,dtype=np.float64)
        ss=np.ascontiguousarray(starts,dtype=np.int32);ii=np.ascontiguousarray(index,dtype=np.int32);vv=np.ascontiguousarray(value,dtype=np.float64)
        previous_rows=self.expected['num_row'];old_version=self.version;start=time.monotonic()
        self._call('Highs_addRows',len(lo),self._ptr(lo),self._ptr(up),len(vv),self._ptr(ss),self._ptr(ii),self._ptr(vv))
        for j,name in enumerate(intended['row_names'][previous_rows:]):self._call('Highs_passRowName',previous_rows+j,name.encode())
        status=int(self.lib.Highs_getModelStatus(self.handle));require(status==0,'Row addition failed to invalidate old model status')
        readback=self._verify(intended);self.expected=intended;self.version+=1;self.last_run=None
        return {'previous_version':old_version,'version':self.version,'same_handle':True,'model_status_after_add':status,
                'old_solution_invalidated':True,'readback':readback,'row_addition_and_full_readback_seconds':time.monotonic()-start,
                'basis_reuse':'supported automatic basis extension; no preserved factorization claim'}

    def destroy(self):
        if self.handle:
            self.lib.Highs_destroy(self.handle);self.handle=None
            require(sha256(self.library_path)==runtime_sha('library'),'Pinned DSO changed during use')
