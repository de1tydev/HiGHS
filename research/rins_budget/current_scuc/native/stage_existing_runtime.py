#!/usr/bin/env python3
"""Plan, then explicitly stage the verified recovered runtime without executing it.

Default mode is read-only. --stage copies a compact prefix only after the caller
has approved its byte and execution budget. This does not claim a new build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from current_scuc.runtime import (SCHEMA,SOURCE_REPOSITORY,SOURCE_COMMIT,SOURCE_TREE,NATIVE_GITHASH,
    HIGHS_VERSION,EXPECTED_OPTIONS,HELPER_SOURCE_SHA256,RECOVERED_NATIVE_HASHES,
    sha256,validate_build,git_tree_from_inventory,source_guard_hashes,discover_runtime)


def inventory(source):
    rows=[]
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('Unexpected recovered source symlink: '+str(path))
        if not path.is_file():
            continue
        data=path.read_bytes()
        rows.append(dict(path=path.relative_to(source).as_posix(),mode='100755' if path.stat().st_mode&0o111 else '100644',
                         git_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),
                         sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
    if git_tree_from_inventory(rows)!=SOURCE_TREE:
        raise ValueError('Recovered source tree does not match the exact official tree')
    return rows


def plan(root,prefix):
    source,build=root/'pristine-source',root/'pristine-build'
    rows=inventory(source)
    cache=validate_build(build/'CMakeCache.txt',build/'HConfig.h')
    copies={Path('bin/highs'):build/'bin/highs',Path('lib/libhighs.so.1.15.1'):build/'lib/libhighs.so.1.15.1',
            Path('lib/libhighs_extras.so'):build/'lib/libhighs_extras.so',
            Path('bin/native_assess'):root/'projected-start-containment-build-v1/native_assess',
            Path('native/native_assess.cpp'):root/'projected-start-containment-v3/native_assess.cpp',
            Path('HConfig.h'):build/'HConfig.h',Path('CMakeCache.txt'):build/'CMakeCache.txt'}
    artifacts={'binary':'bin/highs','library':'lib/libhighs.so.1.15.1','extras':'lib/libhighs_extras.so',
               'native_assess':'bin/native_assess','native_assess_source':'native/native_assess.cpp',
               'hconfig':'HConfig.h','cmake_cache':'CMakeCache.txt','helper_build_receipt':'native-assess-provenance.json'}
    for key,digest in RECOVERED_NATIVE_HASHES.items():
        if sha256(copies[Path(artifacts[key])])!=digest:
            raise ValueError('Recovered artifact is not current verified native identity: '+key)
    if sha256(copies[Path('native/native_assess.cpp')])!=HELPER_SOURCE_SHA256:
        raise ValueError('Recovered helper source is not exact v3')
    for relative,digest in source_guard_hashes().items():
        if sha256(source/relative)!=digest:
            raise ValueError('Recovered native guard mismatch: '+relative)
        copies[Path('source')/relative]=source/relative
    for stem,file in [('c_compiler','CMakeCCompiler.cmake'),('cxx_compiler','CMakeCXXCompiler.cmake')]:
        paths=sorted((build/'CMakeFiles').glob('*/'+file))
        if not paths:
            raise ValueError('Missing recovered compiler evidence')
        for i,path in enumerate(paths):
            relative=path.relative_to(build)
            copies[relative]=path
            artifacts[stem+'_'+str(i)]=str(relative)
    license_dir=Path(__file__).resolve().parents[1]/'licenses'
    for path in license_dir.iterdir():
        if path.is_file():
            copies[Path('licenses')/path.name]=path
    provenance=dict(schema='current-scuc-recovered-assess/v1',source_sha256=HELPER_SOURCE_SHA256,
                    source_commit=SOURCE_COMMIT,rebuild_performed=False,original_build_receipt_is_not_v3_proof=True,
                    native_byte_identities=RECOVERED_NATIVE_HASHES,
                    claim='Exact current v3 source and recovered binary identities; fresh actual helper qualification remains required')
    return rows,cache,copies,artifacts,provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery-root',type=Path,required=True)
    parser.add_argument('--prefix',type=Path,required=True)
    parser.add_argument('--stage',action='store_true')
    parser.add_argument('--max-bytes',type=int,default=16*1024*1024)
    args=parser.parse_args()
    root=args.recovery_root.resolve(strict=True)
    prefix=args.prefix.resolve()
    rows,cache,copies,artifacts,provenance=plan(root,prefix)
    copy_bytes=sum(path.stat().st_size for path in copies.values())
    # Full source inventory is ~250 KiB. Reserve a conservative 1 MiB for JSON and aliases.
    bound=copy_bytes+1024*1024
    if bound>args.max_bytes:
        raise ValueError('Prospective staged bytes exceed supplied --max-bytes')
    report=dict(mode='stage' if args.stage else 'plan_only',source_file_count=len(rows),source_tree=SOURCE_TREE,
                copied_regular_files=len(copies),copy_bytes=copy_bytes,maximum_total_bytes=bound,
                maximum_total_mib=bound/(1024*1024),prefix=str(prefix),native_execution_performed=False,
                shared_python_dependencies=True,environment={'LD_LIBRARY_PATH':str(prefix/'lib')},
                copies=[dict(source=str(path),destination=str(prefix/relative),bytes=path.stat().st_size,
                             sha256=sha256(path)) for relative,path in copies.items()])
    if not args.stage:
        print(json.dumps(report,indent=2,sort_keys=True))
        return
    prefix.mkdir(parents=True,exist_ok=False)
    for relative,path in copies.items():
        output=prefix/relative
        output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,output)
        if sha256(output)!=sha256(path):
            raise ValueError('Staged copy mismatch: '+str(relative))
    for alias in ('libhighs.so','libhighs.so.1'):
        (prefix/'lib'/alias).symlink_to('libhighs.so.1.15.1')
    def write(path,value):
        with path.open('x') as stream:
            json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False)
            stream.write('\n');stream.flush();os.fsync(stream.fileno())
    write(prefix/'native-assess-provenance.json',provenance)
    records={key:dict(path=relative,sha256=sha256(prefix/relative),bytes=(prefix/relative).stat().st_size)
             for key,relative in artifacts.items()}
    manifest=dict(schema=SCHEMA,runtime_identity_kind='recovered_current_v3',
                  source=dict(repository=SOURCE_REPOSITORY,commit=SOURCE_COMMIT,tree=SOURCE_TREE,
                              version=HIGHS_VERSION,native_githash=NATIVE_GITHASH,files=rows),
                  source_root='source',build_root='.',artifacts=records,
                  build_options={k:cache[k] for k in EXPECTED_OPTIONS},
                  compiler={k:cache[k] for k in ('CMAKE_C_COMPILER','CMAKE_CXX_COMPILER','CMAKE_GENERATOR')},
                  execution_claim=dict(native_qualification_performed=False,numerical_execution_performed=False,
                                       byte_identical_to_recovered_build=True,rebuild_performed=False))
    write(prefix/'runtime-manifest.json',manifest)
    write(prefix/'staging-receipt.json',report)
    total=sum(p.stat().st_size for p in prefix.rglob('*') if p.is_file() and not p.is_symlink())
    if total>bound:
        raise ValueError('Stage exceeded prospective output bound')
    discover_runtime(prefix/'bin/highs',prefix/'runtime-manifest.json')
    print(json.dumps(dict(report,actual_total_bytes=total,runtime_manifest=str(prefix/'runtime-manifest.json')),indent=2,sort_keys=True))


if __name__=='__main__':
    main()
