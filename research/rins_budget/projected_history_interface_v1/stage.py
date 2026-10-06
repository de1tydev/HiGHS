"""Materialize a fresh experimental package from four overlay files, without running it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ADAPTER_SHA = '64fc588e461c918ead65bd55c9c0dbaa9667f3047d0ba95734e41ea9b48944ca'
QUALIFIED_REVIEW = 'd3f28f71864a303c616d1c84e1d41952b966c2f72f0f5c0616d7643bfa70cc9e'
OCTOBER_SOURCE = 'b64be5dcaec762356291b8ee353ee242869e2a8a0c68859aa477a4431dc1d9d6'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--adapter',type=Path,required=True)
    p.add_argument('--recovery-root',type=Path,required=True)
    p.add_argument('--mode',choices=('history','tiny_history'),default='history')
    a=p.parse_args()
    base=HERE.parent/'current_scuc/current_scuc';support=HERE.parent/'checked_history_interface_v1'
    if a.out.exists() or a.out.is_symlink() or not a.out.parent.is_dir():raise ValueError('Fresh staged parent required')
    if sha(a.adapter)!=ADAPTER_SHA or sha(support/'SOURCE_REVIEW_v2.json')!=QUALIFIED_REVIEW:raise ValueError('Qualified source/adapter changed')
    review=json.loads((support/'SOURCE_REVIEW_v2.json').read_text())
    names=('common.py','history.py','june_label.py','june_admission_pins.json')
    for name in names:
        if sha(support/name)!=review['files'][name]['sha256']:raise ValueError('Qualified historical importer changed')
    source_pins={name:sha(support/name) for name in names}
    source_pins['../generalization_20261006/history_start.py']=sha(support/'../generalization_20261006/history_start.py')
    before={str(path.relative_to(base)):sha(path) for path in base.rglob('*') if path.is_file()}
    if any(path.is_symlink() for path in base.rglob('*')):raise ValueError('Symlink source is not supported')
    a.out.mkdir();target=a.out/'current_scuc'
    # A disposable ~1 MiB isolated copy prevents staged edits touching the base.
    # Only the four-file overlay is maintained/published as source.
    shutil.copytree(base,target,copy_function=shutil.copy2)
    for path in sorted((HERE/'overlay/current_scuc').glob('*.py')):
        destination=target/path.name
        if destination.exists():destination.unlink()
        shutil.copyfile(path,destination)
    manifest=target/'SOURCE_MANIFEST.json';manifest.unlink()
    plan=dict(schema='projected-history-fixed-plan/v1',mode=a.mode,simulated_chronology=True,solver_random_seed=1,
              historical_scenario_start='2017-06-01T00:00:00+00:00',target_scenario_start='2017-10-01T00:00:00+00:00',
              target_raw_source_sha256=OCTOBER_SOURCE,adapter=dict(path=str(a.adapter.resolve()),sha256=ADAPTER_SHA),
              qualified_interface=str(support.resolve()),qualified_source_pins=source_pins,recovery_root=str(a.recovery_root.resolve()))
    plan['profile']=(dict(admission=30.,probe_process=30.,probe_native=25.,check=60.,ordinary_reserve=180.,final_reserve=360.)
        if a.mode=='history' else dict(admission=2.,probe_process=30.,probe_native=25.,check=5.,ordinary_reserve=80.,final_reserve=20.))
    (target/'history_plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n')
    # Identical file selection/encoding to the existing tools/seal_source.py.
    files=sorted([*target.rglob('*.py'),*(path for path in target.glob('*.json') if path.name!='SOURCE_MANIFEST.json')])
    source=dict(schema='current-scuc-package-source/v1',files_sha256={path.relative_to(target).as_posix():sha(path) for path in files})
    manifest.write_text(json.dumps(source,indent=2,sort_keys=True)+'\n')
    if before!={str(path.relative_to(base)):sha(path) for path in base.rglob('*') if path.is_file()}:raise ValueError('Published package changed while staging')
    result=dict(staged_package=str(target.resolve()),source_manifest_sha256=sha(manifest),history_plan_sha256=sha(target/'history_plan.json'),
                modified_runtime_files=['phase.py','carry.py','receipts.py','history_scuc.py'],base_files_unchanged=True,
                isolated_base_copy=True,native_calls=0,mode=a.mode)
    (a.out/'STAGED.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
