"""Separately charged direct historical-core equality for all completed tiny witnesses."""
from pathlib import Path
import sys
import time
from contracts import HERE, read_json, sha, write_json

def replay(tiny):
    from cold_screen_pair import execute, environment
    start = time.monotonic(); tiny = Path(tiny); out = tiny/'frozen_core_replay'; out.mkdir(exist_ok=False)
    pair = read_json(tiny/'pair.json'); selected = read_json(tiny/'replay/RESULT.json')
    if pair.get('tiny_pipeline_verified') is not True or selected.get('passed') is not True:
        raise ValueError('Tiny and exact selector equality must pass first')
    results = pair.get('results', {})
    if set(results) != {'A','B'} or any(not isinstance(results[k].get('state',{}).get('trace'), list) or not results[k]['state']['trace'] for k in ('A','B')):
        raise ValueError('Both tiny arms require nonempty witness traces')
    checks = []; passed = True
    for arm in ('A','B'):
        for index, stage in enumerate(pair['results'][arm]['state']['trace'],1):
            rd = Path(stage['stage_directory']); prefix = out/f'{arm}_{index:02d}_{stage["kind"]}'
            result = Path(str(prefix)+'.json'); receipt = Path(str(prefix)+'.receipt.json')
            command = [sys.executable,'-B','-s',str(HERE/'frozen_core_check.py'),
                       '--pairs',str(rd/'pairs.json'),'--kind',stage['kind'],'--model',str(rd/'master.mps'),
                       '--solution',str(rd/'solution.sol'),'--result',str(result),'--receipt',str(receipt)]
            measured = execute(command,Path(str(prefix)+'.log'),environment(),20.)
            item = {'original_arm':arm,'stage':index,'kind':stage['kind'],'process':measured,
                    'source_sha256':sha(HERE/'tiny_triangle.json'),'solution_sha256':sha(rd/'solution.sol')}
            checks.append(item)
            if measured.get('returncode') != 0 or measured.get('hard_watchdog_killed') or measured.get('interrupted'):
                passed = False; break
            baseline = tiny/'replay'/f'{arm}_{index:02d}_{stage["kind"]}_A.json'
            other = tiny/'replay'/f'{arm}_{index:02d}_{stage["kind"]}_B.json'
            record = read_json(receipt)
            equal = (read_json(result) == read_json(baseline) == read_json(other)
                     and sha(result) == sha(baseline) == sha(other))
            item.update(equal=equal,core_receipt=record,baseline_sha256=sha(baseline),
                        optimized_sha256=sha(other),direct_core_sha256=sha(result),excluded_fields=[])
            if not equal or record.get('passed') is not True or record.get('result_sha256')!=sha(result):
                passed = False; break
        if not passed: break
    report = {'passed':passed,'checks':checks,'witness_count':len(checks),
              'runtime_freeze_sha256':sha(HERE/'REVIEW_MANIFEST.json'),
              'campaign_plan_sha256':sha(HERE/'CAMPAIGN_PLAN.json'), 'tiny_pair_sha256':sha(tiny/'pair.json'),
              'separately_charged_wall_seconds':time.monotonic()-start,
              'scope':'Direct historical mathematical/checker bytes versus both selector results on identical witnesses; same portable runtime bindings; no numerical normalization or excluded fields; no solve/generation/readback'}
    write_json(out/'RESULT.json',report,fresh=True)
    return passed
