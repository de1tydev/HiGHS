#!/usr/bin/env python3
"""Fresh runtime inspection, never an optimizer/model call. --startup is stdlib only."""
import argparse
import ctypes as C
import json
from pathlib import Path
import platform
import sys
import sysconfig
sys.path.insert(0, str(Path(__file__).resolve().parent))
from portable_runtime import BindingError, bindings, read_json, sha, verify, write_json

C_SYMBOLS = ('Highs_create', 'Highs_destroy', 'Highs_getSizeofHighsInt', 'Highs_version',
             'Highs_setBoolOptionValue', 'Highs_setStringOptionValue', 'Highs_readModel',
             'Highs_getNumCol', 'Highs_getNumRow', 'Highs_getNumNz', 'Highs_getHessianNumNz',
             'Highs_getInfinity', 'Highs_getLp', 'Highs_getColName', 'Highs_getRowName')

def startup():
    if sys.version_info < (3, 11): raise BindingError('Python 3.11 or newer required')
    if sys.platform != 'linux' or platform.libc_ver()[0] != 'glibc':
        raise BindingError('Only Linux/glibc is supported')
    executable = Path(sys.executable).absolute()
    venv = executable.parent.parent/'pyvenv.cfg'
    import site  # Under -S this reads stdlib definitions; site.main/startup hooks do not run.
    sites = []
    if venv.exists():
        configuration = dict(line.split('=', 1) for line in venv.read_text().splitlines() if '=' in line)
        configuration = {k.strip(): v.strip() for k, v in configuration.items()}
        if configuration.get('include-system-site-packages', '').lower() != 'false':
            raise BindingError('Virtual environment must disable system-site-packages')
        sites.extend(Path(p) for p in site.getsitepackages([str(executable.parent.parent)]))
    else:
        sites.extend(Path(p) for p in site.getsitepackages())
        sites.extend(Path(sysconfig.get_path(k)) for k in ('purelib', 'platlib'))
    paths = sorted(set(str(p.resolve()) for p in sites))
    startup_dirs = sorted(set(paths + [str(Path(p).resolve()) for p in sys.path[1:] if p and Path(p).is_dir()]))
    for path in sys.path:
        if path.endswith('.zip') and Path(path).exists(): raise BindingError('Zipped Python startup paths are unsupported')
    for directory in startup_dirs:
        root = Path(directory)
        if list(root.glob('*.pth')) or list(root.glob('sitecustomize*')) or list(root.glob('usercustomize*')):
            raise BindingError('Use a clean Python installation without startup hooks: ' + directory)
    installations = {}
    for package in ('numpy', 'scipy'):
        candidates = [Path(p)/package for p in paths if (Path(p)/package/'__init__.py').is_file()]
        if len(candidates) != 1: raise BindingError('Exactly one installed '+package+' package is required')
        root = candidates[0]
        metadata = sorted(root.parent.glob(package+'-*.dist-info'))
        if len(metadata) != 1: raise BindingError('Exactly one distribution metadata directory required: '+package)
        installations[package] = {'root': str(root), 'metadata': str(metadata[0])}
    return {'python_executable': str(executable), 'resolved_executable': str(executable.resolve()),
            'version': sys.version, 'base_prefix': sys.base_prefix, 'sites': paths,
            'startup_directories': startup_dirs, 'installations': installations,
            'pyvenv_cfg': str(venv) if venv.exists() else None,
            'os': platform.platform(), 'libc': list(platform.libc_ver()), 'machine': platform.machine()}

def symbol_provenance(library, names=C_SYMBOLS):
    class DlInfo(C.Structure):
        _fields_ = [('filename', C.c_char_p), ('base', C.c_void_p), ('symbol', C.c_char_p), ('address', C.c_void_p)]
    dladdr = C.CDLL(None).dladdr
    dladdr.restype = C.c_int
    dladdr.argtypes = [C.c_void_p, C.POINTER(DlInfo)]
    result = {}
    for name in names:
        info = DlInfo()
        if dladdr(C.cast(getattr(library, name), C.c_void_p), C.byref(info)) == 0 or not info.filename:
            raise BindingError('Cannot establish symbol provider: ' + name)
        path = Path(info.filename.decode()).resolve()
        result[name] = {'path': str(path), 'sha256': sha(path)}
    return result

def validate_abi_providers(size, providers, library, digest):
    if size != 4: raise BindingError('Only 32-bit HighsInt is supported')
    if set(providers) != set(C_SYMBOLS) or any(v != {'path': str(Path(library).resolve()), 'sha256': digest} for v in providers.values()):
        raise BindingError('Bound C API symbol provider differs from selected main DSO')

def inspect(here):
    value = bindings(here)
    verify(value['preparation_pins'])
    info = value['python_inspection']
    # This child starts normally with -B -s only after its installation was inspected
    # in a separate -I -S child and hooks were rejected by the launcher.
    import sqlite3
    import _sqlite3
    import numpy
    import scipy
    from scipy.sparse.linalg import splu
    from scipy.sparse import coo_matrix
    for name, module in (('numpy', numpy), ('scipy', scipy)):
        if Path(module.__file__).resolve().parent != Path(info['installations'][name]['root']).resolve():
            raise BindingError('Unexpected scientific package provider: ' + name)
    def version_tuple(version): return tuple(int(x) for x in version.split('.')[:2])
    if version_tuple(numpy.__version__) < (1,26) or version_tuple(scipy.__version__) < (1,11):
        raise BindingError('Requires NumPy >= 1.26 and SciPy >= 1.11')
    library = C.CDLL(value['library'])
    providers = symbol_provenance(library)
    # Provider check occurs before invoking even the scalar ABI query.
    validate_abi_providers(4, providers, value['library'], sha(value['library']))
    library.Highs_create.restype = C.c_void_p; library.Highs_create.argtypes = []
    library.Highs_destroy.restype = None; library.Highs_destroy.argtypes = [C.c_void_p]
    library.Highs_getSizeofHighsInt.restype = C.c_int32
    library.Highs_getSizeofHighsInt.argtypes = [C.c_void_p]
    handle = library.Highs_create()
    if not handle: raise BindingError('Highs_create failed')
    try: size = library.Highs_getSizeofHighsInt(handle)
    finally: library.Highs_destroy(handle)
    validate_abi_providers(size, providers, value['library'], sha(value['library']))
    pins = dict(value['preparation_pins'])
    for module in list(sys.modules.values()):
        for attribute in ('__file__', '__cached__'):
            path = getattr(module, attribute, None)
            if path and Path(path).is_file(): pins[str(Path(path).resolve())] = sha(path)
    native = {}
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/') and '.so' in fields[5]:
            path = Path(fields[5])
            if not path.is_file(): raise BindingError('Deleted/unreadable loaded native library')
            native[str(path.resolve())] = sha(path)
    pins.update(native)
    cpu = {}
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if ':' in line:
            key, val = [part.strip() for part in line.split(':', 1)]
            if key in ('vendor_id', 'model name', 'cpu family', 'model', 'stepping', 'flags') and key not in cpu: cpu[key] = val
    config = getattr(numpy.__config__, 'CONFIG', {})
    return {'artifact_sha256': pins, 'numpy_version': numpy.__version__, 'scipy_version': scipy.__version__, 'sqlite_version':sqlite3.sqlite_version,
            'python_version': sys.version, 'python_executable': sys.executable,
            'numpy_build_config': config, 'native_libraries': native, 'cpu': cpu,
            'os': platform.platform(), 'libc': list(platform.libc_ver()), 'highs_int_bytes': size,
            'loaded_symbol_provenance': providers, 'optimization_called': False,
            'model_generation_called': False, 'model_readback_called': False,
            'scope': 'Scientific imports and scalar C API ABI/provider check; no numerical model or optimizer'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.startup:
        print(json.dumps(startup(), allow_nan=False)); return
    if not args.output: parser.error('--output is required')
    write_json(args.output, inspect(Path(__file__).resolve().parent))

if __name__ == '__main__': main()
