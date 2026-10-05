#!/usr/bin/env python3
"""Verify this source-only package using the Python standard library."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent

def verify():
    manifest = json.loads((PACKAGE/'MANIFEST.json').read_text())
    actual = {str(p.relative_to(PACKAGE)) for p in PACKAGE.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != set(manifest['files']) | {'MANIFEST.json'}:
        raise ValueError('Missing or unexpected package files, including bytecode')
    for relative, expected in manifest['files'].items():
        path = PACKAGE/relative
        if path.is_symlink() or not path.resolve().is_relative_to(PACKAGE):
            raise ValueError('Package path is not a contained regular file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Package hash mismatch: '+relative)
    return {'passed':True,'files':len(manifest['files'])}

if __name__ == '__main__':
    print(json.dumps(verify()))
