#!/usr/bin/env python3
"""Pinned stdlib-only exec shim; limit changes are confined to the native child."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time

CAP = 64 * 1024 ** 2
PYTHON_CAP = 512 * 1024 ** 2


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _absolute(path):
    value = Path(path)
    if not value.is_absolute() or '..' in value.parts:
        raise ValueError('native path must be absolute without parent traversal')
    return value


def _validate_argv(argv, solver=None):
    if not argv or not all(isinstance(arg, str) and arg and '\0' not in arg for arg in argv):
        raise ValueError('invalid native command')
    executable = _absolute(argv[0])
    if not executable.is_file() or executable.is_symlink():
        raise ValueError('native executable must be a pinned regular file')
    # Both supported pinned programs use absolute positional paths or CLI flags
    # followed by absolute paths; no shell or unknown relative operands.
    flags = {'--model_file', '--options_file', '--read_solution_file', '--solution_file'}
    numeric = {'--time_limit', '--random_seed'}
    index = 1
    seen, positional = set(), []
    while index < len(argv):
        arg = argv[index]
        if arg.startswith('--'):
            key, sep, value = arg.partition('=')
            if key not in flags | numeric:
                raise ValueError('unsupported native CLI argument')
            if key in seen:
                raise ValueError('duplicate native CLI argument')
            seen.add(key)
            if not sep:
                index += 1
                if index >= len(argv):
                    raise ValueError('native flag missing operand')
                value = argv[index]
            if key in flags:
                _absolute(value)
            elif key == '--random_seed':
                if value != '0':
                    raise ValueError('native random seed must stay zero')
            elif not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError('native time limit must be finite positive')
        else:
            _absolute(arg)
            positional.append(arg)
        index += 1
    if solver is True and (len(positional) != 1 or seen - {'--read_solution_file'} !=
                          {'--options_file', '--time_limit', '--random_seed', '--solution_file'}):
        raise ValueError('native solver command shape changed')
    if solver is False and (seen or len(positional) != 4):
        raise ValueError('native assessment command shape changed')
    return executable


def build_command(native_argv, *, cwd, receipt_path, executable_sha256,
                  python=sys.executable, solver=False, expected_library_path=None,
                  expected_library_sha256=None):
    argv = list(native_argv)
    executable = _validate_argv(argv, solver=solver)
    cwd, receipt = _absolute(cwd), _absolute(receipt_path)
    if not cwd.is_dir() or cwd.is_symlink() or receipt.parent != cwd:
        raise ValueError('native receipt/cwd must be the same real stage directory')
    if sha(executable) != executable_sha256:
        raise ValueError('pinned native executable changed')
    if (expected_library_path is None) != (expected_library_sha256 is None):
        raise ValueError('native library path/hash must be supplied together')
    if expected_library_path is not None:
        _absolute(expected_library_path)
        if sha(expected_library_path) != expected_library_sha256:
            raise ValueError('pinned native library changed')
    shim = Path(__file__).resolve()
    payload = dict(schema='native-limit-request/v2', argv=argv, cwd=str(cwd),
                   cwd_identity=[cwd.stat().st_dev, cwd.stat().st_ino],
                   receipt_path=str(receipt), executable_sha256=executable_sha256,
                   wrapper_path=str(shim), wrapper_sha256=sha(shim), cap_bytes=CAP,
                   solver=bool(solver), expected_library_path=str(expected_library_path)
                   if expected_library_path is not None else None,
                   expected_library_sha256=expected_library_sha256)
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    if len(encoded.encode()) > 32768:
        raise ValueError('native request too large')
    command = [str(_absolute(python)), '-B', '-s', str(shim), '--request', encoded]
    evidence = {**payload, 'wrapper_argv': command,
                'request_sha256': hashlib.sha256(encoded.encode()).hexdigest()}
    return command, evidence


def verify_receipt(path, evidence, *, process_receipt=None, expected_pid=None):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
        raise ValueError('native limit receipt is not bounded/regular')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        raw = stream.read(65537)
        after = os.fstat(stream.fileno())
    if (len(raw)>65536 or (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns) !=
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
        raise ValueError('native receipt changed during read')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate native receipt key')
            result[key]=value
        return result
    receipt = json.loads(raw,object_pairs_hook=unique)
    if receipt.get('schema') != 'native-limit-receipt/v2' or sha(__file__) != evidence['wrapper_sha256']:
        raise ValueError('native receipt schema/current wrapper mismatch')
    for key in ('argv', 'cwd', 'cwd_identity', 'wrapper_sha256', 'executable_sha256', 'request_sha256'):
        if receipt.get(key) != evidence[key]:
            raise ValueError('native receipt binding mismatch: ' + key)
    if (receipt.get('effective_rlimit_fsize') != [CAP, CAP] or
            receipt.get('effective_rlimit_core') != [0, 0] or
            receipt.get('sigxfsz_default') is not True or
            receipt.get('sigxfsz_unblocked') is not True or
            receipt.get('ld_debug_before_python') is not False or
            receipt.get('ld_debug_native') != ('libs' if evidence['solver'] else None)):
        raise ValueError('native limit receipt does not prove exact limits')
    if process_receipt is not None:
        reaped=process_receipt.get('reaped', [])
        if len(reaped)!=1 or process_receipt.get('exact_child_reaped') is not True:
            raise ValueError('native receipt requires exact single reaped child')
        if expected_pid is not None and expected_pid != reaped[0]['pid']:
            raise ValueError('conflicting native child PID evidence')
        expected_pid=reaped[0]['pid']
    if expected_pid is not None and receipt.get('pid') != expected_pid:
        raise ValueError('native receipt PID does not match reaped child')
    return receipt


@contextmanager
def native_output_guard():
    """Single-threaded blocking C-API scope; no Python artifact writes inside.

    Normal return restores the prospective 512-MiB Python policy. SIGXFSZ remains a
    terminating failure; an over-limit native call never resumes serialization.
    """
    before = resource.getrlimit(resource.RLIMIT_FSIZE)
    if before != (PYTHON_CAP, PYTHON_CAP):
        raise ValueError('native guard requires prospective 512-MiB Python file policy')
    handler = signal.getsignal(signal.SIGXFSZ)
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, [])
    core_before = resource.getrlimit(resource.RLIMIT_CORE)
    record = dict(schema='native-inprocess-limit/v2', before=list(before),
                  started_monotonic=time.monotonic(), restored=False)
    try:
        signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGXFSZ})
        resource.setrlimit(resource.RLIMIT_FSIZE, (CAP, before[1]))
        resource.setrlimit(resource.RLIMIT_CORE, (0, core_before[1]))
        effective = resource.getrlimit(resource.RLIMIT_FSIZE)
        if effective != (CAP, PYTHON_CAP):
            raise RuntimeError('native C-API file limit failed to apply')
        core_effective=resource.getrlimit(resource.RLIMIT_CORE)
        if core_effective[0] != 0:
            raise RuntimeError('native C-API core limit failed to apply')
        record.update(effective=list(effective), sigxfsz_default=True, sigxfsz_unblocked=True,
                      core_before=list(core_before),core_effective=list(core_effective))
        yield record
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, before)
        resource.setrlimit(resource.RLIMIT_CORE, core_before)
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        signal.signal(signal.SIGXFSZ, handler)
        if resource.getrlimit(resource.RLIMIT_FSIZE) != before:
            raise RuntimeError('native C-API limit restoration failed')
        record.update(restored=True, after=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
                      finished_monotonic=time.monotonic())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    raw = parser.parse_args().request
    if not sys.dont_write_bytecode or 'LD_DEBUG' in os.environ or len(raw.encode()) > 32768:
        raise ValueError('native shim requires -B and no Python-startup LD_DEBUG')
    request = json.loads(raw)
    executable = _validate_argv(request['argv'], solver=request['solver'])
    if request['schema'] != 'native-limit-request/v2' or request['cap_bytes'] != CAP:
        raise ValueError('wrong native limit request')
    if str(Path(__file__).resolve()) != request['wrapper_path'] or sha(__file__) != request['wrapper_sha256']:
        raise ValueError('native wrapper identity changed')
    if sha(executable) != request['executable_sha256']:
        raise ValueError('native executable identity changed')
    library = request['expected_library_path']
    if library is not None and sha(_absolute(library)) != request['expected_library_sha256']:
        raise ValueError('native library identity changed')
    cwd, receipt = _absolute(request['cwd']), _absolute(request['receipt_path'])
    if cwd.is_symlink() or receipt.parent != cwd:
        raise ValueError('native cwd/receipt identity invalid')
    if [cwd.stat().st_dev, cwd.stat().st_ino] != request['cwd_identity']:
        raise ValueError('native cwd identity changed')
    os.chdir(cwd)
    before = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (CAP, CAP))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGXFSZ})
    effective = resource.getrlimit(resource.RLIMIT_FSIZE)
    core = resource.getrlimit(resource.RLIMIT_CORE)
    if effective != (CAP, CAP) or core != (0, 0):
        raise RuntimeError('native limits not applied')
    env = os.environ.copy()
    if request['solver']:
        env['LD_DEBUG'] = 'libs'
    record = dict(schema='native-limit-receipt/v2', **{k: request[k] for k in
                  ('argv', 'cwd', 'cwd_identity', 'wrapper_path', 'wrapper_sha256', 'executable_sha256')},
                  request_sha256=hashlib.sha256(raw.encode()).hexdigest(), pid=os.getpid(),
                  before_rlimit_fsize=list(before), effective_rlimit_fsize=list(effective),
                  effective_rlimit_core=list(core), sigxfsz_default=signal.getsignal(signal.SIGXFSZ)==signal.SIG_DFL,
                  sigxfsz_unblocked=signal.SIGXFSZ not in signal.pthread_sigmask(signal.SIG_BLOCK, []),
                  ld_debug_before_python=False, ld_debug_native=env.get('LD_DEBUG'),
                  recorded_before_exec_monotonic=time.monotonic())
    data = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
    if len(data) > 65536:
        raise ValueError('native receipt byte limit')
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444), 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    dirfd = os.open(cwd, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)
    os.execve(str(executable), request['argv'], env)


if __name__ == '__main__':
    main()
