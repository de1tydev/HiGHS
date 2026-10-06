#!/usr/bin/env python3
"""Refresh the local package source manifest after reviewed source edits."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1] / 'current_scuc'
files = sorted([*ROOT.rglob('*.py'), *(p for p in ROOT.glob('*.json') if p.name != 'SOURCE_MANIFEST.json')])
manifest = dict(schema='current-scuc-package-source/v1', files_sha256={
    path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})
(ROOT / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(hashlib.sha256((ROOT / 'SOURCE_MANIFEST.json').read_bytes()).hexdigest())
