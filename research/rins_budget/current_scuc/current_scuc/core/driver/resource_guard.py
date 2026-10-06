"""Conservative solver-free allocation gates; not measured peak-memory claims."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import math
import resource

MEMORY_BYTES = 7 * 1024**3
ALLOCATION_BYTES = 6 * 1024**3
MODEL_FILE_BYTES = 4 * 1024**3
ARM_STORAGE_BYTES = 24 * 1024**3
ARM_CONTAINMENT_SECONDS = 1800
INT_MAX = 2**31-1

def apply_process_limit():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    if hard != resource.RLIM_INFINITY and hard < MEMORY_BYTES:
        raise ValueError('Existing process hard memory cap below frozen requirement')
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MODEL_FILE_BYTES, MODEL_FILE_BYTES))

def at(value, hour):
    return value[hour] if isinstance(value, list) else value

def projected_master(data, hours, scope, pairs):
    """Count exact columns and rows, conservative structural nnz before build.

    Costs/physics are not changed. Zero coefficients and combined columns may
    reduce actual nnz. Budget includes model, CSC, JSON/readback copies, loader,
    factors, original checker worst-case violated tuple set and 1GiB runtime.
    """
    if pairs is None: raise ValueError('Explicit selected pairs required; static N-1 forbidden')
    B, L, G = (len(data[k]) for k in ('Buses','Transmission lines','Generators'))
    R = len(data.get('Reserves',{}))
    cols = hours*(2*B+L+len(scope['rated_line_indices'])+R)
    rows = hours*(L+B+R); nz = hours*(3*L+G+B+2*L)
    for g in data['Generators'].values():
        seg = len(g['Production cost curve (MW)'])-1
        reserves = len(g.get('Reserve eligibility',[]))
        starts = g.get('Startup delays (h)',[g.get('Minimum downtime (h)',1)])
        U, D = int(g.get('Minimum uptime (h)',1)), int(g.get('Minimum downtime (h)',1))
        cols += hours*(5+seg+reserves)
        rows += hours*(9+seg+len(starts))+(hours-1)
        nz += hours*(4+2+min(U,hours)+1+min(D,hours)+1+2+seg+2*seg+2+reserves+3+reserves+5+reserves+4+reserves+sum(2+min(int(d),hours) for d in starts))
        nz += (hours-1)*(3+reserves)
    nz += hours*(R+sum(len(g.get('Reserve eligibility',[])) for g in data['Generators'].values()))
    normal_hours = sum(math.isfinite(at(l.get('Normal flow limit (MW)',math.inf),t)) for l in data['Transmission lines'].values() for t in range(hours))
    rows += 2*normal_hours; nz += 4*normal_hours
    counts = scope['finite_emergency_hour_counts']
    selected_hours = sum(counts[i] for i,k in pairs)
    rows += 2*selected_hours; nz += 6*selected_hours
    for name, value in [('columns',cols),('rows',rows),('nonzeros',nz)]:
        if type(value) is not int or value < 0 or value > INT_MAX: raise ValueError('32-bit '+name+' bound exceeded')
    # Deliberately conservative fixed accounting, never tuned to May outcomes.
    factors = 8*(8*L*L+8*B*B+16*L*hours+16*B*hours)
    checker_pairs = 256*scope['eligible_pair_count']
    estimated_memory = 1024**3 + 1500*cols + 800*rows + 200*nz + factors + checker_pairs
    estimated_file = 320*(cols+rows+nz)
    result = dict(schema='conservative-master-allocation-v1',columns=cols,rows=rows,
                  nonzeros_upper=nz,selected_pair_count=len(pairs),selected_pair_hours=selected_hours,
                  estimated_simultaneous_bytes=estimated_memory,estimated_model_file_bytes=estimated_file,
                  process_limit_bytes=MEMORY_BYTES,allocation_limit_bytes=ALLOCATION_BYTES,
                  model_file_limit_bytes=MODEL_FILE_BYTES,passed=estimated_memory<=ALLOCATION_BYTES and estimated_file<=MODEL_FILE_BYTES,
                  numerical_work=False,peak_rss_claim=False)
    if not result['passed']: raise ValueError('Preallocation resource gate failed: '+str(result))
    return result

def actual_master(model, projection):
    actual = (len(model.names),len(model.rhs),len(model.val))
    if actual[0]!=projection['columns'] or actual[1]!=projection['rows'] or actual[2]>projection['nonzeros_upper']:
        raise ValueError('Actual source model exceeds conservative preallocation contract')
    return {'columns':actual[0],'rows':actual[1],'nonzeros':actual[2]}


CAMPAIGN_STORAGE_BYTES = 24 * 1024**3
DISK_HEADROOM_BYTES = 2 * 1024**3

def guard_storage(root, prospective_bytes=0):
    from pathlib import Path
    import shutil
    root=Path(root).resolve()
    campaign=next((p for p in (root,*root.parents) if p.name=='run_v1'),root)
    import stat
    current=0
    for path in campaign.rglob('*'):
        try: info=path.stat()
        except FileNotFoundError: continue  # concurrent atomic sidecar/checkpoint rename
        if stat.S_ISREG(info.st_mode): current+=info.st_size
    free=shutil.disk_usage(campaign).free
    if (current+prospective_bytes>CAMPAIGN_STORAGE_BYTES or prospective_bytes+DISK_HEADROOM_BYTES>free):
        raise ValueError('Frozen campaign artifact/available-space headroom gate would be exceeded')
    return {'current_campaign_bytes':current,'prospective_bytes':prospective_bytes,'campaign_cap_bytes':CAMPAIGN_STORAGE_BYTES,
            'available_bytes':free,'minimum_unallocated_headroom_bytes':DISK_HEADROOM_BYTES,'campaign_root':str(campaign)}
