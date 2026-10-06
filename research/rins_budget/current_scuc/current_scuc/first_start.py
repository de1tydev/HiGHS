"""Source-only complete prefix family; never import diagnostic state or points.

Only the four reviewed source theorem/enumeration/append definitions are loaded
from the pinned complete-family source. Its module imports, prepare, and retained
upper routines are neither compiled nor executed.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import ast
import copy
from fractions import Fraction as F
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from current_scuc.common import ROOT, require

SOURCE_RELATIVE = 'science/first_start_cuts.py'
SOURCE_SHA256 = source_sha('first-start-complete-family-v1/cuts.py')
PROOF_RELATIVE = 'first-start-cut-proof-v1/MANIFEST.json'
PROOF_SHA256 = 'e9f2619089f65a6b3faf559a6d66b6ca760676d7461c7f2b7b480bc48255183a'
FUNCTIONS = ('eligible_units', 'select', 'source_guards', 'append_checked')
SCHEMA = 'source-complete-first-start-family/v1'
import current_scuc.heldout as heldout
HOURS = 36


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def source_functions(model):
    path = ROOT / SOURCE_RELATIVE
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, 'Complete-family source changed')
    tree = ast.parse(raw, filename=str(path))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    require(tuple(node.name for node in selected) == FUNCTIONS, 'Complete-family definition inventory')
    namespace = dict(F=F, math=math, np=np, require=require, dependencies=lambda: (model, None))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in FUNCTIONS})


def rows(family):
    result = []
    for item in family['units']:
        for t in range(family['hours']):
            result.append(dict(unit=item['unit'], prefix_end=t, C_hex=item['C_hex'],
                               C_exact=item['C_exact'], nonzeros=t+2))
    return result


def install(expected, metadata, original, source, model):
    """Append exactly once to the empty fresh base, before any LP is passed."""
    require('first_start_family' not in metadata and not metadata['lineage'], 'First-start family already installed or network prefix nonempty')
    require(not any(name.startswith('first_start_') for name in expected['row_names']), 'Duplicate first-start row family')
    functions = source_functions(model)
    guards = functions.source_guards(source, expected, original)
    inventory, zero_certificate = heldout.certify_omissions(source, original, expected, model,
        production=metadata['full_scope']['production_scope'])
    selected = heldout.zero_cost().positive_rows(source)
    if metadata['full_scope']['production_scope']:
        heldout.check_selected(selected, metadata['hours'])
    strengthened = functions.append_checked(expected, selected)
    family = dict(schema=SCHEMA, source_sha256=metadata['source_identity'],
        source_object_sha256=metadata['full_scope']['source_object_sha256'],
        implementation_sha256=SOURCE_SHA256, proof_manifest_sha256=PROOF_SHA256,
        row_start=expected['num_row'], row_count=len(selected), nonzeros=sum(r['nonzeros'] for r in selected),
        hours=metadata['hours'], production=metadata['full_scope']['production_scope'],
        units=[{key: r[key] for key in ('unit', 'C_hex', 'C_exact')} for r in selected if r['prefix_end'] == 0],
        source_guards=guards, zero_new_columns=True, selection_uses_point=False,
        logical_first_start_inventory=inventory, zero_omission_certificate=zero_certificate,
        amendment_proposal_sha256=heldout.zero_cost().PROPOSAL_SHA,
        amendment_manifest_sha256=heldout.zero_cost().MANIFEST_SHA)
    family['identity_sha256'] = identity(family)
    meta = copy.deepcopy(metadata)
    meta.update(first_start_family=family, fixed_family_nnz=family['nonzeros'],
                base_row_count=strengthened['num_row'])
    validate(strengthened, family, model)
    if family['production']:
        heldout.check_shape(strengthened, 'projected_first_start')
    return strengthened, meta


def validate(expected, family, model, *, canonical=False):
    """Verify every literal family row at its permanent base position."""
    require(family['schema'] == SCHEMA and family['identity_sha256'] ==
            identity({k: v for k, v in family.items() if k != 'identity_sha256'}), 'First-start family identity drift')
    require(family['implementation_sha256'] == SOURCE_SHA256 and family['proof_manifest_sha256'] == PROOF_SHA256,
            'First-start proof/source identity drift')
    require(type(family['hours']) is int and family['hours'] > 0 and
            type(family['row_start']) is int and family['row_start'] >= 0, 'First-start row range')
    selected = rows(family)
    require(len(selected) == family['row_count'] and sum(r['nonzeros'] for r in selected) == family['nonzeros'],
            'First-start family inventory drift')
    require(len({u['unit'] for u in family['units']}) == len(family['units']), 'Duplicate first-start unit')
    if family['production']:
        heldout.check_family(family)
    start, end = family['row_start'], family['row_start'] + family['row_count']
    require(end <= expected['num_row'], 'First-start rows missing')
    names = [f"first_start_{r['unit']}_{r['prefix_end']}" for r in selected]
    if canonical:
        require(expected['row_names'] == [f'R{i}' for i in range(expected['num_row'])], 'Canonical row names changed')
    else:
        require(expected['row_names'][start:end] == names and
                [n for n in expected['row_names'] if n.startswith('first_start_')] == names,
                'First-start family missing, repeated, reordered, or moved')
    require(np.all(expected['row_lower'][start:end] == 0.) and
            np.all(expected['row_upper'][start:end] == math.inf), 'First-start bounds changed')
    index = {name: j for j, name in enumerate(expected['col_names'])}
    block = model.matrix(expected)[start:end, :].tocsr()
    require(block.nnz == family['nonzeros'], 'First-start nonzero count changed')
    for i, row in enumerate(selected):
        g, t, cost = row['unit'], row['prefix_end'], float.fromhex(row['C_hex'])
        require(F(cost) == F(*map(int, row['C_exact'])) and cost > 0., 'Inexact first-start coefficient')
        terms = sorted([(index[f'u_{g}_{t}'], -cost)] + [(index[f'sc_{g}_{s}'], 1.) for s in range(t+1)])
        a, b = block.indptr[i:i+2]
        require(block.indices[a:b].tolist() == [j for j, v in terms] and
                block.data[a:b].tobytes() == np.asarray([v for j, v in terms], dtype=np.float64).tobytes(),
                'Literal first-start row changed')
    return dict(passed=True, identity_sha256=family['identity_sha256'], rows=len(selected), nonzeros=block.nnz,
                row_start=start, row_end=end, zero_new_columns=True)


def check_point(expected, family, point, *, tolerance):
    """Exact added-row carry check on unmodified binary64 coordinates."""
    require(np.asarray(point).dtype == np.float64 and len(point) == expected['num_col'] and np.isfinite(point).all(),
            'Invalid first-start carry point')
    tol = F(tolerance)
    require(0 <= tol <= F(1, 1000000), 'First-start carry tolerance enlarged')
    index = {name: j for j, name in enumerate(expected['col_names'])}
    maximum, count = F(0), 0
    for unit in family['units']:
        g, cost = unit['unit'], F(*map(int, unit['C_exact']))
        total = F(0)
        for t in range(family['hours']):
            total += F(float(point[index[f'sc_{g}_{t}']]))
            activity = total - cost*F(float(point[index[f'u_{g}_{t}']]))
            maximum = max(maximum, -activity)
            count += 1
    require(count == family['row_count'] and maximum <= tol, 'Current point violates complete first-start family')
    return dict(passed=True, rows_checked=count, identity_sha256=family['identity_sha256'],
                maximum_violation_exact=[str(maximum.numerator), str(maximum.denominator)],
                tolerance_exact=[str(tol.numerator), str(tol.denominator)], point_rounded=False)
