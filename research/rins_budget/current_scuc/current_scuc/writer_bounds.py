"""Pure, pre-write accounting for the pinned adaptive integer serializers.

This module opens no output, imports no numerical library, and makes no native
call.  A dimension formula is deliberately insufficient for MPS admission:
canonical_mps_reservation checks the actual view and CSC arrays, formats every
planned record, and binds its byte count and digest to the pinned writer.  Call
verify_written_mps after that writer, before native readback or result admission.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

import hashlib
import json
import math
import numbers
import operator
from pathlib import Path
import re
import stat
import struct

ROOT = PACKAGE_ROOT
STATE_LIMIT = 128 * 1024**2
NATIVE_FILE_LIMIT = 64 * 1024**2
MAX_COLUMNS, MAX_ROWS, MAX_NONZEROS, MAX_BINARIES = 142094, 164080, 1756901, 28080
import current_scuc.heldout as heldout
MAX_COLUMN_BYTES, MAX_ROW_BYTES, MAX_FINITE_17G_BYTES = 19, 7, 24
EXPORTER_RELATIVE = 'core/canonical_mps_export/export_v2.py'
EXPORTER_SHA256 = source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py')
PINS = {
    EXPORTER_RELATIVE: EXPORTER_SHA256,
    'storage_budget.py': source_sha('stage-persistence-v3/storage_budget.py'),
    'projected-start-containment-v3/native_assess.cpp': 'b7cd24d5852080cde20e2d0e269783090bfc004fa2f82fb30f92c9b3ecc73d4a',
    'pristine-source/highs/io/HighsIO.cpp': '5ee0815ae7f7eb6900ffd1b5f250a0efe9aa14538372949a838e4e26ea4f38e9',
    'pristine-source/highs/lp_data/HighsModelUtils.cpp': '584f18dee538ffcc779d9f5924d27ec40145be54304b4e38e8fdabf4936347ae',
    'pristine-source/highs/lp_data/HighsLpUtils.cpp': '5558ae4b4bbaa28200f39087b153aede08ae1cf5962f61ac09fce1b6755e2a82',
}
RECORD_LIMITS = dict(matrix=59, objective=55, row=12, rhs=44, bound=56, marker=35)
RESERVED = {'OBJ', 'RHS1', 'BND1', 'NAME', 'ROWS', 'COLUMNS', 'RHS', 'BOUNDS', 'ENDATA', 'MARKER'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _pin(relative, path=None):
    require(sha256((runtime_path(relative) if relative.startswith(('pristine-source/', 'projected-start-containment-v3/')) else ROOT / relative) if path is None else path) == PINS[relative],
            'Serializer source changed: ' + relative)


def _integer(value, label):
    require(not isinstance(value, bool), 'Boolean ' + label)
    try:
        result = operator.index(value)
    except TypeError as error:
        raise ValueError('Noninteger ' + label) from error
    require(0 <= result < 2**31, 'Invalid 32-bit ' + label)
    return result


def _dimensions(n, m, nz):
    n, m, nz = (_integer(v, k) for v, k in ((n, 'columns'), (m, 'rows'), (nz, 'nonzeros')))
    require(0 < n <= MAX_COLUMNS and 0 < m <= MAX_ROWS and 0 < nz <= MAX_NONZEROS,
            'Adaptive native output dimension ceiling')
    return n, m, nz


def _number(value, label, *, finite=True):
    require(isinstance(value, numbers.Real) and not isinstance(value, bool), 'Nonnumeric ' + label)
    result = float(value)
    require(not math.isnan(result) and (not finite or math.isfinite(result)), 'Nonfinite ' + label)
    return result


def finite_17g(value):
    """Validate the ACTUAL formatting operand, ASCII size, and binary64 roundtrip.

    A finite binary64 .17g value needs at most sign + digit + dot + 16 digits
    + e + exponent sign + three exponent digits = 24 bytes.  Fixed notation
    has no longer representation under general-format's exponent thresholds.
    Every actual operand is checked as well; the proof is not assumed from n.
    """
    actual = _number(value, '.17g value')
    text = format(value, '.17g')
    require(re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?(?:e[+-][0-9]+)?', text) is not None,
            'Unsupported .17g representation')
    require(len(text.encode('ascii')) <= MAX_FINITE_17G_BYTES, 'Finite .17g byte ceiling')
    require(struct.pack('>d', float(text)) == struct.pack('>d', actual), '.17g bit roundtrip changed')
    return text


def _same_number(left, right, label):
    a, b = _number(left, label, finite=False), _number(right, label, finite=False)
    require(struct.pack('>d', a) == struct.pack('>d', b), 'Writer/canonical mismatch: ' + label)


def _names(expected):
    n, m, _ = _dimensions(expected['num_col'], expected['num_row'], expected['num_nz'])
    names, rows = expected['col_names'], expected['row_names']
    require(len(names) == n and len(rows) == m, 'Incomplete writer names')
    require(len(set(names)) == n, 'Duplicate writer column name')
    for name in names:
        require(type(name) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,18}', name) is not None,
                'Unsupported or overlong ASCII column name')
        require(name not in RESERVED and re.fullmatch(r'R[0-9]+|MARK[0-9]+', name) is None,
                'Column name collides with serializer namespace')
    require(all(type(name) is str and name == f'R{i}' and len(name) <= MAX_ROW_BYTES
                for i, name in enumerate(rows)), 'Noncanonical or overlong row names')


def record_bound(n, m, nz, b):
    """Analytical envelope only; never a substitute for actual-input admission.

    Literal prefixes/suffixes in pinned write_model give matrix/objective/row/
    RHS/bound/marker limits 59/55/12/44/56/35.  Every binary has one bound;
    each continuous column has at most two.  At most two markers per binary
    run, hence <=2b+1; there are fewer than 100000 markers (five digits).
    Fixed section records occupy 63 bytes, conservatively reserved as 128.
    """
    n, m, nz = _dimensions(n, m, nz)
    b = _integer(b, 'binaries')
    require(b <= min(n, MAX_BINARIES), 'Adaptive binary inventory ceiling')
    return 59*nz + 55*n + 56*m + 56*(2*n-b) + 35*(2*b+1) + 128


def _fixed_family(family, canonical):
    """Only literal 1/-C prefix records qualify for the additive reservation."""
    if family is None:
        return None
    body = {k: v for k, v in family.items() if k != 'identity_sha256'}
    require(family['schema'] == 'source-complete-first-start-family/v1' and
            hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            == family['identity_sha256'], 'Fixed-family writer identity')
    start, count, hours = family['row_start'], family['row_count'], family['hours']
    require(type(start) is int and type(count) is int and type(hours) is int and
            start >= 0 and count >= 0 and hours > 0 and start + count <= canonical['num_row'], 'Fixed-family writer range')
    rows, roles, ceiling = [], {}, 0
    for unit in family['units']:
        name, cost = unit['unit'], float.fromhex(unit['C_hex'])
        require(math.isfinite(cost) and cost > 0 and
                list(map(str, cost.as_integer_ratio())) == unit['C_exact'], 'Fixed-family writer cold coefficient')
        for t in range(hours):
            rows.append((name, t, cost))
            roles[f'u_{name}_{t}'] = ('u', name, t)
            roles[f'sc_{name}_{t}'] = ('sc', name, t)
            ceiling += 12 + len(f'    u_{name}_{t}  ') + MAX_ROW_BYTES + 2 + len(finite_17g(-cost)) + 1
            ceiling += sum(len(f'    sc_{name}_{s}  ') + MAX_ROW_BYTES + 2 + 1 + 1 for s in range(t+1))
    nnz = sum(t+2 for name, t, cost in rows)
    require(len(rows) == count and nnz == family['nonzeros'] and len({u['unit'] for u in family['units']}) == len(family['units']),
            'Fixed-family writer inventory')
    if family['production']:
        heldout.check_family(family)
        heldout.check_family_bytes(ceiling)
    return dict(start=start, end=start+count, rows=rows, roles=roles, count=count, nonzeros=nnz,
                bound=ceiling, exact_bytes=0, matrix_records=0, row_records=0, identity_sha256=family['identity_sha256'])


def canonical_mps_reservation(view, canonical, *, exporter_path=None, first_start_family=None):
    """Prove all records before writing; return an exact plan and reservation.

    view and canonical must be the same objects passed to pinned write_model.
    Keep their arrays immutable between this call and writing, then call
    verify_written_mps.  Old admitted coarse reservations are never reduced.
    """
    _pin(EXPORTER_RELATIVE, exporter_path)
    _pin('storage_budget.py')
    n, m, nz = _dimensions(canonical['num_col'], canonical['num_row'], canonical['num_nz'])
    fixed = _fixed_family(first_start_family, canonical)
    _names(canonical)
    require(canonical['sense'] == 1 and canonical['offset'] == 0, 'Unsupported canonical objective')
    require(list(view.names) == list(canonical['col_names']), 'Writer/canonical column names differ')
    for field in ('lb', 'ub', 'obj', 'binary'):
        require(len(getattr(view, field)) == n, 'Incomplete writer ' + field)
    require(len(view.sense) == len(view.rhs) == m and len(view.val) == nz, 'Incomplete writer row/matrix inventory')
    for field, length in (('col_lower', n), ('col_upper', n), ('col_cost', n), ('integrality', n),
                          ('row_lower', m), ('row_upper', m), ('a_start', n+1), ('a_index', nz), ('a_value', nz)):
        require(len(canonical[field]) == length, 'Incomplete canonical ' + field)
    starts = [_integer(v, 'CSC start') for v in canonical['a_start']]
    require(starts[0] == 0 and starts[-1] == nz and all(a <= b for a, b in zip(starts, starts[1:])),
            'Invalid CSC endpoints')
    counts = {kind: dict(records=0, bytes=0, max_record_bytes=0) for kind in (*RECORD_LIMITS, 'fixed')}
    digest = hashlib.sha256()
    def emit(kind, text):
        raw = text.encode('ascii')
        row = counts[kind]
        require(kind == 'fixed' or len(raw) <= RECORD_LIMITS[kind], 'Record byte ceiling: ' + kind)
        row['records'] += text.count('\n')
        row['bytes'] += len(raw)
        row['max_record_bytes'] = max(row['max_record_bytes'], len(raw))
        digest.update(raw)
    emit('fixed', 'NAME          SCUCBENCH\nROWS\n N  OBJ\n')
    for i, sense in enumerate(view.sense):
        require(sense in ('E', 'L', 'G'), 'Unsupported row sense')
        rhs = _number(view.rhs[i], 'RHS')
        lo, hi = (rhs if sense != 'L' else -math.inf), (rhs if sense != 'G' else math.inf)
        _same_number(lo, canonical['row_lower'][i], 'row lower')
        _same_number(hi, canonical['row_upper'][i], 'row upper')
        finite_17g(view.rhs[i])
        row_text = f' {sense}  R{i}\n'
        if fixed is not None and fixed['start'] <= i < fixed['end']:
            require(sense == 'G' and rhs == 0., 'Fixed-family writer row changed')
            fixed['row_records'] += 1
            fixed['exact_bytes'] += len(row_text)
        emit('row', row_text)
    emit('fixed', 'COLUMNS\n')
    isint, marker, binaries = False, 0, 0
    for j, name in enumerate(view.names):
        # numpy.bool_ is intentionally supported without importing numpy.
        bit = view.binary[j]
        require(type(bit) is bool or (type(bit).__module__ == 'numpy' and type(bit).__name__ == 'bool_'),
                'Unsupported binary marker')
        integral = _integer(canonical['integrality'][j], 'integrality')
        require(integral in (0, 1) and int(bit) == integral, 'Writer/canonical integrality differs')
        binaries += integral
        for writer_field, field in (('lb', 'col_lower'), ('ub', 'col_upper'), ('obj', 'col_cost')):
            _same_number(getattr(view, writer_field)[j], canonical[field][j], field)
        lo, up = _number(view.lb[j], 'column lower', finite=False), _number(view.ub[j], 'column upper', finite=False)
        require(lo <= up and lo != math.inf and up != -math.inf, 'Invalid column bounds')
        require(not bit or (lo, up) in ((0., 1.), (0., 0.), (1., 1.)), 'Unsupported binary bounds')
        if bit != isint:
            isint = bool(bit)
            emit('marker', f"    MARK{marker}  'MARKER'  '{'INTORG' if isint else 'INTEND'}'\n")
            marker += 1
        emit('objective', f'    {name}  OBJ  {finite_17g(view.obj[j])}\n')
        previous = -1
        for z in range(starts[j], starts[j+1]):
            row = _integer(canonical['a_index'][z], 'CSC row')
            require(previous < row < m, 'Unsorted, duplicate or out-of-range CSC row')
            previous = row
            value = canonical['a_value'][z]
            require(_number(value, 'matrix coefficient') != 0, 'Zero matrix coefficient')
            matrix_text = f'    {name}  R{row}  {finite_17g(value)}\n'
            if fixed is not None and fixed['start'] <= row < fixed['end']:
                unit, end, cost = fixed['rows'][row-fixed['start']]
                role = fixed['roles'].get(name)
                require(role is not None and role[1] == unit and
                        ((role[0] == 'u' and role[2] == end and value == -cost) or
                         (role[0] == 'sc' and role[2] <= end and value == 1.)), 'Fixed-family writer literal term changed')
                fixed['matrix_records'] += 1
                fixed['exact_bytes'] += len(matrix_text)
            emit('matrix', matrix_text)
    if isint:
        emit('marker', f"    MARK{marker}  'MARKER'  'INTEND'\n")
    emit('fixed', 'RHS\n')
    for i, value in enumerate(view.rhs):
        if value:
            emit('rhs', f'    RHS1  R{i}  {finite_17g(value)}\n')
    emit('fixed', 'BOUNDS\n')
    for j, name in enumerate(view.names):
        lo, up = view.lb[j], view.ub[j]
        if lo == up:
            emit('bound', f' FX BND1  {name}  {finite_17g(lo)}\n')
        elif view.binary[j]:
            emit('bound', f' BV BND1  {name}\n')
        else:
            if lo == -math.inf:
                emit('bound', f' MI BND1  {name}\n')
            elif lo != 0:
                emit('bound', f' LO BND1  {name}  {finite_17g(lo)}\n')
            if up != math.inf:
                emit('bound', f' UP BND1  {name}  {finite_17g(up)}\n')
    emit('fixed', 'ENDATA\n')
    analytical = record_bound(n, m, nz, binaries)
    require(counts['matrix']['records'] == nz and counts['objective']['records'] == n and
            counts['row']['records'] == m and counts['rhs']['records'] <= m and
            counts['bound']['records'] <= 2*n-binaries and counts['marker']['records'] <= 2*binaries+1 and
            counts['fixed']['bytes'] <= 128, 'Canonical record inventory ceiling')
    exact = sum(item['bytes'] for item in counts.values())
    inventory_bound = sum(counts[k]['records'] * limit for k, limit in RECORD_LIMITS.items()) + 128
    additive = None
    if fixed is not None:
        require(fixed['row_records'] == fixed['count'] and fixed['matrix_records'] == fixed['nonzeros'] and
                fixed['exact_bytes'] <= fixed['bound'], 'Fixed-family writer complete inventory')
        inherited = record_bound(n, m-fixed['count'], nz-fixed['nonzeros'], binaries)
        analytical = inherited + fixed['bound']
        inventory_bound -= fixed['count']*RECORD_LIMITS['row'] + fixed['nonzeros']*RECORD_LIMITS['matrix']
        inventory_bound += fixed['exact_bytes']
        additive = dict(identity_sha256=fixed['identity_sha256'], rows=fixed['count'], nonzeros=fixed['nonzeros'],
                        inherited_record_bound_bytes=inherited, family_bound_bytes=fixed['bound'],
                        family_exact_planned_bytes=fixed['exact_bytes'], combined_bound_bytes=analytical)
    require(exact <= inventory_bound <= analytical <= STATE_LIMIT, 'Canonical MPS proven byte ceiling')
    coarse = 64*(nz+4*n+2*m+10)
    reservation = max(coarse, exact) if coarse <= STATE_LIMIT else analytical
    if fixed is not None:
        prior_coarse = 64*(nz-fixed['nonzeros']+4*n+2*(m-fixed['count'])+10)
        prior_reservation = prior_coarse if prior_coarse <= STATE_LIMIT else additive['inherited_record_bound_bytes']
        reservation = max(reservation, prior_reservation)
        additive.update(prior_coarse_bound_bytes=prior_coarse,
                        prior_reservation_bytes=prior_reservation,
                        prior_reservation_preserved=True)
    require(reservation <= STATE_LIMIT, 'Canonical MPS reservation ceiling')
    return dict(schema='adaptive-canonical-mps-reservation/v1', columns=n, rows=m, nonzeros=nz, binaries=binaries,
                exporter_sha256=EXPORTER_SHA256, exact_planned_bytes=exact, planned_sha256=digest.hexdigest(),
                records=counts, record_limits=dict(RECORD_LIMITS), inventory_bound_bytes=inventory_bound,
                analytical_bound_bytes=analytical, coarse_bound_bytes=coarse, reservation_bytes=reservation,
                fixed_family_additive_proof=additive,
                mps_cap_bytes=STATE_LIMIT, prior_coarse_reservation_preserved=coarse <= STATE_LIMIT,
                reservation_basis='prior coarse bound retained' if coarse <= STATE_LIMIT else 'validated adaptive canonical record bound')


def verify_written_mps(path, receipt):
    """Check bytes AND complete serialized contents before any native call."""
    path = Path(path)
    require(receipt['schema'] == 'adaptive-canonical-mps-reservation/v1' and
            receipt['exporter_sha256'] == EXPORTER_SHA256, 'Wrong MPS reservation receipt')
    _pin(EXPORTER_RELATIVE)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), 'MPS output is not a regular file')
    require(info.st_size == receipt['exact_planned_bytes'] <= receipt['reservation_bytes'] <= STATE_LIMIT,
            'MPS actual size differs from pre-write plan')
    require(sha256(path) == receipt['planned_sha256'], 'MPS contents differ from pre-write plan')
    return dict(verified=True, bytes=info.st_size, sha256=receipt['planned_sha256'],
                reservation_bytes=receipt['reservation_bytes'])


def native_shape_guard(expected, *, production=False, library_path=None):
    """Pure expanded shape check; retain the inherited native reservations.

    Dense raw native output has at most two name/value records per column/row
    (primal and dual), plus one name/status basis record.  highsDoubleToString
    returns char[32], so <=31 characters plus space/newline gives 33.  Basis
    codes have one digit plus space/newline.  65536 covers fixed headers.

    Assessment's pinned 32-bit/little-endian binary writer emits 44*n+28*m+
    12*nz+sum(name byte lengths)+84+DSO-name bytes.  The inherited readback
    demands a DSO name below 4096 bytes; 8192 covers that plus fixed fields.
    The 64-MiB native file cap remains the actual enforcement for every output.
    """
    for relative in PINS:
        _pin(relative)
    n, m, nz = _dimensions(expected['num_col'], expected['num_row'], expected['num_nz'])
    _names(expected)
    if production:
        heldout.check_native_minimum(n, m)
        require(len(expected['integrality']) == n and
                all(_integer(value, 'integrality') in (0, 1) for value in expected['integrality']) and
                sum(map(int, expected['integrality'])) == MAX_BINARIES, 'Production adaptive binary inventory')
    dense = 2*(n*(19+33)+m*(7+33)) + n*(19+3) + m*(7+3) + 65536
    assessment = 63*n + 35*m + 12*nz + 8192
    require(dense < NATIVE_FILE_LIMIT and assessment < NATIVE_FILE_LIMIT, 'Native serializer exceeds unchanged file cap')
    if library_path is not None:
        path = Path(library_path)
        require(path.is_absolute() and len(str(path).encode()) < 4096, 'Unsupported assessment library pathname')
    return dict(columns=n, rows=m, nonzeros=nz, dense_solution_bound_bytes=dense,
                assessment_dump_bound_bytes=assessment, assessment_dso_name_limit_bytes=4095,
                native_file_cap_bytes=NATIVE_FILE_LIMIT,
                carry_point_bound_bytes=n*(19+33)+65536, carry_rows_bound_bytes=m*(7+33)+65536)
