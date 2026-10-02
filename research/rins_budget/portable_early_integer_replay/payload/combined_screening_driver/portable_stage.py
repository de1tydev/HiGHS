"""Fresh original A helpers under the prepared fixed-source local allowlist."""
import argparse
import importlib.util
from pathlib import Path
import resource
import sys
import traceback

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('local_exact_selector',HERE/'stage_child.py')
selector=importlib.util.module_from_spec(spec);spec.loader.exec_module(selector)
sha,read_json=selector.sha,selector.read_json

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['scope','generate','check'])
    p.add_argument('--plan-sha256',required=True);p.add_argument('--source',required=True);p.add_argument('--hours',type=int,required=True)
    p.add_argument('--pairs');p.add_argument('--model');p.add_argument('--solution');p.add_argument('--result',required=True);p.add_argument('--receipt',required=True);a=p.parse_args()
    receipt=dict(passed=False,action=a.action,source=a.source,hours=a.hours,kind=None if a.action=='scope' else 'mip',arm='A',plan_sha256=a.plan_sha256)
    try:
        resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**3,4*1024**3))
        if sha(HERE/'CAMPAIGN_PLAN.json')!=a.plan_sha256:raise ValueError('Local source-plan identity mismatch')
        plan=read_json(HERE/'CAMPAIGN_PLAN.json');entry=plan['allowed_sources'].get(a.source)
        if entry is None or entry['hours']!=a.hours or sha(a.source)!=entry['sha256']:raise ValueError('Unsupported or changed source/hours')
        stage,loaded=selector.load_selected(plan,'A');stage.runtime_manifest()
        receipt.update(loaded_python_modules=loaded,runtime_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'))
        if a.action=='scope':
            data=stage.source_data(a.source);scope=sys.modules['fractional_separator'].source_scope(data,a.hours,source_sha256=sha(a.source))
            result=dict(scope=scope,dimensions={k:len(data[k]) for k in ('Buses','Generators','Transmission lines')})
            if entry['kind']!='synthetic' and (scope!=entry['scope'] or result['dimensions']!=entry['dimensions']):raise ValueError('Declared original source scope changed')
        elif a.action=='generate':result=stage.generate(a.source,a.hours,a.pairs,'mip',a.model)
        else:result=stage.check(a.source,a.hours,a.pairs,'mip',a.model,a.solution)
        stage.write_json(a.result,result,fresh=True);stage.runtime_manifest()
        receipt.update(passed=True,input_identity=selector.input_identity(a.source,a.pairs,a.model,a.solution),output_sha256=sha(a.result),python_executable=sys.executable)
        stage.write_json(a.receipt,receipt,fresh=True);return 0
    except BaseException as exc:
        receipt['error']=type(exc).__name__+': '+str(exc);traceback.print_exc()
        import json,os
        for name,value in [(a.result,{'error':receipt['error']}),(a.receipt,receipt)]:
            if not Path(name).exists():
                with open(name,'x') as stream:json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        return 2

if __name__=='__main__':raise SystemExit(main())
