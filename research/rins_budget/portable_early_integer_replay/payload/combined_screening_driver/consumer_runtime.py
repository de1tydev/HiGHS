"""Local source/seed/output binding; unchanged early-only stage and proof policy."""
import time
from common import *
from pair_codec import PackedPairs
from trial_policy import DISCOVERY,PROOF,options_text,run_pipeline
import early_runtime as bound

class PortableBackend(bound.Backend):
    def __init__(self,out,source,hours,seed,arm,*,tiny):
        plan=read_json(HERE/'CAMPAIGN_PLAN.json');self.record=plan['allowed_sources'].get(str(source))
        if self.record is None or self.record['hours']!=hours:raise ContractError('Unsupported source/hours')
        super().__init__(out,source,hours,tiny=tiny,candidate=arm=='early_candidate')
        self.seed=seed

    def start(self,state):
        self.tracked=dict(runtime_manifest()['artifact_sha256']);health()
        if self.tracked.get(str(self.source))!=sha(self.source):raise ContractError('Local input not pinned')
        scope_record={};checked=self.auxiliary('scope',None,self.out,None,None,None,scope_record)
        if not self.tiny and (checked['scope']!=self.record['scope'] or checked['dimensions']!=self.record['dimensions']):
            raise ContractError('Exact original source scope mismatch')
        self.eligible=checked['scope']
        state.update(arm='early_candidate' if self.candidate else 'A',common_pipeline_arm='A',arm_record=bound.existing.arm_record('A'),
            root_child_credit_enabled=False,lp_discovery_required=False,source_scope=self.eligible,source_sha256=sha(self.source),
            seed=self.seed,hours=self.hours,scope_preparation=scope_record,memory_limit_bytes=MEMORY_BYTES,
            auxiliary_watchdog_seconds=self.aux_watchdog,mip_watchdog_grace_seconds=self.mip_grace,
            runtime_freeze_sha256=sha(HERE/'RUNTIME_MANIFEST.json'),package_sha256=BINDINGS['release_sha256'],
            common_options=bound.existing.options_text('mip',False),
            environment_overrides={k:self.env[k] for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONHASHSEED','LD_LIBRARY_PATH')})
        initial=self.out/'initial_pairs.json';write_json(initial,self.pair_manifest(PackedPairs(self.eligible)),fresh=True)
        self.tracked[str(initial)]=sha(initial);state['initial_pairs_sha256']=sha(initial)
        for kind in ('lp','mip'):
            path=self.out/(kind+'.options');path.write_text(bound.existing.options_text(kind,False));self.tracked[str(path)]=sha(path)
        for role in (PROOF,DISCOVERY):
            path=self.out/(role+'.options');path.write_text(options_text(role));self.tracked[str(path)]=sha(path)
        self.checkpoint(state)

    def auxiliary(self,action,kind,rd,model,pair_path,solution,rec):
        health();result=rd/(action+'.json');log=rd/(action+'.log');receipt=rd/(action+'.selector.json')
        if kind not in (None,'mip'):raise ContractError('Only original integer helpers are enabled')
        command=[PYTHON,'-B','-s',str(HERE/'portable_stage.py'),action,'--source',str(self.source),'--hours',str(self.hours),
                 '--plan-sha256',sha(HERE/'CAMPAIGN_PLAN.json'),'--result',str(result),'--receipt',str(receipt)]
        if action!='scope':command+=['--pairs',str(pair_path),'--model',str(model)]
        if action=='check':command+=['--solution',str(solution)]
        rec[action+'_command']=command;measured=execute(command,log,self.aux_watchdog);rec[action+'_process']=measured
        self.aux.append(dict(kind=kind,action=action,**measured))
        if measured.get('interrupted'):raise KeyboardInterrupt(action+' interrupted')
        if measured.get('returncode')!=0 or measured.get('hard_watchdog_killed'):raise ContractError(action+' helper failed')
        from stage_child import input_identity
        from contracts import SEPARATOR_PATHS
        selected=read_json(receipt);plan=read_json(HERE/'CAMPAIGN_PLAN.json')
        paths={**plan['common_module_paths'],'fractional_separator':str(SEPARATOR_PATHS['A'])}
        expected_loaded={name:{'path':path,'sha256':plan['module_sha256'][path],'loading':'compile exact pinned source bytes'} for name,path in paths.items()}
        expected=dict(passed=True,action=action,source=str(self.source),hours=self.hours,kind=kind,arm='A',
            plan_sha256=sha(HERE/'CAMPAIGN_PLAN.json'),runtime_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'),
            output_sha256=sha(result),input_identity=input_identity(self.source,pair_path,model,solution),
            loaded_python_modules=expected_loaded,python_executable=PYTHON)
        if selected!=expected:raise ContractError('Exact local selector/provenance receipt mismatch')
        rec[action+'_selector']=selected;self.tracked[str(receipt)]=sha(receipt);runtime_manifest()
        return read_json(result)

def run_arm(out,source,hours,seed,arm,*,tiny):
    started=time.monotonic();limit();runtime_manifest();health();out=Path(out);out.mkdir(exist_ok=False)
    backend=PortableBackend(out,source,hours,seed,arm,tiny=tiny)
    state=run_pipeline(backend,arm=='early_candidate',total=10. if tiny else 600.)
    state['auxiliary_processes']=backend.aux
    state['stage_wall_seconds']={label:sum(m['process_wall_seconds'] for m in backend.aux if m['action']==action)
        for label,action in [('scope_preparation','scope'),('generation_readback','generate'),('integer_checks','check')]}
    state['stage_wall_seconds']['integer_solving']=state['budget']['solver_process_wall_seconds']
    measured=[r['solver'] for r in state['trace'] if 'solver' in r]+backend.aux
    state['child_resource_accounting_complete']=all(all(k in m for k in ('user_cpu_seconds','system_cpu_seconds','peak_rss_KiB')) for m in measured)
    state['child_peak_rss_KiB']=max((m.get('peak_rss_KiB',0) for m in measured),default=0)
    state['parent_process_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if not state['child_resource_accounting_complete']:state.update(complete=False,stop_campaign=True,reason='Missing child resource accounting')
    runtime_manifest();verify(backend.tracked);health();backend.checkpoint(state)
    write_json(out/'completion_receipt.json',dict(complete=state['complete'],summary_sha256=sha(out/'summary.json'),
        solver_process_wall_seconds=state['budget']['solver_process_wall_seconds'],arm_body_seconds=time.monotonic()-started,
        timing='Diagnostic body endpoint; primary arm E2E is containing-process launch through exact reap'),fresh=True)
    return state
