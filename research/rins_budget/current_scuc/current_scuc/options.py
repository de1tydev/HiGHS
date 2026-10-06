"""Fixed role-specific options and public-API readback on an empty reference handle."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from pathlib import Path
import hashlib
import re
from current_scuc.native_exec import validate_solver_random_seed
from current_scuc.common import ROOT, helpers, module, require, finite

PROOF = ('threads = 2\nparallel = off\npresolve = on\nwrite_solution_to_file = true\n'
    'write_solution_style = 0\nlog_dev_level = 1\nhighs_analysis_level = 128\n'
    'mip_rel_gap = 0.01\nmip_abs_gap = 0\nmip_improving_solution_save = false\n'
    'mip_lp_solver = choose\nmip_ipm_solver = choose\n')
EXPECTED = {
    'Int': {'threads': 2, 'random_seed': 0, 'write_solution_style': 0, 'log_dev_level': 1,
            'highs_analysis_level': 128, 'highs_debug_level': 0, 'mip_max_nodes': 2147483647, 'mip_max_improving_sols': 2147483647},
    'Double': {'mip_rel_gap': .01, 'mip_abs_gap': 0., 'mip_feasibility_tolerance': 1e-6,
        'primal_feasibility_tolerance': 1e-7, 'dual_feasibility_tolerance': 1e-7,
        'optimality_tolerance': 1e-7, 'kkt_tolerance': 1e-7, 'mip_heuristic_effort': .05},
    'Bool': {'write_model_to_file': False, 'write_presolved_model_to_file': False, 'write_solution_to_file': True, 'mip_improving_solution_save': False,
        'mip_heuristic_run_feasibility_jump': True, 'mip_heuristic_run_rins': True,
        'mip_heuristic_run_rens': True, 'mip_heuristic_run_root_reduced_cost': True,
        'mip_heuristic_run_zi_round': False, 'mip_heuristic_run_shifting': False},
    'String': {'write_model_file': '', 'write_presolved_model_file': '', 'write_iis_model_file': '',
        'write_basis_file': '', 'mip_improving_solution_file': '', 'ranging': 'off',
        'read_basis_file': '', 'parallel': 'off', 'presolve': 'on', 'mip_lp_solver': 'choose', 'mip_ipm_solver': 'choose'},
}

# Exact pinned build excludes this member and option registration. No generic
# failed-getter exception is introduced: runtime inventory must prove absence.
COMPILED_OUT_OPTION = 'mip_debug_solution_file'
BUILD_OPTION_PINS = {
    'pristine-source/highs/Highs.h': '48113595b60211adfcf0200f1f23ae46cea22c21dc64648f70cd389d4f19e89d',
    'pristine-build/CMakeCache.txt': '33fd1d06f80af72311aa341322760f3cb9d312d9ef70b4029a934942dde99ded',
    'pristine-build/HConfig.h': 'f764fdbb5ddb7f8a9f9b8d3824438f3f3ba5a5552d08d21db163cf5dff1fcbcf',
    'pristine-source/CMakeLists.txt': '29ecd20ff02ed171ac56ca9b6433fdaf673534329699060c53602669a47bcf40',
    'pristine-source/highs/lp_data/HighsOptions.h': 'c2a1db98117a9016acf51bf04f7a6e2f801d79b240528e2ef8891e2556f1b410',
    'pristine-source/highs/interfaces/highs_c_api.cpp': 'fbe75ee7e3e5938f0f04a04caf704ff38ba1bad2b7d252a850018473b6ab8396',
}
OPTION_TYPES = {'Bool':0,'Int':1,'Double':2,'String':3}


def compiled_out_source_evidence():
    f=helpers()
    for relative,digest in BUILD_OPTION_PINS.items():
        require(f.sha256(runtime_path(relative))==(runtime_sha('hconfig') if relative == 'pristine-build/HConfig.h' else runtime_sha('cmake_cache') if relative == 'pristine-build/CMakeCache.txt' else digest),'Conditional option source/build pin changed: '+relative)
    require(re.findall(r'^DEBUGSOL:BOOL=(.+)$',(runtime_path('pristine-build/CMakeCache.txt')).read_text(),re.M)==['OFF'],
        'Debug solution build must remain disabled')
    return dict(option=COMPILED_OUT_OPTION,compile_definition='HIGHS_DEBUGSOL',cmake_cache_value='OFF',
        source_build_pins={relative:f.sha256(runtime_path(relative)) for relative in BUILD_OPTION_PINS},expected_runtime_presence=False,
        debug_registration_precedes_user_settable_count=True,normal_named_getters_not_inferred_from_enumeration=True)


def check_option_inventory(names,count,expected):
    require(type(count) is int and 0<count<=4096 and len(names)==count and len(set(names))==count,
        'Incomplete/duplicate option inventory')
    require(all(type(name) is str and name and name.isascii() and len(name)<128 for name in names),'Invalid option inventory name')
    require(COMPILED_OUT_OPTION not in names,'Compiled-out debug option unexpectedly exposed')
    return dict(count=count,names=names,names_sha256=hashlib.sha256(('\n'.join(names)+'\n').encode()).hexdigest(),
        complete=True,unique=True,compiled_out_debug_option_absent=True,
        scope='Highs_getNumOptions user-settable prefix only; ordinary named getters remain authoritative')


def read_option_inventory(lib,h,C,I,P,expected,cfg):
    count=int(lib.Highs_getNumOptions(h))
    require(0<count<=4096,'Unsafe option count')
    # The pinned C API calls process-global malloc. The pinned interpreter
    # interposes malloc/free, so verify the matching symbol object rather than
    # assuming a libc filename. No HiGHS object or option is mutated here.
    allocator_api=C.CDLL(None);allocator_api.free.restype=None;allocator_api.free.argtypes=[P]
    bridge=module('_integer_master',Path(__file__).with_name('master.py'))
    allocator=bridge.helpers().readback.symbol_provenance(allocator_api,('malloc','free'))
    allocated,freed=allocator['malloc'],allocator['free']
    require(allocated['path']==freed['path'] and allocated['sha256']==freed['sha256'] and
        cfg['runtime_pins'].get(freed['path'])==freed['sha256'],
        'Option-name malloc/free object does not match frozen runtime identity')
    names=[]
    for index in range(count):
        pointer=P()
        status=lib.Highs_getOptionName(h,index,C.byref(pointer))
        try:
            require(status==0 and bool(pointer.value),'Option name getter failed')
            names.append(C.string_at(pointer).decode('ascii'))
        finally:
            if pointer.value:allocator_api.free(pointer)
    return dict(check_option_inventory(names,count,expected),name_allocator=allocator,returned_names_freed=True)

DISCOVERY = 'discovery'
PROOF_ROLE = 'proof'
ROLES = (DISCOVERY, PROOF_ROLE)


def role_for_call(call):
    require(type(call) is int and 1 <= call <= 3, 'Fixed three-call role schedule')
    return DISCOVERY if call == 1 else PROOF_ROLE


def option_text(role=PROOF_ROLE):
    require(role in ROLES, 'Unknown MIP role')
    return PROOF + ('mip_max_improving_sols = 1\n' if role == DISCOVERY else '')


def expected_options(role, native_limit, *, start, solver_random_seed=0):
    require(role in ROLES, 'Unknown MIP role')
    require(role != DISCOVERY or start is None, 'Discovery must be cold')
    expected = {kind: dict(items) for kind, items in EXPECTED.items()}
    expected['Int']['random_seed'] = validate_solver_random_seed(solver_random_seed)
    expected['Int']['mip_max_improving_sols'] = 1 if role == DISCOVERY else 2147483647
    expected['Double']['time_limit'] = native_limit
    expected['String']['read_solution_file'] = str(Path(start).resolve()) if start is not None else ''
    expected['String']['log_file'] = ''
    return expected



def command(cfg, model, option_path, solution, native_limit, start=None, *, role=PROOF_ROLE, solver_random_seed=0):
    require(role in ROLES and (role != DISCOVERY or start is None), 'Invalid/carry discovery role')
    require(finite(native_limit) and native_limit > 0, 'No native request window')
    solver_random_seed = validate_solver_random_seed(solver_random_seed)
    result = [str(Path(cfg['binary']).resolve()), str(Path(model).resolve()), '--options_file', str(Path(option_path).resolve()), '--time_limit',
        format(native_limit, '.17g'), '--random_seed', str(solver_random_seed), '--solution_file', str(Path(solution).resolve())]
    if start is not None:
        require(Path(start).resolve()!=Path(solution).resolve(),'start input must differ from output')
        require(Path(start).is_file(),'start input missing')
        result += ['--read_solution_file',str(Path(start).resolve())]
    return result


def probe(cfg, option_path, native_limit, start=None, *, role=PROOF_ROLE, solver_random_seed=0):
    """Production profile stays exact; fixture callers cannot change it."""
    require(Path(option_path).read_text() == option_text(role), 'Unsupported option bytes')
    expected = expected_options(role, native_limit, start=start, solver_random_seed=solver_random_seed)
    from current_scuc.common import native_call_guard
    with native_call_guard('production option readback') as guard:
        result = _probe_checked(cfg, option_path, native_limit, start, role, expected, solver_random_seed)
    return dict(result,native_output_limit=guard)


def _probe_checked(cfg, option_path, native_limit, start, role, expected, solver_random_seed=0):
    """Private readback shared with the separately pinned rgn fixture profile."""
    solver_random_seed = validate_solver_random_seed(solver_random_seed)
    require(type(expected['Int']['random_seed']) is int and expected['Int']['random_seed'] == solver_random_seed,
        'Option reference seed/profile mismatch')
    import ctypes as C
    f = helpers()
    base = module('_integer_frozen_option_identity', ROOT/'option_probe.py')
    # The v4 binding predates this descriptive field; byte pins plus the
    # native githash below independently establish this frozen source commit.
    identity = base._runtime(dict(cfg, pristine_source_commit=base.SOURCE_COMMIT))
    conditional=compiled_out_source_evidence()
    require(role != DISCOVERY or start is None, 'Discovery must be cold')
    I, D, P = C.c_int32, C.c_double, C.c_void_p
    lib = C.CDLL(identity['library_path'])
    signatures = {'Highs_create': (P, []), 'Highs_destroy': (None, [P]),
        'Highs_readOptions': (I, [P, C.c_char_p]), 'Highs_setBoolOptionValue': (I,[P,C.c_char_p,I]),
        'Highs_setDoubleOptionValue': (I,[P,C.c_char_p,D]), 'Highs_setIntOptionValue': (I,[P,C.c_char_p,I]),
        'Highs_setStringOptionValue': (I,[P,C.c_char_p,C.c_char_p]),
        'Highs_githash': (C.c_char_p, []), 'Highs_getSizeofHighsInt': (I,[P]),
        'Highs_getNumOptions':(I,[P]),'Highs_getOptionName':(I,[P,I,C.POINTER(P)]),
        'Highs_getOptionType':(I,[P,C.c_char_p,C.POINTER(I)])}
    for kind, typ in [('Int', I), ('Double', D), ('Bool', I), ('String', C.c_char)]:
        signatures['Highs_get'+kind+'OptionValue'] = (I,[P,C.c_char_p,C.POINTER(typ)])
    for name, (restype, argtypes) in signatures.items():
        getattr(lib,name).restype, getattr(lib,name).argtypes = restype, argtypes
    bridge = module('_integer_master',Path(__file__).with_name('master.py'))
    symbols = bridge.helpers().readback.symbol_provenance(lib,tuple(signatures))
    require(all(row['path'] == identity['library_path'] and row['sha256'] == runtime_sha('library')
        for row in symbols.values()) and set(symbols) == set(signatures), 'Option API symbol provenance mismatch')
    h = lib.Highs_create()
    require(bool(h), 'Option reference handle absent')
    try:
        require(lib.Highs_getSizeofHighsInt(h) == 4 and lib.Highs_githash().decode() == base.NATIVE_GITHASH,
            'Option probe runtime mismatch')
        require(lib.Highs_setBoolOptionValue(h,b'output_flag',0) == 0, 'Cannot quiet option probe')
        require(lib.Highs_readOptions(h,str(option_path).encode()) == 0, 'Cannot parse proof options')
        require(lib.Highs_setIntOptionValue(h,b'random_seed',solver_random_seed) == 0 and
            lib.Highs_setDoubleOptionValue(h,b'time_limit',native_limit) == 0, 'CLI option probe failed')
        if start is not None:
            require(Path(start).is_file(),'start input missing at option probe')
            require(lib.Highs_setStringOptionValue(h,b'read_solution_file',str(Path(start).resolve()).encode())==0,
                'Cannot set public CLI input solution path')
        inventory=read_option_inventory(lib,h,C,I,P,expected,cfg)
        actual = {};typed_reads={};failures=[]
        for kind, items in expected.items():
            for name,want in items.items():
                option_type=I()
                type_status=int(lib.Highs_getOptionType(h,name.encode(),C.byref(option_type)))
                typed_reads[name]=dict(expected_kind=kind,type_status=type_status,
                    actual_type=option_type.value if type_status==0 else None)
                if type_status!=0 or option_type.value!=OPTION_TYPES[kind]:
                    failures.append('Option type getter failed or mismatched: '+name);continue
                value = C.create_string_buffer(4096) if kind == 'String' else D() if kind == 'Double' else I()
                arg = value if kind == 'String' else C.byref(value)
                getter_status=int(getattr(lib,'Highs_get'+kind+'OptionValue')(h,name.encode(),arg))
                typed_reads[name]['getter_status']=getter_status
                if getter_status!=0:
                    failures.append('Option getter failed: '+name);continue
                got = value.value.decode() if kind == 'String' else bool(value.value) if kind == 'Bool' else value.value
                typed_reads[name].update(actual_value=got,expected_value=want,value_matches=(got==want))
                if got!=want:failures.append('Effective option mismatch: '+name)
                actual[name] = got
        if failures:
            failure=ValueError('; '.join(failures))
            failure.evidence=dict(option_inventory=inventory,typed_option_readback=typed_reads,compiled_out_option=conditional,failures=failures)
            raise failure
        return dict(passed=True, role=role, solver_random_seed=solver_random_seed, identity=identity, loaded_symbol_provenance=symbols,
            option_inventory=inventory,typed_option_readback=typed_reads,compiled_out_option=conditional,
            options=actual, options_sha256=f.sha256(option_path),
            same_live_solving_handle=False, model_read_called=False, optimization_or_presolve_called=False)
    finally:
        lib.Highs_destroy(h)
