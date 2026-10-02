#!/usr/bin/env python3
"""Prepare an immutable materialized replay, then explicitly launch a frozen phase."""
import argparse
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE/'payload/combined_screening_driver'))
from portable_runtime import (BindingError, STATUS, DATES, assert_clean_bundle, bindings,
    checked_path, fresh_directory, minimal_environment, read_json, relative_path,
    release_pins, sha, validate_manifest, verify, write_json)

PIN = '73cac48c5340d775a477087198611862559be250'

def release(research=None):
    manifest = read_json(PACKAGE/'PACKAGE_MANIFEST.json')
    files = {str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob('*') if p.is_file() or p.is_symlink()}
    if files != set(manifest['files']) | {'PACKAGE_MANIFEST.json'}:
        raise BindingError('Release package contains missing or unexpected files (including bytecode)')
    verify({str(relative_path(PACKAGE, name)): digest for name, digest in manifest['files'].items()})
    if research is not None:
        verify({str(relative_path(research, name)): digest for name, digest in manifest['external_files'].items()})
    return manifest

def source_inventory(source):
    expected = {}
    for line in (PACKAGE/'SOURCE_TREE.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if name in expected: raise BindingError('Duplicate source inventory entry')
        expected[name] = digest
    if len(expected) != 984: raise BindingError('Incomplete patched source inventory')
    actual = set()
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if relative.parts[0] == '.git': continue
        if path.is_file() or path.is_symlink(): actual.add(str(relative))
    if actual != set(expected): raise BindingError('Patched source has extra or missing files')
    verify({str(relative_path(source, name)): digest for name, digest in expected.items()})
    # The complete patched tree, rather than repository metadata or mutable HEAD,
    # is the executable source authority. .git is deliberately excluded.
    return {'base_commit': PIN, 'source_files': len(expected), 'inventory_sha256': sha(PACKAGE/'SOURCE_TREE.sha256'),
            'exact_tree_verified': True}

def cmake_cache(path):
    fields = {}
    for line in path.read_text().splitlines():
        match = re.match(r'^([^#/:][^:]*):[^=]+=(.*)$', line)
        if match: fields[match[1]] = match[2]
    return fields

def build_identity(source, build):
    cache = build/'CMakeCache.txt'; config = build/'HConfig.h'
    fields = cmake_cache(cache)
    required = {'CMAKE_BUILD_TYPE':'Release', 'FAST_BUILD':'ON', 'BUILD_SHARED_LIBS':'ON',
                'HIPO':'OFF', 'HIGHSINT64':'OFF', 'BUILD_TESTING':'ON', 'ALL_TESTS':'ON',
                'CMAKE_C_FLAGS':'', 'CMAKE_CXX_FLAGS':'',
                'CMAKE_C_FLAGS_RELEASE':'-O3 -DNDEBUG', 'CMAKE_CXX_FLAGS_RELEASE':'-O3 -DNDEBUG'}
    if any(fields.get(key) != value for key, value in required.items()):
        raise BindingError('Build flags differ from the published exact recipe')
    for key, value in fields.items():
        if (re.fullmatch(r'CMAKE_(EXE|MODULE|SHARED|STATIC)_LINKER_FLAGS(_RELEASE)?',key)
                or key in ('CMAKE_TOOLCHAIN_FILE','CMAKE_C_COMPILER_LAUNCHER','CMAKE_CXX_COMPILER_LAUNCHER')) and value:
            raise BindingError('Unreviewed build override: '+key)
        if key.startswith('CMAKE_INTERPROCEDURAL_OPTIMIZATION') and value.upper() not in ('','OFF','FALSE','0'):
            raise BindingError('Unreviewed interprocedural optimization override')
    if Path(fields.get('CMAKE_HOME_DIRECTORY', '')).resolve() != source:
        raise BindingError('Build source directory mismatch')
    header = config.read_text()
    if re.search(r'^\s*#\s*define\s+(HIGHSINT64|HIPO)\b', header, re.M):
        raise BindingError('64-bit HighsInt or HIPO build is unsupported')
    if not re.search(r'^\s*#\s*define\s+FAST_BUILD\b', header, re.M) or not re.search(r'^\s*#\s*define\s+CMAKE_BUILD_TYPE\s+"Release"', header, re.M):
        raise BindingError('Generated configuration header differs from shared Release/FAST_BUILD recipe')
    binary = checked_path(str(build/'bin/highs'))
    if not binary.is_relative_to(build): raise BindingError('Executable escapes selected build')
    library = checked_path(str(build/'lib/libhighs.so'), library=True)
    extras = checked_path(str(build/'lib/libhighs_extras.so'), library=True)
    aliases = sorted(set([*build.glob('lib/libhighs.so*'), *build.glob('lib/libhighs_extras.so*')]))
    if not (build/'lib/libhighs.so.1').exists(): raise BindingError('Shared-library SONAME alias missing')
    library_pins = {}
    alias_targets = {}
    for alias in aliases:
        target = checked_path(str(alias), library=True)
        expected = extras if alias.name.startswith('libhighs_extras.so') else library
        if target != expected or not target.is_relative_to(build): raise BindingError('Unexpected shared-library alias target')
        library_pins[str(alias.absolute())] = sha(alias)
        library_pins[str(target)] = sha(target)
        alias_targets[str(alias.absolute())] = str(target)
    pins = {str(cache):sha(cache), str(config):sha(config), str(binary):sha(binary), **library_pins}
    compiler_metadata = sorted(build.glob('CMakeFiles/*/CMake*Compiler.cmake'))
    if not compiler_metadata: raise BindingError('Compiler metadata missing')
    for item in compiler_metadata: pins[str(item)] = sha(item)
    return {'binary':str(binary), 'library':str(library), 'extras':str(extras),
            'runtime_library_pins':library_pins, 'runtime_pins':{str(binary):sha(binary), **library_pins},
            'build_pins':pins, 'aliases':alias_targets, 'flags':required,
            'compiler': {k:v for k,v in fields.items() if k in ('CMAKE_C_COMPILER','CMAKE_CXX_COMPILER','CMAKE_GENERATOR')}}

def verify_data(data, manifest):
    pins = {}
    for date,record in manifest['data'].items():
        path = relative_path(data,record['filename'])
        if not path.is_relative_to(data): raise BindingError('Input escapes data directory')
        if sha(path) != record['compressed_sha256']: raise BindingError('Compressed data hash mismatch: '+date)
        digest = hashlib.sha256()
        with gzip.open(path, 'rb') as stream:
            for block in iter(lambda:stream.read(1024*1024), b''): digest.update(block)
        if digest.hexdigest() != record['decompressed_sha256']: raise BindingError('Decompressed data hash mismatch: '+date)
        pins[str(path)] = record['compressed_sha256']
    return pins

def clean_env(work, library=None):
    result = {'PATH':'/usr/bin:/bin', 'LANG':'C', 'LC_ALL':'C', 'TZ':'UTC',
              'HOME':str(work/'environment/home'), 'TMPDIR':str(work/'environment/tmp'),
              'XDG_CACHE_HOME':str(work/'environment/cache'), 'PYTHONDONTWRITEBYTECODE':'1',
              'PYTHONNOUSERSITE':'1', 'PYTHONHASHSEED':'0', 'OPENBLAS_NUM_THREADS':'1',
              'OMP_NUM_THREADS':'1', 'MKL_NUM_THREADS':'1', 'NUMEXPR_NUM_THREADS':'1'}
    if library: result['LD_LIBRARY_PATH'] = str(Path(library).parent)
    return result

def bounded(command, *, env, cwd, timeout=120, stdout_path=None, stderr_path=None):
    from resource_guard import apply_process_limit
    # No inherited environment, shell interpolation, or unbounded helper wait.
    def retain(stdout, stderr):
        for path, text in ((stdout_path, stdout), (stderr_path, stderr)):
            if path is not None:
                with Path(path).open('x') as stream:
                    stream.write(text); stream.flush(); os.fsync(stream.fileno())
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=env, cwd=cwd, start_new_session=True, preexec_fn=apply_process_limit)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        stdout, stderr = process.communicate()
        retain(stdout, stderr)
        raise
    retain(stdout, stderr)
    if process.returncode: raise BindingError('Helper failed: '+stderr[-4000:])
    return stdout, stderr

def validate_version_loader(stderr, value):
    """Version-only loader observation; extras is lazy in the pinned source.

    This does not replace the unchanged mandatory main AND extras checks in
    every actual LP/MIP process, nor the C API function-address provider checks.
    """
    main, extras = [], []
    # Consume the complete initialization-line remainder before classification.
    # A whitespace-bearing unexpected provider must fail, never look absent.
    for path in re.findall(r'calling init:[ \t]*([^\r\n]*)', stderr):
        if re.search(r'(?:^|/)libhighs_extras\.so', path):
            checked_path(path, library=True); extras.append(path)
        elif re.search(r'(?:^|/)libhighs\.so', path):
            checked_path(path, library=True); main.append(path)
    if len(main) != 1 or len(extras) > 1:
        raise BindingError('Missing or duplicate version-loader initialization record')
    for observed, expected in ((main, value['library']), (extras, value['extras'])):
        for path in observed:
            resolved = checked_path(path, library=True)
            if str(resolved) != expected or sha(resolved) != value['runtime_library_pins'][expected]:
                raise BindingError('Version command loaded an unexpected main/extras library')
    return {'main':main, 'extras':extras,
            'extras_observation':'initialized_exact' if extras else 'not_initialized_by_version_command',
            'scope':'Version-only observation; extras is lazy. Actual LP/MIP processes still require exact loaded main and extras identities.'}

def python_identity(python, work, library):
    stdout, _ = bounded([str(python), '-I', '-S', '-B', str(PACKAGE/'payload/combined_screening_driver/runtime_inspect.py'), '--startup'],
                        env=clean_env(work, library), cwd=work)
    # The helper emits JSON generated from stdlib metadata, no external input.
    result = json.loads(stdout)
    if Path(result['python_executable']).absolute() != python.absolute(): raise BindingError('Python executable binding mismatch')
    pins = {str(python.absolute()):sha(python), str(python.resolve()):sha(python)}
    if result['pyvenv_cfg']: pins[result['pyvenv_cfg']] = sha(result['pyvenv_cfg'])
    for package, item in result['installations'].items():
        roots = [Path(item['root']), Path(item['metadata'])]
        native = Path(item['root']).with_name(package+'.libs')
        if native.exists(): roots.append(native)
        for root in roots:
            for path in root.rglob('*'):
                if path.is_symlink() and not path.resolve().is_relative_to(root.parent.resolve()):
                    raise BindingError('Scientific installation symlink escapes installation root')
                if path.is_file(): pins[str(path.resolve())] = sha(path)
    return result, pins

def freeze(work, value):
    started = time.monotonic(); here = Path(value['driver']); receipt = {'status':'started'}
    write_json(work/'preflight.started.json', {'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    try:
        verify(release_pins(value)); verify(value['preparation_pins']); assert_clean_bundle(here,value)
        source_receipt = source_inventory(Path(value['source']))
        current = build_identity(Path(value['source']),Path(value['build']))
        if current['aliases'] != value['aliases'] or current['runtime_pins'] != value['runtime_pins']:
            raise BindingError('Build aliases or executable changed after preparation')
        env = minimal_environment(here)
        # Repeat isolated startup inspection before launching a normal site-enabled child.
        current_python, current_pins = python_identity(Path(value['python']),work,value['library'])
        if current_python != value['python_inspection'] or any(value['preparation_pins'].get(p)!=h for p,h in current_pins.items()):
            raise BindingError('Python installation changed after preparation')
        inspection_start = time.monotonic()
        bounded([value['python'],'-B','-s',str(here/'runtime_inspect.py'),'--output',str(work/'runtime_inventory.json')],env=env,cwd=work)
        inventory = read_json(work/'runtime_inventory.json')
        # Verify exact binary-loaded main/extras identity using glibc's loader log,
        # not ldd or a successful dlopen. This is a --version invocation only.
        stdout_path, stderr_path = work/'loader_version.stdout.log', work/'loader_version.stderr.log'
        stdout, stderr = bounded([value['binary'],'--version'],env=dict(env,LD_DEBUG='libs'),cwd=work,
                                 stdout_path=stdout_path,stderr_path=stderr_path)
        observation = validate_version_loader(stderr,value)
        loaded, extras = observation['main'], observation['extras']
        loader_pins = {}
        for path in re.findall(r'calling init:\s*(\S+)',stderr):
            if path.startswith('/'):
                resolved = checked_path(path); loader_pins[str(resolved)] = sha(resolved)
        # Inventory is append-free and immutable. Loader dependencies are retained
        # in a separate frozen receipt, also part of every stage's mandatory pins.
        loader_pins.update({str(stdout_path):sha(stdout_path),str(stderr_path):sha(stderr_path)})
        loader_record = {'artifact_sha256':loader_pins,**observation,'version_output':stdout.strip()}
        write_json(work/'loader_inventory.json', loader_record)
        inventory_digest = sha(work/'runtime_inventory.json')
        pins = {**release_pins(value), **value['preparation_pins'], **inventory['artifact_sha256'],
                str(here/'BINDINGS.json'):sha(here/'BINDINGS.json'),
                str(here/'CAMPAIGN_PLAN.json'):value['campaign_plan_sha256'],
                str(work/'runtime_inventory.json'):inventory_digest,
                str(work/'loader_inventory.json'):sha(work/'loader_inventory.json'), **loader_pins}
        record = {'status':STATUS, 'release_sha256':value['release_sha256'],
                  'bindings_sha256':sha(here/'BINDINGS.json'),'runtime_inventory_sha256':inventory_digest,
                  'loader_inventory_sha256':sha(work/'loader_inventory.json'),'artifact_sha256':pins,
                  'runtime_identity_scope':'This local runtime; historical binary bytes/timings are not inherited',
                  'optimization_called':False, 'real_model_generation_called':False,'real_model_api_readback_called':False,
                  'runtime_abi_preflight_called':True,'scientific_imports_called':True}
        write_json(here/'RUNTIME_MANIFEST.json', record)
        receipt.update(status='passed', source=source_receipt, runtime_inspection_seconds=time.monotonic()-inspection_start,
                       main_library_paths=loaded,extras_library_paths=extras,
                       runtime_manifest_sha256=sha(here/'RUNTIME_MANIFEST.json'))
    except BaseException as exc:
        receipt.update(status='failed_preserved',error=type(exc).__name__+': '+str(exc)); raise
    finally:
        receipt['loader_logs'] = {name:sha(work/name) for name in ('loader_version.stdout.log','loader_version.stderr.log') if (work/name).is_file()}
        receipt['preflight_freeze_seconds'] = time.monotonic()-started
        receipt['timing_scope'] = 'Explicit separately reported provisioning; imports and C API scalar ABI checks, no solve/model prep'
        write_json(work/'preflight_receipt.json',receipt)

def prepare(args):
    """Reuse the published source/build/Python inspection and materialization contract."""
    from resource_guard import apply_process_limit,guard_storage
    apply_process_limit();started=time.monotonic();research=PACKAGE;manifest=release(research)
    source,build,data=[checked_path(getattr(args,k)) for k in ('source','build','data')]
    for first,second in ((source,build),(source,data),(build,data)):
        if first==second or first.is_relative_to(second) or second.is_relative_to(first):raise BindingError('Source/build/data must be disjoint')
    python=Path(args.python).absolute();checked_path(str(python))
    payload_bytes=sum((PACKAGE/name).stat().st_size for name in manifest['files'] if name.startswith('payload/'))
    guard_storage(Path(args.work).absolute().parent,3*payload_bytes+64*1024**2)
    work=fresh_directory(args.work,(PACKAGE,source,build,data,python.parent))
    for name in ('home','tmp','cache'):(work/'environment'/name).mkdir(parents=True,exist_ok=False)
    (work/'runs').mkdir()
    receipt=dict(status='preparing',optimization_called=False,scientific_import_called=False,model_generation_called=False,api_called=False)
    try:
        source_receipt=source_inventory(source);build_record=build_identity(source,build)
        data_pins=verify_data(data,manifest);python_record,python_pins=python_identity(python,work,build_record['library'])
        replay=work/'replay';replay.mkdir()
        for name in manifest['files']:
            if not name.startswith('payload/'):continue
            destination=replay/name.removeprefix('payload/');destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:stream.write(relative_path(PACKAGE,name).read_bytes())
        here=replay/'combined_screening_driver'
        from policy import arm_record
        paths={name:str(here/(name+'.py')) for name in ('pair_codec','witness_store','resource_guard','release_gate','contracts','primal_and_bound','model_stage')}
        separators={'A':here/'fractional_separator.py','B':replay/'lp_security_separator_optimized/fractional_separator.py','C':replay/'lp_security_separator_optimized/fractional_separator.py'}
        cases={name:str(relative_path(data,item['filename'])) for name,item in manifest['data'].items()}
        sources={cases[name]:dict(sha256=item['compressed_sha256'],hours=36,scope=item['scope'],dimensions=item['dimensions'],kind='reserved') for name,item in manifest['data'].items()}
        sources[str(here/'tiny_triangle.json')]=dict(sha256=sha(here/'tiny_triangle.json'),hours=2,kind='synthetic')
        plan=dict(schema='portable-early-source-plan-v1',release_sha256=sha(PACKAGE/'PACKAGE_MANIFEST.json'),
            arms={k:arm_record(k) for k in ('A','B','C')},common_module_paths=paths,separator_paths={k:str(v) for k,v in separators.items()},
            module_sha256={p:sha(p) for p in [*paths.values(),*map(str,separators.values())]},allowed_sources=sources,cases=cases,
            supported_seeds=[211,212,213],explicit_run_required=True,source_exposure_sha256=sha(here/'SOURCE_EXPOSURE.json'))
        write_json(here/'CAMPAIGN_PLAN.json',plan)
        preparation_pins={**build_record['build_pins'],**data_pins,**python_pins,str(PACKAGE/'SOURCE_TREE.sha256'):sha(PACKAGE/'SOURCE_TREE.sha256')}
        value=dict(schema=1,driver=str(here),work=str(work),package=str(PACKAGE),research_package=str(PACKAGE),source=str(source),build=str(build),data=str(data),
            python=str(python),python_inspection=python_record,release_sha256=sha(PACKAGE/'PACKAGE_MANIFEST.json'),campaign_plan_sha256=sha(here/'CAMPAIGN_PLAN.json'),
            preparation_pins=preparation_pins,**{k:build_record[k] for k in ('binary','library','extras','runtime_library_pins','runtime_pins','aliases')})
        write_json(here/'BINDINGS.json',value);verify(release_pins(value));verify(preparation_pins);assert_clean_bundle(here,value)
        receipt.update(status='prepared_no_numerical_launch',source=source_receipt,build_flags=build_record['flags'],compiler=build_record['compiler'],
            python=python_record,release_sha256=value['release_sha256'],bindings_sha256=sha(here/'BINDINGS.json'),plan_sha256=sha(here/'CAMPAIGN_PLAN.json'))
    except BaseException as exc:receipt.update(status='failed_preserved',error=type(exc).__name__+': '+str(exc));raise
    finally:
        receipt['preparation_seconds']=time.monotonic()-started
        receipt['timing_scope']='Separate provisioning; source/build/data/package/interpreter metadata checks, no scientific import, model or solve'
        write_json(work/'materialization_receipt.json',receipt)
    print(json.dumps(dict(work=str(work),status=receipt['status'],next='preflight --work WORK')))

def fetch_data(args):
    """Fetch exactly the three public source files, with compressed/decompressed hashes."""
    manifest=release();data=fresh_directory(args.data,(PACKAGE,));records=[]
    try:
        for case,item in manifest['data'].items():
            request=urllib.request.Request(item['url'],headers={'User-Agent':'portable-early-integer-replay-v1'})
            destination=data/item['filename']
            with urllib.request.urlopen(request,timeout=120) as response,destination.open('xb') as stream:
                count=0
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    count+=len(block)
                    if count>32*1024**2:raise BindingError('Public input exceeds fixed size guard')
                    stream.write(block)
                stream.flush();os.fsync(stream.fileno())
                records.append(dict(case=case,url=item['url'],resolved_url=response.geturl(),bytes=count,sha256=sha(destination)))
            if sha(destination)!=item['compressed_sha256']:raise BindingError('Public compressed input changed: '+case)
        verify_data(data,manifest)
        write_json(data/'FETCH_RECEIPT.json',dict(passed=True,records=records))
    except BaseException as exc:
        write_json(data/'FETCH_FAILURE.json',dict(error=type(exc).__name__+': '+str(exc),records=records));raise
    print(json.dumps(dict(data=str(data),verified_public_cases=list(manifest['data']))))

def run(args):
    release();work=checked_path(args.work);here=work/'replay/combined_screening_driver';value=bindings(here)
    if value is None or Path(value['package'])!=PACKAGE:raise BindingError('Use the exact prepared package/work binding')
    if not (here/'RUNTIME_MANIFEST.json').is_file():raise BindingError('Run preflight first')
    verify(release_pins(value));verify(value['preparation_pins']);assert_clean_bundle(here,value)
    out=checked_path(args.out,exists=False)
    if not out.is_relative_to(work/'runs'):raise BindingError('Choose a fresh output below WORK/runs')
    if out.exists() or out.is_symlink():raise BindingError('Refusing existing output')
    if args.tiny:
        if args.seed is not None:raise BindingError('Tiny has fixed seed0')
    elif args.seed not in (None,211,212,213):raise BindingError('Supported public case seeds are211,212,213')
    command=[value['python'],'-B','-s',str(here/'consumer_launch.py'),'--out',str(out),'--arm',args.arm]
    if args.tiny:command+=['--tiny']
    else:command+=['--case',args.case,'--seed',str(args.seed or 211)]
    # The consumer launcher owns the unchanged per-arm process envelopes and cancellation.
    os.execve(value['python'],command,minimal_environment(here))

def verify_output(args):
    release();work=checked_path(args.work);here=work/'replay/combined_screening_driver';value=bindings(here)
    if value is None or Path(value['package'])!=PACKAGE:raise BindingError('Wrong prepared package/work binding')
    out=checked_path(args.out)
    if not out.is_relative_to(work/'runs'):raise BindingError('Output must be below prepared WORK/runs')
    command=[value['python'],'-B','-s',str(here/'verify_run.py'),'--out',str(out)]
    os.execve(value['python'],command,minimal_environment(here))

def main():
    from resource_guard import apply_process_limit
    apply_process_limit()
    if not sys.flags.no_site or not sys.flags.isolated or not __debug__:raise BindingError('Invoke with python3 -I -S -B')
    parser=argparse.ArgumentParser(description='Prepare and run the fixed early-only PG89 replay')
    sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare',help='Source/build/data/interpreter inspection and fresh materialization; no solve')
    for option in ('source','build','data','python','work'):prep.add_argument('--'+option,required=True)
    fetch=sub.add_parser('fetch-data',help='Download only the three hash-checked public PG89 inputs');fetch.add_argument('--data',required=True)
    runtime=sub.add_parser('preflight',help='Native/scientific provider and scalar ABI checks; no model or solve');runtime.add_argument('--work',required=True)
    verify_cli=sub.add_parser('verify',help='Offline artifact/debit/numerical-certificate consistency; no solve/API');verify_cli.add_argument('--work',required=True);verify_cli.add_argument('--out',required=True)
    launch=sub.add_parser('run',help='Explicit fresh-output baseline, early or paired solve');launch.add_argument('--work',required=True);launch.add_argument('--out',required=True)
    choice=launch.add_mutually_exclusive_group(required=True);choice.add_argument('--tiny',action='store_true');choice.add_argument('--case',choices=['2017-05-01','2017-06-01','2017-09-01'])
    launch.add_argument('--seed',type=int);launch.add_argument('--arm',choices=['baseline','early','pair'],default='pair')
    args=parser.parse_args()
    if args.command=='prepare':prepare(args);return 0
    if args.command=='fetch-data':fetch_data(args);return 0
    if args.command=='verify':return verify_output(args)
    if args.command=='preflight':
        work=checked_path(args.work);value=bindings(work/'replay/combined_screening_driver')
        if value is None or Path(value['package'])!=PACKAGE:raise BindingError('Wrong prepared work binding')
        release();freeze(work,value);return 0
    return run(args)

if __name__=='__main__':
    try:raise SystemExit(main())
    except BindingError as error:raise SystemExit(str(error))
