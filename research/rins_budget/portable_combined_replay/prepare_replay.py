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
    if len(expected) != 983: raise BindingError('Incomplete patched source inventory')
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
    for date in DATES:
        path = checked_path(str(data/('case89pegase_'+date+'.json.gz')))
        if not path.is_relative_to(data): raise BindingError('Input escapes data directory')
        record = manifest['data'][date]
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
    # No inherited environment, shell interpolation, or unbounded helper wait.
    def retain(stdout, stderr):
        for path, text in ((stdout_path, stdout), (stderr_path, stderr)):
            if path is not None:
                with Path(path).open('x') as stream:
                    stream.write(text); stream.flush(); os.fsync(stream.fileno())
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, env=env, cwd=cwd, start_new_session=True)
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

def prepare(args):
    started = time.monotonic()
    research = checked_path(args.research_package or str(PACKAGE.parent))
    manifest = release(research)
    source, build, data = [checked_path(getattr(args,k)) for k in ('source','build','data')]
    for first, second in ((source,build),(source,data),(build,data)):
        if first == second or first.is_relative_to(second) or second.is_relative_to(first):
            raise BindingError('Source, build and data roots must be disjoint')
    python = Path(args.python).absolute()  # Preserve venv invocation alias; pin its resolved target too.
    checked_path(str(python))
    work = fresh_directory(args.work, (PACKAGE, research, source, build, data, python.parent))
    for name in ('home','tmp','cache'): (work/'environment'/name).mkdir(parents=True, exist_ok=False)
    receipt = {'status':'preparing', 'optimization_called':False, 'scientific_import_called':False,
               'model_generation_called':False, 'api_called':False}
    try:
        source_receipt = source_inventory(source)
        build_record = build_identity(source, build)
        data_pins = verify_data(data, manifest)
        python_record, python_pins = python_identity(python, work, build_record['library'])
        staging = time.monotonic()
        replay = work/'replay'; replay.mkdir(exist_ok=False)
        for name, digest in manifest['files'].items():
            if not name.startswith('payload/'): continue
            destination = replay/name.removeprefix('payload/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream: stream.write(relative_path(PACKAGE,name).read_bytes())
        for origin, target in manifest['external_materialization'].items():
            destination = replay/target; destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream: stream.write(relative_path(research,origin).read_bytes())
        here = replay/'combined_screening_driver'
        # policy.py is release-verified source and contains immutable pure scheduling definitions.
        from policy import arm_record, schedule
        paths = {name:str(here/(name+'.py')) for name in ('contracts','primal_and_bound','model_stage')}
        separators = {'A':here/'fractional_separator.py', 'B':replay/'lp_security_separator_optimized/fractional_separator.py'}
        sources = {str(data/('case89pegase_'+d+'.json.gz')):{'sha256':manifest['data'][d]['compressed_sha256'],'hours':36} for d in DATES}
        sources[str(here/'tiny_triangle.json')] = {'sha256':sha(here/'tiny_triangle.json'),'hours':2}
        plan = {'status':'frozen_before_any_portable_numerical_outcome',
                'release_sha256':sha(PACKAGE/'PACKAGE_MANIFEST.json'),
                'arms':{k:arm_record(k) for k in ('A','B')}, 'common_module_paths':paths,
                'separator_paths':{k:str(v) for k,v in separators.items()},
                'module_sha256':{p:sha(p) for p in [*paths.values(), *map(str,separators.values())]},
                'allowed_sources':sources, 'confirmation':schedule(),
                'development':{'case':'2017-02-01','seed':0,'arm_order':['A','B']},
                'campaign_directory':str(here/'run_v1'),'solver_budget_per_arm':600.,'tiny_budget_per_arm':20.,
                'source_exposure_sha256':sha(here/'SOURCE_EXPOSURE.json'),'source_only_freeze':True,
                'explicit_cli_run_required':True}
        write_json(here/'CAMPAIGN_PLAN.json', plan)
        preparation_pins = {**build_record['build_pins'], **data_pins, **python_pins,
                            str(PACKAGE/'SOURCE_TREE.sha256'):sha(PACKAGE/'SOURCE_TREE.sha256')}
        value = {'schema':1, 'driver':str(here), 'work':str(work),'package':str(PACKAGE),
                 'research_package':str(research),'source':str(source),'build':str(build),'data':str(data),
                 'python':str(python),'python_inspection':python_record,
                 'release_sha256':sha(PACKAGE/'PACKAGE_MANIFEST.json'),
                 'campaign_plan_sha256':sha(here/'CAMPAIGN_PLAN.json'),
                 'preparation_pins':preparation_pins,
                 **{k:build_record[k] for k in ('binary','library','extras','runtime_library_pins','runtime_pins','aliases')}}
        write_json(here/'BINDINGS.json', value)
        verify(release_pins(value)); verify(preparation_pins)
        assert_clean_bundle(here, value)
        receipt.update(status='prepared_no_numerical_launch', source=source_receipt,
                       build_flags=build_record['flags'], compiler=build_record['compiler'],
                       python=python_record, release_sha256=value['release_sha256'],
                       bindings_sha256=sha(here/'BINDINGS.json'), plan_sha256=sha(here/'CAMPAIGN_PLAN.json'),
                       materialization_wall_seconds=time.monotonic()-staging)
    except BaseException as exc:
        receipt.update(status='failed_preserved', error=type(exc).__name__+': '+str(exc)); raise
    finally:
        receipt['preparation_function_seconds_before_receipt'] = time.monotonic()-started
        receipt['timing_scope'] = 'Starts at prepare-function entry (launcher imports/argument parsing excluded); includes source/build/data/package checks, interpreter metadata inspection and materialization; no scientific import/model/cache prep; provisioning separate from benchmark'
        write_json(work/'materialization_receipt.json', receipt)
    print(json.dumps({'work':str(work),'status':receipt['status'],'next':'run --work WORK --phase tiny --run-reviewed'}))

def fetch_data(args):
    start = time.monotonic(); manifest = release()
    data = fresh_directory(args.data, (PACKAGE,))
    for date in DATES:
        item = manifest['data'][date]
        expected_url = 'https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/'+date+'.json.gz'
        if item['url'] != expected_url: raise BindingError('Nonofficial data URL in release')
        target = data/('case89pegase_'+date+'.json.gz'); temporary = target.with_suffix('.download')
        # No credentials/proxies/config discovery or redirects to another host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): raise BindingError('Data redirect refused; provide exact hash-checked offline files')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(expected_url, timeout=60) as response, temporary.open('xb') as out:
            total = 0
            while True:
                block = response.read(1024*1024)
                if not block: break
                total += len(block)
                if total > 64*1024*1024: raise BindingError('Unexpected data size')
                out.write(block)
            out.flush(); os.fsync(out.fileno())
        if sha(temporary) != item['compressed_sha256']: raise BindingError('Downloaded compressed hash mismatch')
        digest = hashlib.sha256()
        with gzip.open(temporary,'rb') as stream:
            for block in iter(lambda:stream.read(1024*1024), b''): digest.update(block)
        if digest.hexdigest() != item['decompressed_sha256']: raise BindingError('Downloaded decompressed hash mismatch')
        os.link(temporary, target); temporary.unlink()  # Exclusive install; never replace existing data.
    write_json(data/'download_receipt.json', {'data':manifest['data'],'fetch_wall_seconds':time.monotonic()-start})
    print(json.dumps({'data':str(data),'verified_dates':list(DATES)}))

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
        write_json(here/'REVIEW_MANIFEST.json', record)
        receipt.update(status='passed', source=source_receipt, runtime_inspection_seconds=time.monotonic()-inspection_start,
                       main_library_paths=loaded,extras_library_paths=extras,
                       runtime_manifest_sha256=sha(here/'REVIEW_MANIFEST.json'))
    except BaseException as exc:
        receipt.update(status='failed_preserved',error=type(exc).__name__+': '+str(exc)); raise
    finally:
        receipt['loader_logs'] = {name:sha(work/name) for name in ('loader_version.stdout.log','loader_version.stderr.log') if (work/name).is_file()}
        receipt['preflight_freeze_seconds'] = time.monotonic()-started
        receipt['timing_scope'] = 'Explicit separately reported provisioning; imports and C API scalar ABI checks, no solve/model prep'
        write_json(work/'preflight_receipt.json',receipt)

def descendant_identities(parent):
    records = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            raw = (entry/'stat').read_text(); fields = raw[raw.rfind(')')+2:].split()
            records[int(entry.name)] = (int(fields[1]), fields[19])
        except (OSError, ValueError, IndexError): continue
    selected = {}; pending = {parent}
    while pending:
        children = {pid for pid,(ppid,_) in records.items() if ppid in pending and pid not in selected}
        selected.update({pid:records[pid][1] for pid in children}); pending = children
    return selected

def kill_identified_descendants(records):
    for pid, start in records.items():
        try:
            raw = Path('/proc')/str(pid)/'stat'
            fields = raw.read_text(); fields = fields[fields.rfind(')')+2:].split()
            if fields[19] == start: os.kill(pid, signal.SIGKILL)
        except (OSError, ValueError, IndexError): pass

def run(args):
    started = time.monotonic(); release()
    work = checked_path(args.work); here = work/'replay/combined_screening_driver'
    value = bindings(here)
    if value is None: raise BindingError('Work has no materialized binding')
    if Path(value['package']) != PACKAGE: raise BindingError('Invoke the exact package used for preparation')
    source_inventory(Path(value['source']))
    if not (here/'REVIEW_MANIFEST.json').exists(): freeze(work,value)
    receipt_path = work/(args.phase+'.launch_receipt.json')
    marker = work/(args.phase+'.launch.started.json')
    write_json(marker, {'phase':args.phase,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    receipt = {'phase':args.phase, 'status':'launching'}
    process = None
    try:
        verify(release_pins(value));verify(value['preparation_pins']);assert_clean_bundle(here,value)
        # Child performs unchanged startup/end/stage manifest verification inside
        # benchmark timing; parent preflight does not substitute those checks.
        command = [value['python'],'-B','-s',str(here/'cold_screen_pair.py'),'--run-reviewed','--phase',args.phase]
        with (work/(args.phase+'.launch.log')).open('x') as stream:
            child_started = time.monotonic()
            process = subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=minimal_environment(here),cwd=work,start_new_session=True)
            try: code = process.wait()
            except BaseException:
                # Give the driver's cancellation path the opportunity to reap its
                # own independently grouped child and preserve process debits.
                descendants = descendant_identities(process.pid)
                process.send_signal(signal.SIGINT)
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    kill_identified_descendants(descendants)
                    os.killpg(process.pid,signal.SIGKILL);process.wait()
                raise
        receipt.update(status='exited',returncode=code,
                       driver_launch_to_exit_seconds=time.monotonic()-child_started,
                       runtime_manifest_sha256=sha(here/'REVIEW_MANIFEST.json'))
        return code
    except BaseException as exc:
        receipt.update(status='failed_or_cancelled',error=type(exc).__name__+': '+str(exc));raise
    finally:
        receipt['entrypoint_seconds_before_receipt'] = time.monotonic()-started
        receipt['scope'] = 'Run-function interval includes source checks and preflight/freeze when needed, but excludes launcher interpreter startup, imports and argument parsing. driver_launch_to_exit_seconds measures the complete benchmark child launch through exact wait; final receipt excluded. Provisioning remains separate from unchanged standalone-equivalent arm endpoints'
        write_json(receipt_path,receipt)

def cancellation_signal(signum, frame):
    raise KeyboardInterrupt('Replay cancelled by signal '+str(signum))

def main():
    for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(signum, cancellation_signal)
    if not sys.flags.no_site or not sys.flags.isolated or not __debug__:
        raise BindingError('Launch this entrypoint with python3 -I -S -B (assertions enabled)')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    prep = sub.add_parser('prepare',help='Source-only validation and materialization; never imports science')
    prep.add_argument('--research-package')
    for option in ('source','build','data','python','work'):prep.add_argument('--'+option,required=True)
    fetch = sub.add_parser('fetch-data',help='Download only the three hash-checked official public inputs')
    fetch.add_argument('--data',required=True)
    launch = sub.add_parser('run',help='Explicitly execute frozen numerical preflight and phase')
    launch.add_argument('--work',required=True);launch.add_argument('--phase',choices=['tiny','development','confirmation'],required=True)
    launch.add_argument('--run-reviewed',action='store_true',required=True,
                        help='Acknowledge the frozen protocol, costs and one-use phase; no external approval file required')
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args);return 0
    if args.command == 'fetch-data': fetch_data(args);return 0
    return run(args)

if __name__ == '__main__':
    try: raise SystemExit(main())
    except BindingError as error: raise SystemExit(str(error))
