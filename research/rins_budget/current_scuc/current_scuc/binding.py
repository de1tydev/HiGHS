"""Source-only local runtime contract; native qualification stays explicit."""
from __future__ import annotations
import os
from pathlib import Path
import re
import site
import sys
from . import case_binding as cb
from ._paths import ROOT, module as load

HERE = PACKAGE = ROOT
CORE = ROOT/'core'
FREEZE = ROOT/'SOURCE_MANIFEST.json'
PROTOCOL = ROOT/'PROTOCOL.json'
ContractError, require, sha, read = cb.ContractError, cb.require, cb.sha, cb.read


def write(path,value,*,fresh=False):
    return cb.write(path,value,fresh=fresh)


def source_only():
    require(__debug__ and sys.dont_write_bytecode,'Require assertions and Python -B')


def verify(pins):
    for path,digest in pins.items():
        require(re.fullmatch('[0-9a-f]{64}',digest) is not None and sha(path)==digest,'Changed artifact: '+str(path))


def source_snapshot():
    files={}
    for path in sorted(ROOT.rglob('*')):
        require(not path.is_symlink(),'Symlink in source package: '+str(path))
        require(path.name!='__pycache__' and path.suffix not in ('.pyc','.pyo'),'Bytecode in source package')
        if path.is_file(): files[str(path.relative_to(ROOT))]=sha(path)
    require(files and 'case_binding.py' in files and 'preparation.py' in files,'Incomplete local source package')
    return dict(schema='current-scuc-source-snapshot/v1',files_sha256=files)


def verify_source_snapshot(item):
    snapshot=read(cb.check_record(item))
    require(snapshot==source_snapshot(),'Local source package changed')
    return snapshot


def startup_directories():
    paths = [*site.getsitepackages(), str(ROOT.parent), *(p or os.getcwd() for p in sys.path)]
    return sorted({str(Path(p).resolve()) for p in paths if Path(p).is_dir()})


def configure(instance,runtime_manifest,out):
    """Write one hash-bound local driver config without loading numerical code."""
    from .runtime import load_runtime_config, loaded_python_identities
    out=Path(out).resolve()
    require(out.parent.is_dir(),'Runtime config parent must exist')
    cfg=dict(load_runtime_config(runtime_manifest))
    source=cb.record(instance); cb.check_record(source)
    snapshot_path=out.with_name(out.stem+'.source.json')
    cb.write(snapshot_path,source_snapshot())
    cfg.update(schema='current-scuc-runtime-binding/v1',phase='current',package=str(ROOT),
        inputs={'current':source},source_snapshot=cb.record(snapshot_path),
        source_manifest=cb.record(FREEZE),source_manifest_sha256=sha(FREEZE),
        python=str(Path(sys.executable).absolute()),python_prefix=str(Path(sys.prefix).resolve()),
        python_base_prefix=str(Path(sys.base_prefix).resolve()),
        numerical_lock=str(out.parent/'numerical.lock'),runtime_manifest=str(Path(runtime_manifest).resolve()),
        runtime_manifest_sha256=sha(runtime_manifest))
    verify_package_source(FREEZE,sha(FREEZE))
    cfg['startup_directories']=startup_directories()
    require(cfg['startup_directories'],'Missing interpreter startup directory authority')
    assert_no_startup_hooks(cfg['startup_directories'])
    cfg['python_distribution_files']=loaded_python_identities()
    cfg['runtime_pins']=dict(cfg.get('runtime_pins',{}))
    cfg['runtime_pins'].update({item['path']:item['sha256'] for item in cfg['python_distribution_files']})
    cfg['runtime_pins'][str(Path(cfg['python']).resolve())]=sha(cfg['python'])
    cfg['runtime_identity_sha256']=cb.identity(cfg)
    cb.write(out,cfg)
    return cfg


def config():
    path=os.environ.get('PRIMAL_CACHE_CONFIG')
    require(path is not None and os.environ.get('PRIMAL_CACHE_CONFIG_SHA256')==sha(path),'Current config must be explicitly pinned')
    value=read(path)
    require(value.get('schema')=='current-scuc-runtime-binding/v1','Wrong local runtime config schema')
    require(Path(value['package']).resolve()==PACKAGE,'Runtime package path changed')
    require(value.get('phase')=='current' and set(value.get('inputs',{}))=={'current'},'Only current input role permitted')
    cb.check_record(value['inputs']['current'])
    require(value.get('pristine_source_commit')==cb.COMMIT,'Runtime source commit changed')
    require(value['runtime_identity_sha256']==cb.identity({k:v for k,v in value.items() if k!='runtime_identity_sha256'}),'Runtime identity changed')
    require(sha(value['runtime_manifest'])==value['runtime_manifest_sha256'],'Native runtime manifest changed')
    from .runtime import load_runtime_config
    native=load_runtime_config(value['runtime_manifest'])
    for key in ('binary','library','extras','native_assess','pristine_source_commit'):
        require(value[key]==native[key],'Native runtime field changed: '+key)
    require(value['source_manifest_sha256']==value['source_manifest']['sha256'],'Source snapshot identity mismatch')
    return value


def assert_no_startup_hooks(directories):
    for directory in directories:
        root=Path(directory)
        if not root.exists():continue
        hooks=list(root.glob('*.pth'))+list(root.glob('sitecustomize*'))+list(root.glob('usercustomize*'))
        require(not hooks,'Startup hook requires a clean installation: '+str(hooks[0] if hooks else root))


def verify_freeze():
    source_only(); value=config()
    snapshot=verify_source_snapshot(value['source_snapshot'])
    verify_package_source(value['source_manifest']['path'],value['source_manifest_sha256'])
    verify(value['runtime_pins'])
    verify(value.get('runtime_library_pins',{}))
    verify(value.get('build_pins',{}))
    require(isinstance(value.get('startup_directories'),list) and value['startup_directories']
        and set(startup_directories())<=set(value['startup_directories']), 'Changed or missing startup directory authority')
    assert_no_startup_hooks(value['startup_directories'])
    require(Path(sys.executable).absolute()==Path(value['python']).absolute() and
        str(Path(sys.prefix).resolve())==value['python_prefix'] and
        str(Path(sys.base_prefix).resolve())==value['python_base_prefix'],'Wrong interpreter or virtual environment')
    return dict(schema='current-scuc-runtime-verification/v1',
        artifact_sha256={str(ROOT/k):v for k,v in snapshot['files_sha256'].items()},
        source_manifest_sha256=value['source_manifest_sha256'],native_runtime_manifest_sha256=value['runtime_manifest_sha256'])


def environment(out):
    value=config(); out=Path(out)
    for name in ('home','tmp','cache'):(out/'environment'/name).mkdir(parents=True,exist_ok=True)
    env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','TZ':'UTC','HOME':str(out/'environment/home'),
        'TMPDIR':str(out/'environment/tmp'),'XDG_CACHE_HOME':str(out/'environment/cache'),
        'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1',
        'PYTHONHASHSEED':'0','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1',
        'PYTHONPATH':str(ROOT.parent),'LD_LIBRARY_PATH':str(Path(value['library']).parent),
        'PRIMAL_CACHE_CONFIG':os.environ['PRIMAL_CACHE_CONFIG'],
        'PRIMAL_CACHE_CONFIG_SHA256':os.environ['PRIMAL_CACHE_CONFIG_SHA256'],
        'CURRENT_SCUC_RUNTIME_MANIFEST':value['runtime_manifest']}
    for name in ('HELDOUT_CASE_BINDING','HELDOUT_CASE_BINDING_SHA256'):
        if name in os.environ:env[name]=os.environ[name]
    return env


def fresh_directory(path):
    path=Path(path).absolute(); require(not path.exists() and not path.is_symlink(),'Fresh output required')
    require(not path.resolve().is_relative_to(PACKAGE),'Output must be outside source package')
    require(path.parent.is_dir(),'Output parent must exist');path.mkdir();return path.resolve()


def validate_source_reference(reference):
    """Local source references bind the source snapshot, never a remote archive."""
    value=config()
    require(type(reference) is dict and reference.get('source_manifest_sha256')==value['source_manifest_sha256'],
        'Source reference does not bind the current source snapshot')
    verify_source_snapshot(value['source_snapshot'])
    return reference


def verify_package_source(path,digest):
    """Validate the installed extraction manifest without executing its sources."""
    path=Path(path).resolve()
    require(path==FREEZE and sha(path)==digest,'Installed source manifest identity changed')
    manifest=read(path)
    require(manifest.get('schema')=='current-scuc-package-source/v1','Wrong package source manifest schema')
    files=manifest.get('files_sha256')
    require(isinstance(files,dict) and files,'Empty package source manifest')
    inventory=set()
    for relative,expected in files.items():
        require(type(relative) is str and relative and not Path(relative).is_absolute() and
            '..' not in Path(relative).parts and str(Path(relative))==relative,'Invalid package relative path')
        raw=ROOT/relative; item=raw.resolve()
        require(item.is_relative_to(ROOT) and item.is_file() and not raw.is_symlink(),'Invalid package source path')
        require(item!=path and sha(item)==expected,'Package source changed: '+relative)
        inventory.add(item)
    required={item.resolve() for item in ROOT.rglob('*.py')}
    require(required<=inventory,'Unbound executable package source')
    return dict(passed=True,source_manifest_sha256=digest,
        artifact_sha256={str(ROOT/k):v for k,v in files.items()})

verify_source_manifest=verify_package_source
