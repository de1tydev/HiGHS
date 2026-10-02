"""Separately charged exact-selector equality on the completed tiny witnesses."""
from pathlib import Path
import sys
import time
from contracts import HERE, SEPARATOR_SHA256, read_json, sha, write_json

def replay(tiny):
    from cold_screen_pair import execute, environment
    started=time.monotonic();tiny=Path(tiny);out=tiny/'replay';out.mkdir(exist_ok=False)
    pair=read_json(tiny/'pair.json')
    if pair.get('tiny_pipeline_verified') is not True: raise ValueError('Tiny gate required')
    checks=[];passed=True
    for original_arm in ('A','B'):
        for index,stage in enumerate(pair['results'][original_arm]['state']['trace'],1):
            rd=Path(stage['stage_directory']);outputs={};receipts={}
            for selected in ('A','B'):
                prefix=out/f'{original_arm}_{index:02d}_{stage["kind"]}_{selected}'
                result=Path(str(prefix)+'.json');receipt=Path(str(prefix)+'.selector.json')
                command=[sys.executable,'-B','-s',str(HERE/'stage_child.py'),'check',
                    '--plan',str(HERE/'CAMPAIGN_PLAN.json'),'--plan-sha256',sha(HERE/'CAMPAIGN_PLAN.json'),
                    '--arm',selected,'--source',str(HERE/'tiny_triangle.json'),'--hours','2',
                    '--kind',stage['kind'],'--pairs',str(rd/'pairs.json'),'--model',str(rd/'master.mps'),
                    '--solution',str(rd/'solution.sol'),'--result',str(result),'--receipt',str(receipt)]
                measured=execute(command,Path(str(prefix)+'.log'),environment(),20.)
                item={'original_arm':original_arm,'stage':index,'selected_arm':selected,'command':command,'process':measured}
                checks.append(item)
                if measured.get('returncode')!=0 or measured.get('hard_watchdog_killed') or measured.get('interrupted'):
                    passed=False;break
                outputs[selected]=read_json(result);receipts[selected]=read_json(receipt)
                selected_receipt=receipts[selected]
                if (selected_receipt.get('passed') is not True or selected_receipt.get('output_sha256')!=sha(result)
                    or selected_receipt.get('loaded_python_modules',{}).get('fractional_separator',{}).get('sha256')!=SEPARATOR_SHA256[selected]):
                    passed=False;break
            if len(outputs)!=2 or outputs.get('A')!=outputs.get('B'):
                passed=False
            if not passed: break
        if not passed: break
    result={'passed':passed,'checks':checks,'witness_count':len(checks)//2,
        'runtime_freeze_sha256':sha(HERE/'REVIEW_MANIFEST.json'),'campaign_plan_sha256':sha(HERE/'CAMPAIGN_PLAN.json'),
        'tiny_pair_sha256':sha(tiny/'pair.json'),'separately_charged_wall_seconds':time.monotonic()-started,
        'scope':'Post-tiny differential replay; excluded from tiny performance endpoints; no solve/generation/readback'}
    write_json(out/'RESULT.json',result,fresh=True)
    return passed
