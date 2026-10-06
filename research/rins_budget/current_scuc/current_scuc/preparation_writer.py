"""Exact preparation MPS prewrite reservation extracted from the original writer."""
import hashlib
import math
from pathlib import Path
import re
import struct
from .case_binding import require, sha as sha256, ContractError as ResourceFailure
from ._paths import ROOT, source_path, source_sha
STATE_LIMIT = 128*1024**2
def finite_17g(value):
    require(not isinstance(value, bool) and math.isfinite(float(value)), 'Invalid finite formatting operand')
    text = format(value, '.17g')
    require(re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?(?:e[+-][0-9]+)?', text) is not None and len(text) <= 24,
            'Finite .17g record width changed')
    require(struct.pack('>d', float(text)) == struct.pack('>d', float(value)), 'Formatting changed binary64 bits')
    return text

def canonical_records(view, canonical):
    """Exact pinned write_model records, without touching an output."""
    n, m = canonical['num_col'], canonical['num_row']
    require(canonical['sense'] == 1 and canonical['offset'] == 0., 'Unsupported objective')
    require(list(view.names) == canonical['col_names'] and canonical['row_names'] == [f'R{i}' for i in range(m)],
            'Canonical writer map mismatch')
    require(len(view.sense) == len(view.rhs) == m, 'Canonical row count mismatch')
    reserved = {'OBJ','RHS1','BND1','NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA','MARKER'}
    for name in view.names:
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,254}', name) is not None and
                name not in reserved and re.fullmatch(r'R[0-9]+|MARK[0-9]+',name) is None, 'Unsafe canonical column')
    for writer, field in (('lb','col_lower'),('ub','col_upper'),('obj','col_cost')):
        values=getattr(view,writer)
        require(len(values)==n and all(struct.pack('>d',float(a)) == struct.pack('>d',float(b))
                for a,b in zip(values,canonical[field])), 'Writer field differs: '+field)
    require(len(view.binary)==n and all(type(v) is bool for v in view.binary) and
            all(int(a)==b for a,b in zip(view.binary,canonical['integrality'])), 'Writer integrality differs')
    yield 'fixed', 'NAME          SCUCBENCH\nROWS\n N  OBJ\n'
    for r, (sense,rhs) in enumerate(zip(view.sense,view.rhs)):
        require(sense in ('E','L','G'), 'Unsupported row sense')
        lo, hi = (rhs if sense != 'L' else -math.inf), (rhs if sense != 'G' else math.inf)
        require(lo == canonical['row_lower'][r] and hi == canonical['row_upper'][r], 'Writer row bounds differ')
        finite_17g(rhs)
        yield 'row', f' {sense}  R{r}\n'
    yield 'fixed', 'COLUMNS\n'
    isint, marker = False, 0
    starts, indices, values = (canonical[k] for k in ('a_start','a_index','a_value'))
    for j,name in enumerate(view.names):
        if view.binary[j] != isint:
            isint = view.binary[j]
            yield 'marker', f"    MARK{marker}  'MARKER'  '{'INTORG' if isint else 'INTEND'}'\n"
            marker += 1
        yield 'objective', f'    {name}  OBJ  {finite_17g(view.obj[j])}\n'
        for z in range(starts[j],starts[j+1]):
            yield 'matrix', f'    {name}  R{indices[z]}  {finite_17g(values[z])}\n'
    if isint: yield 'marker', f"    MARK{marker}  'MARKER'  'INTEND'\n"
    yield 'fixed', 'RHS\n'
    for r,rhs in enumerate(view.rhs):
        if rhs: yield 'rhs', f'    RHS1  R{r}  {finite_17g(rhs)}\n'
    yield 'fixed', 'BOUNDS\n'
    for j,name in enumerate(view.names):
        lo,hi=view.lb[j],view.ub[j]
        require(not math.isnan(lo) and not math.isnan(hi) and lo<=hi and lo!=math.inf and hi!=-math.inf,
                'Invalid canonical bounds')
        require(not view.binary[j] or (lo,hi) in ((0.,0.),(1.,1.),(0.,1.)), 'Unsupported binary bound')
        if lo==hi: yield 'bound', f' FX BND1  {name}  {finite_17g(lo)}\n'
        elif view.binary[j]: yield 'bound', f' BV BND1  {name}\n'
        else:
            if lo==-math.inf: yield 'bound', f' MI BND1  {name}\n'
            elif lo!=0: yield 'bound', f' LO BND1  {name}  {finite_17g(lo)}\n'
            if hi!=math.inf: yield 'bound', f' UP BND1  {name}  {finite_17g(hi)}\n'
    yield 'fixed', 'ENDATA\n'

def canonical_mps_reservation(view,canonical):
    require(sha256(source_path('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py')) == source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py'),
            'Canonical writer source changed')
    counts, digest, total = {}, hashlib.sha256(), 0
    for kind,text in canonical_records(view,canonical):
        payload=text.encode('ascii'); row=counts.setdefault(kind,dict(records=0,bytes=0,max_record_bytes=0))
        row['records']+=1; row['bytes']+=len(payload); row['max_record_bytes']=max(row['max_record_bytes'],len(payload))
        total+=len(payload)
        if total>STATE_LIMIT:raise ResourceFailure('Exact conventional MPS exceeds unchanged128MiB cap')
        digest.update(payload)
    require(counts['matrix']['records']==canonical['num_nz'] and counts['objective']['records']==canonical['num_col']
            and counts['row']['records']==canonical['num_row'],'Incomplete canonical record plan')
    return dict(schema='conventional-canonical-mps-reservation/v1',exporter_sha256=source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py'),
                exact_planned_bytes=total,reservation_bytes=total,planned_sha256=digest.hexdigest(),records=counts,
                finite_17g_max_bytes=24,mps_cap_bytes=STATE_LIMIT,reservation_basis='complete exact canonical record stream')

def verify_written_mps(path,receipt):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and receipt['schema']=='conventional-canonical-mps-reservation/v1',
            'Invalid canonical output/receipt')
    require(path.stat().st_size==receipt['exact_planned_bytes']<=receipt['reservation_bytes']<=STATE_LIMIT
            and sha256(path)==receipt['planned_sha256'],'Canonical output differs from prewrite plan')
    return dict(verified=True,bytes=path.stat().st_size,sha256=sha256(path))
