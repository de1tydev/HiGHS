#!/usr/bin/env python3
"""Fresh allowlisted exact-byte selector for one scope/generation/complete check."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
SEPARATORS = {'A': HERE/'fractional_separator.py',
              'B': HERE.parent/'lp_security_separator_optimized/fractional_separator.py'}
HASHES = {'A': '0760ccabff276b927cc746437e8ee83c0517e00c6aa27f0bf12de043a50582bb',
          'B': '1833d1f645507495daac922fbeb58ba0eb5fe3f2c25e98d331b7a56fbd436293'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def reject(value): raise ValueError('Nonfinite JSON: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=reject)

def load_source(name, path, expected_sha):
    path = Path(path).resolve()
    if name in sys.modules: raise ValueError('Existing module registration: ' + name)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha: raise ValueError('Loaded source hash mismatch: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    try:
        exec(compile(raw, str(path), 'exec'), result.__dict__)
        if Path(result.__file__).resolve() != path: raise ValueError('Loaded source path mismatch')
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return result, {'path': str(path), 'sha256': digest, 'loading': 'compile exact pinned source bytes'}

def validate_plan(plan, arm):
    expected = {'A': {'name': 'A', 'lp_discovery': False, 'root_credit': False, 'separator_variant': 'baseline'},
                'B': {'name': 'B', 'lp_discovery': True, 'root_credit': True, 'separator_variant': 'optimized'}}
    if arm not in expected or plan.get('arms') != expected: raise ValueError('Frozen arm record mismatch')
    paths = {'contracts': str(HERE/'contracts.py'), 'fractional_separator': str(SEPARATORS[arm]),
             'primal_and_bound': str(HERE/'primal_and_bound.py'), 'model_stage': str(HERE/'model_stage.py')}
    if plan.get('common_module_paths') != {k:v for k,v in paths.items() if k != 'fractional_separator'}:
        raise ValueError('Nonallowlisted common module path')
    if plan.get('separator_paths') != {k:str(v) for k,v in SEPARATORS.items()}:
        raise ValueError('Nonallowlisted separator path')
    pins = plan.get('module_sha256', {})
    if pins.get(paths['fractional_separator']) != HASHES[arm]: raise ValueError('Separator pin mismatch')
    if any(p not in pins for p in paths.values()): raise ValueError('Required module pin missing')
    return paths

def load_selected(plan, arm):
    paths = validate_plan(plan, arm)
    loaded = {}
    for name in ('contracts', 'fractional_separator', 'primal_and_bound', 'model_stage'):
        _, loaded[name] = load_source(name, paths[name], plan['module_sha256'][paths[name]])
    return sys.modules['model_stage'], loaded

def input_identity(source, pair_path, model, solution):
    paths = {'source': source, 'pairs': pair_path, 'model': model,
             'expected': str(model)+'.expected.json', 'api': str(model)+'.readback.json',
             'metadata': str(model)+'.meta.json', 'solution': solution}
    return {k: {'path': str(v), 'sha256': sha(v)} for k,v in paths.items() if v and Path(v).is_file()}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['scope', 'generate', 'check'])
    p.add_argument('--plan', required=True); p.add_argument('--plan-sha256', required=True)
    p.add_argument('--arm', choices=['A', 'B'], required=True)
    p.add_argument('--source', required=True); p.add_argument('--hours', type=int, required=True)
    p.add_argument('--pairs'); p.add_argument('--kind', choices=['lp', 'mip'])
    p.add_argument('--model'); p.add_argument('--solution')
    p.add_argument('--result', required=True); p.add_argument('--receipt', required=True)
    a = p.parse_args()
    receipt = {'arm': a.arm, 'action': a.action, 'kind': a.kind, 'passed': False,
               'plan_sha256': a.plan_sha256, 'source': a.source, 'hours': a.hours}
    try:
        if Path(a.plan).resolve() != HERE/'CAMPAIGN_PLAN.json' or sha(a.plan) != a.plan_sha256:
            raise ValueError('Plan path/identity mismatch')
        plan = read_json(a.plan)
        # Paths are checked before executing any supplied bytes.
        validate_plan(plan, a.arm)
        if a.source not in plan['allowed_sources'] or plan['allowed_sources'][a.source]['hours'] != a.hours:
            raise ValueError('Unreviewed source/hours')
        if sha(a.source) != plan['allowed_sources'][a.source]['sha256']: raise ValueError('Source changed')
        stage, loaded = load_selected(plan, a.arm)
        freeze = stage.runtime_manifest()
        if freeze['artifact_sha256'].get(str(HERE/'CAMPAIGN_PLAN.json')) != a.plan_sha256:
            raise ValueError('Plan not bound to runtime freeze')
        receipt.update(arm_record=plan['arms'][a.arm], loaded_python_modules=loaded,
                       runtime_manifest_sha256=sha(HERE/'REVIEW_MANIFEST.json'),
                       input_identity=input_identity(a.source, a.pairs, a.model, a.solution))
        if a.action == 'scope':
            data = stage.source_data(a.source)
            result = sys.modules['fractional_separator'].source_scope(data, a.hours)
            result = {'scope': result, 'dimensions': {k:len(data[k]) for k in ('Buses','Generators','Transmission lines')}}
        elif a.action == 'generate':
            result = stage.generate(a.source, a.hours, a.pairs, a.kind, a.model)
        else:
            result = stage.check(a.source, a.hours, a.pairs, a.kind, a.model, a.solution)
        stage.write_json(a.result, result, fresh=True)
        stage.runtime_manifest()
        receipt.update(passed=True, input_identity=input_identity(a.source, a.pairs, a.model, a.solution),
                       output_sha256=sha(a.result), python_executable=sys.executable,
                       python=sys.version)
        stage.write_json(a.receipt, receipt, fresh=True)
        return 0
    except BaseException as exc:
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        traceback.print_exc()
        # Errors must remain inspectable even if loading contracts itself failed.
        for path, value in ((a.result, {'error': receipt['error']}), (a.receipt, receipt)):
            target = Path(path)
            if not target.exists():
                with target.open('x') as stream:
                    json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush()
                    import os
                    os.fsync(stream.fileno())
        return 2

if __name__ == '__main__': raise SystemExit(main())
