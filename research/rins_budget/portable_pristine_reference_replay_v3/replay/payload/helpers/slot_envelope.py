#!/usr/bin/env python3
"""Authoritative whole-campaign watchdog; no numerical work in this process."""
import argparse
import ctypes
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

from contracts import read_json, sha, write_json

HERE = Path(__file__).resolve().parent
STOP_REASON = None
ACTIVE_RUNNER = None


def request_stop(signum, frame=None):
    global STOP_REASON
    STOP_REASON = STOP_REASON or "termination signal " + str(signum)
    child = ACTIVE_RUNNER
    if child is not None and child.returncode is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def become_subreaper():
    # If the runner dies, its sole active check becomes our child for exact
    # cleanup/reaping. This is a process-local Linux setting, not persistent.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "Cannot establish child cleanup owner")


def children_of(pid):
    path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        return [int(item) for item in path.read_text().split()]
    except FileNotFoundError:
        # Some supported Linux execution kernels omit this optional proc file.
        # Absence is not evidence that a process has no children.
        result=[]
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit(): continue
            try: raw=(entry/'stat').read_text()
            except FileNotFoundError: continue
            fields=raw[raw.rfind(')')+2:].split()
            if int(fields[1])==pid: result.append(int(entry.name))
        return result


def kill_group(pid, signum=signal.SIGKILL):
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        # A forked check may not have finished setsid yet. The PID still belongs
        # to our stopped runner, so kill it directly in that startup window.
        try:
            os.kill(pid, signum)
        except ProcessLookupError:
            pass


def stop_tree(child):
    """Stop new launches, kill the known check groups, then kill the runner."""
    try:
        os.kill(child.pid, signal.SIGSTOP)
        # Wait for the stopped state, without consuming the eventual exit reap.
        os.waitid(os.P_PID, child.pid, os.WSTOPPED | os.WEXITED | os.WNOWAIT)
    except ProcessLookupError:
        pass
    for pid in children_of(child.pid):
        kill_group(pid)
    kill_group(child.pid)


def reap_adopted_checks():
    """Only children of this dedicated envelope are eligible for cleanup."""
    records = []
    while True:
        for pid in children_of(os.getpid()):
            kill_group(pid)
        try: actual, status, usage = os.wait4(-1, 0)
        except ChildProcessError: break
        records.append(dict(pid=actual, returncode=os.waitstatus_to_exitcode(status),
            user_cpu_seconds=usage.ru_utime, system_cpu_seconds=usage.ru_stime,
            peak_rss_KiB=usage.ru_maxrss))
    return records


def supervise(command, environment, log_path, timeout=180., health_check=None):
    """The endpoint is after runner reap and any forced orphan cleanup."""
    global ACTIVE_RUNNER
    become_subreaper()
    child = None
    pidfd = None
    timed_out = False
    error = None
    health_error = None
    with Path(log_path).open("xb") as stream:
        start = time.monotonic()
        try:
            if STOP_REASON:
                raise InterruptedError(STOP_REASON)
            child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                     env=environment, start_new_session=True)
            ACTIVE_RUNNER = child
            if STOP_REASON:
                request_stop(signal.SIGTERM)
            pidfd = os.pidfd_open(child.pid)
            remaining = max(0., timeout - (time.monotonic() - start))
            ready = []
            while remaining > 0:
                if STOP_REASON:
                    stop_tree(child)
                    break
                if health_check is not None:
                    try: health_check()
                    except Exception as exc:
                        health_error=type(exc).__name__+': '+str(exc)
                        stop_tree(child)
                        break
                ready, _, _ = select.select([pidfd], [], [], min(remaining,.25))
                if ready: break
                remaining=max(0.,timeout-(time.monotonic()-start))
            if not ready and health_error is None and not STOP_REASON:
                timed_out = True
                stop_tree(child)
            actual, status, usage = os.wait4(child.pid, 0)
            assert actual == child.pid
            child.returncode = os.waitstatus_to_exitcode(status)
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
            if child is not None and child.returncode is None:
                stop_tree(child)
                _, status, usage = os.wait4(child.pid, 0)
                child.returncode = os.waitstatus_to_exitcode(status)
        finally:
            ACTIVE_RUNNER = None
            if pidfd is not None:
                os.close(pidfd)
        adopted = reap_adopted_checks()
        elapsed = time.monotonic() - start
    return dict(command=command, runner_returncode=child.returncode if child else None,
        runner_launched=child is not None, total_slot_elapsed_seconds=elapsed,
        total_slot_within_timeout=bool(elapsed <= timeout and not timed_out and health_error is None),
        health_check_error=health_error,
        hard_watchdog_killed=timed_out, interruption=STOP_REASON, error=error,
        adopted_checks_killed_and_reaped=adopted,
        boundary="Immediately before runner Popen through exact wait4 reap, including all campaign writes/fsync, shutdown, and any orphan cleanup",
        outer_receipt_publication="Observation-only receipt is published after the measured endpoint; no campaign work occurs after that endpoint")

