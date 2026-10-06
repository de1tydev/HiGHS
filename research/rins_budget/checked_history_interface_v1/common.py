"""Small sibling glue around the unchanged original-model validators."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent / 'current_scuc'))
from current_scuc import case_binding
from current_scuc.science import model, qa
from current_scuc.core.driver.primal_and_bound import unpack_expected

require = case_binding.require
read_json = case_binding.read
sha = case_binding.sha


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(payload) <= 1024**2, 'Metadata exceeds 1 MiB')
    with Path(path).open('xb') as out:
        out.write(payload)


def expected_model(path):
    return model.validate_model(unpack_expected(read_json(path)))


def read_values(path, names):
    """Native adapter's exact named-vector interchange; never round values."""
    values = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        require(len(fields) == 2 and fields[0] not in values, 'Malformed/duplicate point row')
        value = float(fields[1])
        require(math.isfinite(value), 'Nonfinite point')
        values[fields[0]] = value
    require(set(values) == set(names), 'Point does not cover exact original columns')
    return [values[name] for name in names]


def check_point(expected, values):
    """Original numerical matrix feasibility, not full SCUC/source/DC acceptance."""
    result = qa.check_primal(expected, values, tolerance=1e-5)
    result.pop('activities', None)
    integers = [j for j, kind in enumerate(expected['integrality']) if kind]
    valid_size = len(values) == expected['num_col']
    residual = max((abs(values[j] - round(values[j])) for j in integers), default=0.) if valid_size else math.inf
    result.update(integrality_checked=True, maximum_integrality_residual=residual if math.isfinite(residual) else None,
                  integrality_tolerance=1e-6, point_rounded=False,
                  acceptance_scope='complete_original_matrix_only', full_scuc_checked=False)
    result['passed'] = result['passed'] and residual <= 1e-6
    return result


def write_values(path, names, values):
    require(len(names) == len(values), 'Point size')
    with Path(path).open('x') as out:
        for name, value in zip(names, values):
            require(isinstance(name, str) and len(name.split()) == 1 and math.isfinite(value), 'Invalid named value')
            out.write(f'{name} {value:.17g}\n')


def checked_member(root, relative, wanted):
    root = Path(root).resolve()
    raw = Path(relative)
    require(not raw.is_absolute() and '..' not in raw.parts, 'Unsafe artifact locator')
    path = root / raw
    require(path.resolve() == path and path.is_file(), 'Missing/symlink artifact')
    require(all(not part.is_symlink() for part in [path, *path.parents] if part.is_relative_to(root)), 'Symlink ancestor')
    require(sha(path) == wanted, 'Changed artifact: ' + relative)
    return path
