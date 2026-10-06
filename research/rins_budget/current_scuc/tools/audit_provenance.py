#!/usr/bin/env python3
"""Compare original attributed sources with this extraction without executing them."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(value).hexdigest()


def functions(source):
    result = {}
    tree = ast.parse(source)
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result[item.name] = dict(line=item.lineno, end_line=item.end_lineno,
                ast_sha256=digest(ast.dump(item, include_attributes=False).encode()),
                source_sha256=digest(ast.get_source_segment(source, item).encode()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--scope-map', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    package = root/'current_scuc'
    scope = json.loads(args.scope_map.read_text())
    originals = {row['path']: row for row in scope['records']}
    mapping = json.loads((package/'SOURCE_PATHS.json').read_text())
    rows = []
    for old, new in sorted(mapping.items()):
        before = args.source_root/old
        after = package/new
        if not before.is_file() or not after.is_file():
            raise ValueError('Missing mapped source: '+old+' -> '+new)
        original_hash = digest(before.read_bytes())
        if old in originals and original_hash != originals[old]['sha256']:
            raise ValueError('Original source differs from approved scope: '+old)
        old_functions, new_functions = functions(before.read_text()), functions(after.read_text())
        selected = []
        for name in sorted(old_functions.keys() & new_functions.keys()):
            first, second = old_functions[name], new_functions[name]
            selected.append(dict(name=name, original=first, portable=second,
                ast_unchanged=first['ast_sha256'] == second['ast_sha256']))
        rows.append(dict(original_path=old, original_sha256=original_hash,
            portable_path='current_scuc/'+new, portable_sha256=digest(after.read_bytes()),
            original_scope_category=originals.get(old,{}).get('category'),
            original_function_count=len(old_functions), portable_function_count=len(new_functions),
            matching_named_functions=selected, omitted_original_functions=sorted(old_functions.keys()-new_functions.keys()),
            new_function_names=sorted(new_functions.keys()-old_functions.keys())))
    document = dict(schema='current-scuc-source-provenance/v1',
        reference_source_manifest_sha256=scope['source_manifest_sha256'],
        original_source_bytes_verified_against_scope=True, native_execution_performed=False,
        purpose='Exact file/function evidence; changed ASTs require the accompanying binding review',
        records=rows)
    path = root/'SOURCE_PROVENANCE.json'
    path.write_text(json.dumps(document, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(records=len(rows), bytes=path.stat().st_size,
        functions=sum(len(row['matching_named_functions']) for row in rows),
        unchanged=sum(item['ast_unchanged'] for row in rows for item in row['matching_named_functions']))))


if __name__ == '__main__':
    main()
