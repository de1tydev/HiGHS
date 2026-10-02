"""Exact bound-file I/O announcements only; never a general warning filter."""
import hashlib
from pathlib import Path

READ='readMPS: Trying to open file '
WRITE='Writing the solution to '
SET_SOLUTION='Set option solution_file to '

def filter_known_io(text,model,solution=None,*,solver=False):
    model=Path(model)
    if any(ord(c)<32 or ord(c)==127 for c in str(model)):raise ValueError('Control character in bound model path')
    expected={READ+str(model):'model_read'}
    if solver:
        solution=Path(solution)
        if any(ord(c)<32 or ord(c)==127 for c in str(solution)):raise ValueError('Control character in bound solution path')
        expected[WRITE+str(solution)]='solution_write'
        expected[SET_SOLUTION+'"'+str(solution)+'"']='solution_option'
    seen={};kept=[];excluded=[]
    for raw in text.splitlines(keepends=True):
        line=raw.rstrip('\r\n')
        if READ in line or WRITE in line or SET_SOLUTION in line:
            if line not in expected:raise ValueError('Unexpected, prefixed, suffixed or foreign-path I/O announcement')
            kind=expected[line]
            if kind in seen:raise ValueError('Duplicate bound-file I/O announcement')
            target=model if kind=='model_read' else solution
            if kind!='solution_option' and not target.is_file():raise ValueError('Present bound-file announcement names a missing file')
            seen[kind]=True;excluded.append(line)
        else:kept.append(raw)
    filtered=''.join(kept)
    return filtered,dict(schema='exact-bound-io-announcement-filter-v2',excluded_lines=excluded,
        raw_text_sha256=hashlib.sha256(text.encode()).hexdigest(),filtered_text_sha256=hashlib.sha256(filtered.encode()).hexdigest(),
        scope='Only exact expected bound-file normal announcements; all other diagnostics retained',solver=solver)
