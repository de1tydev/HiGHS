#!/usr/bin/env python3
"""Bind a prospective local build to official source and actual local bytes.

This script hashes files and calls read-only Git commands. It never loads HiGHS,
runs a helper or solves. It requires a complete pristine official checkout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_scuc.runtime import (SCHEMA,SOURCE_REPOSITORY,SOURCE_COMMIT,SOURCE_TREE,NATIVE_GITHASH,
    HIGHS_VERSION,EXPECTED_OPTIONS,HELPER_SOURCE_SHA256,sha256,validate_build,git_tree_from_inventory,
    source_guard_hashes,discover_runtime)


def git(source,*args):
    return subprocess.run(['git','-C',str(source),*args],check=True,capture_output=True,timeout=60).stdout


def source_inventory(source):
    if git(source,'rev-parse','HEAD').decode().strip()!=SOURCE_COMMIT:
        raise ValueError('Checkout does not identify the official required commit')
    if git(source,'rev-parse','HEAD^{tree}').decode().strip()!=SOURCE_TREE:
        raise ValueError('Checkout does not identify the official required tree')
    if git(source,'status','--porcelain','--untracked-files=no').strip():
        raise ValueError('Native source checkout has tracked modifications')
    result=[]
    for item in git(source,'ls-tree','-r','-z','HEAD').split(b'\0'):
        if not item:
            continue
        metadata,name=item.split(b'\t',1)
        mode,kind,blob=metadata.decode().split()
        name=name.decode()
        if kind!='blob' or mode not in ('100644','100755'):
            raise ValueError('Unsupported source entry: '+name)
        path=source/name
        if path.is_symlink():
            raise ValueError('Unexpected source symlink: '+name)
        data=path.read_bytes()
        observed=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if observed!=blob:
            raise ValueError('Native source bytes differ from official Git object: '+name)
        result.append(dict(path=name,mode=mode,git_blob=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    if git_tree_from_inventory(result)!=SOURCE_TREE:
        raise ValueError('Independent source tree reconstruction failed')
    for name,digest in source_guard_hashes().items():
        if sha256(source/name)!=digest:
            raise ValueError('Native source guard changed: '+name)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    source,build=args.source.resolve(strict=True),args.build.resolve(strict=True)
    output=(args.output or build/'runtime-manifest.json').resolve()
    if output.exists():
        raise ValueError('Runtime manifest output must be fresh')
    inventory=source_inventory(source)
    cache=validate_build(build/'CMakeCache.txt',build/'HConfig.h')
    helper=Path(__file__).with_name('native_assess.cpp').resolve()
    if sha256(helper)!=HELPER_SOURCE_SHA256:
        raise ValueError('Wrong assessment v3 source')
    artifacts={'binary':build/'bin/highs','library':build/'lib/libhighs.so.1.15.1',
        'extras':build/'lib/libhighs_extras.so','native_assess':build/'bin/native_assess',
        'native_assess_source':helper,'hconfig':build/'HConfig.h','cmake_cache':build/'CMakeCache.txt',
        'helper_build_receipt':build/'native-assess-build.json'}
    for stem,file in [('c_compiler','CMakeCCompiler.cmake'),('cxx_compiler','CMakeCXXCompiler.cmake')]:
        files=sorted((build/'CMakeFiles').glob('*/'+file))
        if not files:
            raise ValueError('Missing compiler evidence: '+file)
        artifacts.update({stem+'_'+str(i):path for i,path in enumerate(files)})
    records={name:dict(path=os.path.relpath(path.resolve(strict=True),output.parent),
                      sha256=sha256(path),bytes=path.stat().st_size) for name,path in artifacts.items()}
    result=dict(schema=SCHEMA,source=dict(repository=SOURCE_REPOSITORY,commit=SOURCE_COMMIT,tree=SOURCE_TREE,
                version=HIGHS_VERSION,native_githash=NATIVE_GITHASH,files=inventory),
                source_root=os.path.relpath(source,output.parent),build_root=os.path.relpath(build,output.parent),
                artifacts=records,build_options={k:cache[k] for k in EXPECTED_OPTIONS},
                compiler={k:cache[k] for k in ('CMAKE_C_COMPILER','CMAKE_CXX_COMPILER','CMAKE_GENERATOR')},
                execution_claim=dict(native_qualification_performed=False,numerical_execution_performed=False,
                                     byte_identical_to_historical_build=False))
    with output.open('x') as stream:
        json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    discover_runtime(build/'bin/highs',output)
    print(output)


if __name__=='__main__':
    main()
