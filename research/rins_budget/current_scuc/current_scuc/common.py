"""Narrow bindings to frozen projection, proof and artifact helpers; no work at import."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import hashlib
from contextlib import contextmanager
import importlib.util
import math
import os
from pathlib import Path
import sys
import time

ROOT = PACKAGE_ROOT
RETENTION_CONTRACT_SHA = '15d02f592afbfa0f57bbbc21a65cdd343d0914cde811aa2e6cb6167799b76c32'
DISCOVERY_REVIEW_SHA = 'c9adb98ed79c83015241a784aa38d2ac6fb36df0579c2e19306a0c9870352a83'
STORAGE_CONTRACT_SHA = 'e7812bdcb09753885884522ee3d64dcb07aa546b08f64abcce4abd16c32f5a5d'
NATIVE_CAP_ADDENDUM_SHA = '739a4bb891a26a5a99583d89c0469081e58e353df561a7e3429be87264750283'
CARRY_PROPOSAL_SHA = '94343d879494ad0eb0cf84494cc6c3041b8b814746ea37dd6b51923a3ba9f9e6'
PROPOSAL_SHA = 'f7b60293bbd62c3398a9dfec19f950d5a5dac5b33d058f16fb2810db7821e7f0'
ADAPTIVE_PROPOSAL_SHA = 'e736b6b52300226a68910846397e6201f188a8d2919cac7f382419254c0b153e'
LP_TERMINAL_RECEIPT_SHA = '64f049a0e46dfcdfa605ead16fc77283ba7bef4bfd2512f2eb7b912755f09fbc'
ADAPTIVE_RUNTIME = None


def module(name, path):
    return load_module(name, path)


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def helpers():
    f = module('_integer_frozen_full_arm', ROOT / 'full_arm.py')
    if not getattr(f, '_discovery_bounded_io', False):
        f.write_json = bounded_json
        f.bundle = bounded_bundle
        f._discovery_bounded_io = True
    return f


_METADATA = None
IO_ADMISSIONS = []
NATIVE_LIMIT_RECORDS = []


def storage():
    return module('storage_budget', ROOT/'storage_budget.py')


def native_limits():
    return module('native_exec', ROOT/'native_exec.py')


@contextmanager
def native_call_guard(action, log_path=None):
    if log_path is not None:
        budget=storage()
        IO_ADMISSIONS.append(budget.admit_phase(Path(log_path).parent,phase=action,writes=[budget.WriteBound(
            log_path,budget.NATIVE_FILE_LIMIT,'synchronous native log','temporary native-only 64-MiB file limit')]))
    record=None;error_type=None
    try:
        with native_limits().native_output_guard() as record:
            yield record
    except BaseException as exc:
        error_type=type(exc).__name__
        raise
    finally:
        if record is not None:
            record.update(action=action,error_type=error_type)
            NATIVE_LIMIT_RECORDS.append(dict(record))


def start_output_phase(path, phase, writes=(), metadata_bytes=None):
    global _METADATA
    budget = storage()
    record = budget.admit_phase(path,phase=phase,writes=list(writes),
        metadata_bytes=budget.METADATA_LIMIT if metadata_bytes is None else metadata_bytes)
    _METADATA = budget.MetadataBudget()
    IO_ADMISSIONS.append(record)
    return record


def bounded_write(path,value,*,fresh=False,limit=None):
    global _METADATA
    budget = storage()
    if _METADATA is None: _METADATA = budget.MetadataBudget()
    return budget.atomic_json(path,value,fresh=fresh,limit=budget.STATE_LIMIT if limit is None else limit,
        metadata_budget=_METADATA)


def bounded_json(out,name,value,costs):
    tick=time.monotonic();require(Path(name).name==name,'Artifact name must be a basename')
    path=Path(out)/name;f=helpers()
    bounded_write(path,f.clean_json(value))
    costs['serialization_seconds']=costs.get('serialization_seconds',0.)+time.monotonic()-tick
    return dict(path=path.name,sha256=f.sha256(path),bytes=path.stat().st_size)


def bounded_bundle(out,stem,value,costs):
    """Same array split/bit readback contract, with a bounded NPZ writer."""
    import numpy as np
    tick=time.monotonic();arrays={};f=helpers();budget=storage()
    require(Path(stem).name==stem,'Artifact stem must be a basename')
    def split(item,key='root'):
        if isinstance(item,np.ndarray):
            require(item.dtype.kind in 'biuf','Object or nonnumeric artifact array')
            name='a'+str(len(arrays));arrays[name]=np.array(item,copy=True,order='C')
            return dict(npz_array=name,field=key,dtype=item.dtype.str,shape=list(item.shape))
        if isinstance(item,dict):return {str(k):split(v,key+'.'+str(k)) for k,v in item.items()}
        if isinstance(item,(list,tuple)):return [split(v,key+'['+str(i)+']') for i,v in enumerate(item)]
        return item
    document=split(value);receipt={'bit_roundtrip_verified':True}
    if arrays:
        path=Path(out)/(stem+'.npz')
        # Each array has bounded numeric dtype and explicit shape. ZIP/NPY names
        # and headers are tiny; 64 KiB per member conservatively covers both.
        maximum=sum(a.nbytes+65536 for a in arrays.values())+65536
        require(maximum<=budget.STATE_LIMIT,'NPZ output exceeds fixed 128-MiB writer cap')
        with budget.bounded_open(path,maximum) as stream:np.savez(stream,**arrays)
        with np.load(path,allow_pickle=False) as stored:
            require(set(stored.files)==set(arrays),'NPZ array names drifted')
            for key,expected in arrays.items():
                actual=stored[key]
                require(actual.dtype==expected.dtype and actual.shape==expected.shape and actual.tobytes()==expected.tobytes(),'NPZ bit readback mismatch: '+key)
        receipt['arrays']=dict(path=path.name,sha256=f.sha256(path),bytes=path.stat().st_size,
            count=len(arrays),array_sha256={k:hashlib.sha256(a.tobytes()).hexdigest() for k,a in arrays.items()})
    costs['serialization_seconds']=costs.get('serialization_seconds',0.)+time.monotonic()-tick
    receipt['document']=bounded_json(out,stem+'.json',document,costs)
    return receipt


class GuardedLP:
    """Bound native-only LP calls; frozen methods never write Python artifacts."""
    def __init__(self,factory,*args):
        self.limit_records=[]
        self._log_path=Path(args[1])
        record=None
        try:
            with native_call_guard('PersistentLP.__init__',self._log_path) as record:self._lp=factory(*args)
        finally:
            if record is not None:self.limit_records.append(dict(record))
    def __getattr__(self,name):
        value=getattr(self._lp,name)
        if not callable(value):return value
        def guarded(*args,**kwargs):
            record=None
            try:
                with native_call_guard(name,self._log_path) as record:return value(*args,**kwargs)
            finally:
                if record is not None:self.limit_records.append(dict(record))
        return guarded
    def __enter__(self):return self
    def __exit__(self,*args):self.destroy()


def native_shape_guard(expected,*,production=False):
    """Source-derived ceilings required before CLI and assessment outputs."""
    from current_scuc.writer_bounds import native_shape_guard as adaptive_shape_guard
    return adaptive_shape_guard(expected,production=production)


def native_command(command,cwd,cfg,*,solver):
    f=helpers();native=native_limits()
    executable_sha=runtime_sha('binary')
    library_sha=runtime_sha('library')
    require(solver is True and Path(command[0]).resolve()==Path(cfg['binary']).resolve(), 'Native CLI identity mismatch')
    require(f.sha256(command[0])==executable_sha and f.sha256(cfg['library'])==library_sha, 'Immutable native runtime pin changed')
    return native.build_command(command,cwd=cwd,receipt_path=Path(cwd)/'native-exec.json',
        executable_sha256=executable_sha,python=cfg['python'],solver=True,
        expected_library_path=cfg['library'],expected_library_sha256=library_sha)


def native_receipt(cwd,evidence,process_receipt):
    return native_limits().verify_receipt(Path(cwd)/'native-exec.json',evidence,process_receipt=process_receipt)



def read_bundle(directory, receipt):
    """Read only an explicitly hash-bound fresh-stage artifact; verify every array."""
    import numpy as np
    f = helpers()
    directory = Path(directory).resolve()
    document = receipt['document']
    def path(item):
        p = directory / item['path']
        require(Path(item['path']).name == item['path'] and p.is_file(), 'Invalid bundle member')
        require(f.sha256(p) == item['sha256'] and p.stat().st_size == item['bytes'], 'Bundle byte mismatch')
        return p
    raw = f.strict_json(path(document))
    arrays = {}
    if 'arrays' in receipt:
        a = receipt['arrays']
        with np.load(path(a), allow_pickle=False) as stored:
            require(set(stored.files) == set(a['array_sha256']), 'Bundle array inventory mismatch')
            for name in stored.files:
                value = np.array(stored[name], copy=True)
                require(hashlib.sha256(value.tobytes()).hexdigest() == a['array_sha256'][name], 'Bundle array hash mismatch')
                arrays[name] = value
    def restore(value):
        if isinstance(value, dict):
            if 'npz_array' in value:
                a = arrays[value['npz_array']]
                require(a.dtype.str == value['dtype'] and list(a.shape) == value['shape'], 'Bundle array schema mismatch')
                return a
            return {k: restore(v) for k, v in value.items()}
        return [restore(v) for v in value] if isinstance(value, list) else value
    return restore(raw)


def verify_manifest(path, digest, deadline):
    """Bind all fresh case, package and native/Python runtime bytes locally."""
    from current_scuc import binding, heldout
    f = helpers()
    require(f.sha256(path) == digest, 'Arm manifest changed')
    manifest = f.strict_json(path)
    require(manifest['schema'] == 'current-scuc-arm-manifest/v1', 'Wrong candidate manifest schema')
    heldout.check_manifest(manifest)
    binding.verify_freeze()
    paths, identities = {}, []
    def checked(item):
        p = Path(item['path']).resolve()
        require(p.is_file() and f.sha256(p) == item['sha256'], 'Changed local artifact: ' + str(p))
        require(time.monotonic() < deadline, 'Whole deadline during verification')
        identities.append(dict(path=str(p), sha256=item['sha256'], bytes=p.stat().st_size))
        return p
    pins = heldout.input_pins()
    require(set(manifest['inputs']) == set(pins), 'Incomplete candidate input identities')
    for role, expected in pins.items():
        require(manifest['inputs'][role]['sha256'] == expected, 'Input identity changed: ' + role)
        paths[role] = checked(manifest['inputs'][role])
    payload = {checked(item) for item in manifest['payload_files']}
    snapshot = binding.verify_source_snapshot(binding.config()['source_snapshot'])
    require(payload == {(ROOT / name).resolve() for name in snapshot['files_sha256']}, 'Incomplete package source inventory')
    runtime = manifest['runtime']
    require(Path(runtime['python_executable']).resolve() == Path(sys.executable).resolve(), 'Wrong Python')
    require(runtime['python_version'] == list(sys.version_info[:3]), 'Wrong Python version')
    require(all(runtime['environment'].get(k) == v for k, v in f.ENVIRONMENT.items()), 'Missing runtime environment')
    require(all(os.environ.get(k) == v for k, v in runtime['environment'].items()), 'Environment mismatch')
    runtime_paths = {checked(item) for item in runtime['files']}
    require(Path(sys.executable).resolve() in runtime_paths, 'Unpinned interpreter')
    return manifest, paths, identities


def prepare(paths, manifest, deadline):
    """Each process factors fresh; no factor archive is imported."""
    f = helpers()
    model, old_projection, old_capi, qa, full_oracle = f.load_modules()
    import current_scuc.adaptive as adaptive
    projection,capi=adaptive.adapter(),adaptive.native()
    original = model.load_expected(paths['expected'], f.INPUT_PINS['expected'])
    from current_scuc.case_binding import read_source
    data = read_source(paths['source'])
    full_oracle.v2.check_finite_source(data)
    import current_scuc.heldout as heldout
    heldout.check_inputs({k+'_sha256': f.INPUT_PINS[k] for k in ('source','expected','mps','generator')}, data=data, expected=original)
    generator = module('_integer_frozen_generator', paths['generator'])
    oracle = full_oracle.prepare(data, original, f.PAIRS, generator=generator,
        pins={k + '_sha256': f.INPUT_PINS[k] for k in ('source', 'expected', 'mps', 'generator')}, deadline=deadline)
    oracle.source_data=data
    require(f.valid_full_scope(oracle.full_scope), 'Invalid complete oracle scope')
    require(all(oracle.full_scope[k] == manifest['scope'][k] for k in f.FULL_COUNTS), 'Production coverage mismatch')
    projected, metadata, activation = adaptive.make_base(original,data,36,f.PAIRS,oracle.lodf,
        oracle.pins['source_sha256'],oracle.full_scope)
    master = module('_integer_master', Path(__file__).with_name('master.py'))
    metadata['source_binary_authority'] = master.source_binary_authority(data, 36)
    return model, projection, capi, qa, oracle, original, projected, metadata, data


def append_batch(expected, batch, model):
    return model.append_rows(expected, batch['lower'], batch['upper'], batch['starts'],
        batch['index'], batch['value'], batch['names'])


def evaluate_point(x, original, metadata, oracle, out, round_index, deadline, *, projection, qa,
                   integer=False, master=None, persist_batch=True):
    """Full support and persisted zero-radius lift QA. Never a final physical U."""
    import numpy as np
    f = helpers()
    require(time.monotonic() < deadline, 'No whole time for oracle evaluation')
    full_scope = metadata['full_scope']
    require(oracle.full_scope == full_scope and f.valid_full_scope(full_scope), 'Oracle scope changed')
    retained = projection.restore_retained(x, metadata)
    retained.setflags(write=False)
    before = retained.tobytes()
    evaluated = oracle.evaluate(retained, deadline=deadline)
    require(retained.tobytes() == before and not retained.flags.writeable, 'Oracle changed retained point')
    require(f.certificate_gate(evaluated['certificate'], full_scope), 'Full support certificate failed')
    require(evaluated['original_network_lift'].get('network_residual_le_1e_5') is True, 'Network recovery failed')
    lift = np.asarray(evaluated['original_network_lift']['values'])
    f.verify_retained(retained, lift, metadata)
    costs = {}
    record = {'oracle_artifact': f.bundle(out, f'round-{round_index:02d}-oracle', evaluated, costs)}
    stored, receipt = f.persist_lift(out, round_index, lift, costs)
    f.verify_retained(retained, stored, metadata)
    check = oracle.check_lift(stored, deadline=deadline)
    require(f.full_lift_gate(check, full_scope, receipt['readback_values_sha256']), 'Full stored-lift check failed')
    record.update(stored_lift_artifact=receipt, full_source_quality=check,
        full_source_quality_artifact=f.bundle(out, f'round-{round_index:02d}-full-source-quality', check, costs))
    source_check = qa.check_primal(original, stored)
    record['source_quality_artifact'] = f.bundle(out, f'round-{round_index:02d}-source-quality', source_check, costs)
    source_check.pop('activities', None)
    require(source_check.get('passed') is True, 'Original matrix primal check failed')
    if integer:
        require(master is not None, 'Integer checker absent')
        integer_check = master.check_integer_values(original, dict(zip(original['col_names'], map(float, stored))))
        require(integer_check['passed'] is True, 'Original binary/temporal matrix check failed')
        integer_check.pop('x', None)
        record['original_integer_quality'] = integer_check
    import current_scuc.no_shedding as no_shedding
    record['target_subset_quality'] = no_shedding.point_check(original, stored, metadata['hard_zero_subset'],
        projection.model, production=full_scope['production_scope'])
    record['negligible_slack_quality'] = no_shedding.slack_quality(original, stored)
    upper = source_check['objective_recomputed']
    oracle_upper = evaluated['original_network_lift']['recomputed_original_objective']
    require(finite(upper) and finite(oracle_upper), 'Nonfinite provisional upper')
    require(abs(upper-oracle_upper) <= max(1e-5, 1e-10*max(abs(upper), abs(oracle_upper))), 'Oracle/matrix cost disagreement')
    import current_scuc.adaptive as adaptive
    require(ADAPTIVE_RUNTIME is not None,'Fresh adaptive runtime absent')
    current=ADAPTIVE_RUNTIME.expected
    activation=adaptive.activation(metadata)
    emitted,debit=adaptive.support().evaluate_supports(activation,oracle,evaluated,retained,
        ADAPTIVE_RUNTIME.bank,ADAPTIVE_RUNTIME.cache,deadline)
    ADAPTIVE_RUNTIME.check_requests()
    caps=adaptive.adapter().line_caps(oracle.source_data,metadata['hours'],oracle.lodf,emitted['token']['active'])
    batch=adaptive.envelope(current,metadata,emitted,caps,debit)
    record['adaptive_support_artifact']=f.bundle(out,f'round-{round_index:02d}-adaptive-support',batch,costs)
    record.update(adaptive_support_passed=True,adaptive_cache=adaptive.support().cache_receipt(ADAPTIVE_RUNTIME.cache),
        combined_elementary_requests=ADAPTIVE_RUNTIME.check_requests(),map_hash=metadata['map_hash'],
        matrix_identity=metadata['matrix_identity'],positive_lines=list(emitted['token']['active']))
    record.update(source_quality=source_check, source_point_components=f.point_components(original, stored),
        provisional_upper=max(upper, oracle_upper), oracle_objective=oracle_upper,
        full_scope_identity_sha256=full_scope['full_scope_identity_sha256'],
        full_scope_scans=2, oracle_evaluations=1, final_upper_admitted=False,
        retained_original_columns=list(map(int, metadata['retained_original_columns'])),
        retained_values_sha256=hashlib.sha256(stored[metadata['retained_original_columns']].tobytes()).hexdigest())
    if persist_batch:
        record['cut_batch_artifact'] = record['adaptive_support_artifact']
    require(time.monotonic() < deadline, 'Whole deadline during oracle/lift checks')
    return batch, record


def verify_source_freeze(path, digest):
    from current_scuc.binding import verify_package_source
    return verify_package_source(path, digest)
