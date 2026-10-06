#!/usr/bin/env python3
"""Prospective v3 helper build; invoked only after an explicit build budget."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_scuc.runtime import HELPER_SOURCE_SHA256, SOURCE_COMMIT, sha256, validate_build


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--cxx',default='g++')
    args=parser.parse_args()
    source,build=args.source.resolve(strict=True),args.build.resolve(strict=True)
    helper=Path(__file__).with_name('native_assess.cpp').resolve()
    if sha256(helper)!=HELPER_SOURCE_SHA256:
        raise ValueError('Assessment v3 source changed')
    validate_build(build/'CMakeCache.txt',build/'HConfig.h')
    output=build/'bin/native_assess'
    receipt=build/'native-assess-build.json'
    if output.exists() or receipt.exists():
        raise ValueError('Helper build outputs must be fresh')
    library=(build/'lib/libhighs.so.1.15.1').resolve(strict=True)
    command=[args.cxx,'-std=c++17','-O3','-DNDEBUG','-I'+str(source/'highs'),'-I'+str(build),
             str(helper),'-L'+str(library.parent),'-lhighs','-ldl','-Wl,-rpath,$ORIGIN/../lib','-o',str(output)]
    version=subprocess.run([args.cxx,'--version'],check=True,text=True,capture_output=True,timeout=10).stdout
    subprocess.run(command,check=True,timeout=120)
    result=dict(schema='current-scuc-native-assess-build/v1',source_sha256=sha256(helper),
                source_commit=SOURCE_COMMIT,library_sha256=sha256(library),binary_sha256=sha256(output),
                hconfig_sha256=sha256(build/'HConfig.h'),command=command,compiler_version=version,
                optimization_or_presolve_executed=False,helper_execution_performed=False)
    with receipt.open('x') as stream:
        json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write('\n')
    print(receipt)


if __name__=='__main__':
    main()
