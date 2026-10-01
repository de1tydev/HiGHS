"""POSIX child-specific CPU/RSS and process-group watchdog, without cumulative rusage."""
import os,signal,subprocess,time

def run_measured(command, *, stream, env, preexec_fn=None, timeout=660):
    start=time.monotonic()
    child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=env,
                           preexec_fn=preexec_fn,start_new_session=True)
    killed=False
    try:
        while True:
            pid,status,usage=os.wait4(child.pid,os.WNOHANG)
            if pid:break
            if time.monotonic()-start>=timeout:
                killed=True
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                pid,status,usage=os.wait4(child.pid,0)
                break
            time.sleep(.05)
    except BaseException:
        # Includes Python cancellation (KeyboardInterrupt), not uncatchable SIGKILL.
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:
            _,cleanup_status,_=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(cleanup_status)
        except ChildProcessError:pass
        raise
    child.returncode=os.waitstatus_to_exitcode(status)
    return {'solver_returncode':child.returncode,'hard_watchdog_killed':killed,
            'solver_process_wall_seconds':time.monotonic()-start,
            'solver_peak_rss_KiB':usage.ru_maxrss,
            'solver_user_cpu_seconds':usage.ru_utime,
            'solver_system_cpu_seconds':usage.ru_stime,
            'resource_accounting':'os.wait4 rusage of this solver child only; Linux RSS KiB'}
