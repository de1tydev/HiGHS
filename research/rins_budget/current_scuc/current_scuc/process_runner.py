"""New receipt adapter around the unchanged reviewed public cleanup envelope."""
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import time
from . import binding as b
from . import slot_envelope
from ._paths import ROOT

ADDRESS_SPACE_BYTES=7*1024**3
MEMORY_BYTES=6*1024**3
HEADROOM_BYTES=2*1024**3
PYTHON_FILE_LIMIT=512*1024**2

def apply_limits():
    # Process-local hard zero is inherited by every later exec/fork child.
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    b.require(resource.getrlimit(resource.RLIMIT_CORE)==(0,0),'Core-file limit was not disabled')
    resource.setrlimit(resource.RLIMIT_AS,(ADDRESS_SPACE_BYTES,ADDRESS_SPACE_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE,(PYTHON_FILE_LIMIT,PYTHON_FILE_LIMIT))
    b.require(resource.getrlimit(resource.RLIMIT_AS)==(ADDRESS_SPACE_BYTES,ADDRESS_SPACE_BYTES)
        and resource.getrlimit(resource.RLIMIT_FSIZE)==(PYTHON_FILE_LIMIT,PYTHON_FILE_LIMIT),
        'Process resource limit readback failed')

class WaitObserver:
    """Observe the public owner's exact wait4 calls, without changing cleanup."""
    def __init__(self): self.records=[]; self.echild=False
    def __getattr__(self,name): return getattr(os,name)
    def wait4(self,pid,options):
        try: result=os.wait4(pid,options)
        except ChildProcessError:
            if pid==-1:self.echild=True
            raise
        actual,status,usage=result
        if actual:self.records.append(dict(pid=actual,returncode=os.waitstatus_to_exitcode(status),user_cpu_seconds=usage.ru_utime,
            system_cpu_seconds=usage.ru_stime,peak_rss_KiB=usage.ru_maxrss))
        return result

def run(command,log,out,allocation,*,solver=False):
    b.require(type(allocation) in (int,float) and math.isfinite(allocation) and allocation>1,'No cleanup-reserved allocation')
    envelope=slot_envelope
    observer=WaitObserver();envelope.os=observer;envelope.STOP_REASON=None
    old={signum:signal.signal(signum,envelope.request_stop) for signum in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
    samples=[]
    def health():
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
        free=shutil.disk_usage(out).free
        todo=[os.getpid()];seen=set();rss=0
        while todo:
            pid=todo.pop()
            if pid in seen:continue
            seen.add(pid);todo.extend(envelope.children_of(pid))
            try:status=Path(f'/proc/{pid}/status').read_text()
            except FileNotFoundError:continue
            rss+=sum(int(line.split()[1])*1024 for line in status.splitlines() if line.startswith('VmRSS:'))
        samples.append((rss,available,free))
        b.require(rss<=MEMORY_BYTES and available>=HEADROOM_BYTES and free>=HEADROOM_BYTES,'RSS/headroom gate failed')
    try:
        env=b.environment(out)
        if solver:env['LD_DEBUG']='libs'
        health()
        result=envelope.supervise(command,env,log,timeout=allocation-1.,health_check=health)
    finally:
        for signum,handler in old.items():signal.signal(signum,handler)
    remaining=envelope.children_of(os.getpid())
    clean=bool(result['runner_launched'] and observer.echild and not remaining and not result['adopted_checks_killed_and_reaped'])
    elapsed=result['total_slot_elapsed_seconds']
    receipt=dict(result,returncode=result['runner_returncode'],process_wall_seconds=elapsed,
        resource_accounting_complete=clean and len(observer.records)==1,
        cleanup_verified=clean,wait4_echild=observer.echild,remaining_owned_pids=remaining,
        exact_child_reaped=bool(observer.records),reaped=observer.records,
        allocation_seconds=allocation,watchdog_trigger_seconds=allocation-1.,cleanup_reserve_seconds=1.,
        actual_within_allocation=elapsed<=allocation,interrupted=bool(result['interruption']),
        launch_or_measurement_error=result['error'],peak_rss_KiB=max((r['peak_rss_KiB'] for r in observer.records),default=0),
        parent_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        user_cpu_seconds=sum(r['user_cpu_seconds'] for r in observer.records),system_cpu_seconds=sum(r['system_cpu_seconds'] for r in observer.records),
        peak_sampled_tree_rss_bytes=max(s[0] for s in samples),minimum_sampled_memory_bytes=min(s[1] for s in samples),
        minimum_sampled_disk_bytes=min(s[2] for s in samples),source_envelope_sha256=b.sha(ROOT/'slot_envelope.py'),
        cpu_scope='wait4 child-subtree cumulative usage; outer and stage usage must never be summed',
        parent_rss_scope='This process cumulative ru_maxrss high-water mark, not incremental per-call RSS')
    return receipt

def require_clean(receipt,*,allowed_returns=(0,)):
    b.require(receipt.get('returncode') in allowed_returns and receipt.get('resource_accounting_complete') is True
        and receipt.get('cleanup_verified') is True and receipt.get('wait4_echild') is True and not receipt.get('remaining_owned_pids')
        and not receipt.get('hard_watchdog_killed') and not receipt.get('interrupted') and not receipt.get('error')
        and not receipt.get('health_check_error') and receipt.get('actual_within_allocation') is True,'Abnormal or uncontained process')
