"""Consumer-local bindings to the preserved early-integer method."""
from pathlib import Path
import resource
import shutil
import sys
import time
from contracts import (ContractError,sha,read_json,write_json,verify,module,finite,BINARY,LIBRARY,
    GENERATOR,CHECKER,EXPORTER,runtime_manifest,MEMORY_BYTES,MIP_SCOPE,TARGET,SOLVER_BUDGET,MIP_GRACE)
from portable_runtime import bindings,minimal_environment

HERE=Path(__file__).resolve().parent
DRIVER=HERE
HELPERS=HERE.parent/'helpers'
BINDINGS=bindings(HERE)
PYTHON=BINDINGS['python'] if BINDINGS else sys.executable
TINY=HERE/'tiny_triangle.json'
RESERVE_BYTES=2*1024**3

def health():
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
    free=shutil.disk_usage(HERE).free
    if available<RESERVE_BYTES or free<RESERVE_BYTES:raise ContractError('Sampled 2 GiB memory/disk availability guard failed')
    return dict(available_memory_bytes=available,free_disk_bytes=free,guard_bytes=RESERVE_BYTES)

def environment():return minimal_environment(HERE)

def limit():
    resource.setrlimit(resource.RLIMIT_AS,(MEMORY_BYTES,MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**3,4*1024**3))

def execute(command,log,timeout,*,solver=False):
    health();measure=module(HELPERS/'process_measure.py','portable_early_process_measure');env=environment()
    if solver:env['LD_DEBUG']='libs'
    started=time.monotonic()
    try:
        with Path(log).open('x') as stream:
            result=measure.run_measured(command,stream=stream,env=env,preexec_fn=limit,timeout=timeout)
    except BaseException as exc:
        return dict(returncode=None,hard_watchdog_killed=False,process_wall_seconds=time.monotonic()-started,
            interrupted=isinstance(exc,(KeyboardInterrupt,SystemExit)),launch_or_measurement_error=type(exc).__name__+': '+str(exc))
    return {k.removeprefix('solver_'):v for k,v in result.items()}

def verify_trial():
    """Mechanical local provenance check; no approval service or historical receipt."""
    return runtime_manifest()
