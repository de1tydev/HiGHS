"""Canonical local source and native-runtime identity resolution.

Historical names are attribution keys only. They never select an external
research checkout or supply a saved numerical input.
"""
from __future__ import annotations
import hashlib
import importlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def source_path(original):
    mapping = json.loads((ROOT / 'SOURCE_PATHS.json').read_text())
    relative = mapping.get(str(original), str(original))
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('Missing local package source: ' + relative)
    return path


def source_sha(original):
    path = source_path(original)
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text())
    relative = path.relative_to(ROOT).as_posix()
    expected = manifest['files_sha256'].get(relative)
    if expected is None or sha256(path) != expected:
        raise ValueError('Local source identity changed: ' + relative)
    return expected


def module(name, path):
    """Load one canonical package module, sharing its process-local state."""
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or path.suffix != '.py':
        raise ValueError('Module outside current_scuc: ' + str(path))
    source_sha(path.relative_to(ROOT).as_posix())
    dotted = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
    value = importlib.import_module('current_scuc.' + dotted)
    if Path(value.__file__).resolve() != path:
        raise ValueError('Canonical module collision: ' + name)
    return value


def _runtime_config():
    from . import binding
    return binding.config()


def runtime_path(relative):
    """Resolve a native guard/build artifact from the local runtime manifest."""
    from . import runtime
    return runtime.runtime_path(relative)


def runtime_sha(role):
    config = _runtime_config()
    keys = {'library': 'library_sha256', 'binary': 'binary_sha256',
            'native_assess': 'native_assess_sha256', 'extras': 'extras_sha256',
            'hconfig': 'hconfig_sha256', 'cmake_cache': 'cmake_cache_sha256'}
    if role not in keys or not config.get(keys[role]):
        raise ValueError('Missing validated native identity: ' + role)
    return config[keys[role]]
