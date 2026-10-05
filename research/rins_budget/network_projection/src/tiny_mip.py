"""Fresh public-C-API integer solves for the fixed tiny demonstration only.

No incumbent, basis or search state is supplied. This is a new portable tiny
adapter, not the process/log parser used by the recorded 36-hour experiment.
"""
import ctypes as C
import math
import time
import numpy as np
import capi
import model
import integer_bridge


def solve(expected, library, log_path, deadline):
    e = model.validate_model(expected)
    model.require(e['num_col'] < 1000 and e['num_row'] < 1000, 'Tiny adapter size limit')
    model.require(np.count_nonzero(e['integrality']) == 12, 'Fixed tiny needs exactly twelve binaries')
    with capi.PersistentLP(library, log_path) as lp:
        options = {'solver': 'choose', 'mip_rel_gap': .01, 'mip_abs_gap': 0.,
                   'mip_lp_solver': 'choose', 'mip_ipm_solver': 'choose', 'random_seed': 0}
        for key, value in options.items():
            lp.set_option(key, value)
        args = (e['num_col'], e['num_row'], e['num_nz'], 1, e['sense'], e['offset'],
                *(lp._ptr(e[k]) for k in ('col_cost', 'col_lower', 'col_upper',
                  'row_lower', 'row_upper', 'a_start', 'a_index', 'a_value')))
        lp._call('Highs_passMip', *args, lp._ptr(e['integrality']))
        for field, api in (('col_names', 'Highs_passColName'), ('row_names', 'Highs_passRowName')):
            for index, name in enumerate(e[field]):
                capi.checked(getattr(lp.lib, api)(lp.handle, index, name.encode()), api)
        readback = lp._verify(e)
        remaining = min(20., deadline-time.monotonic()-5.)
        model.require(remaining > 0, 'No tiny integer solve window')
        lp.set_option('time_limit', float(remaining))
        started = time.monotonic()
        status = int(lp.lib.Highs_run(lp.handle))
        wall = time.monotonic()-started
        native_status = int(lp.lib.Highs_getModelStatus(lp.handle))
        model.require(status == 0 and native_status == 7, 'Tiny requires clean OK/Optimal; no TimeLimit admission')
        model.require(time.monotonic() < deadline, 'Tiny integer deadline exceeded')
        arrays = {name: np.full(size, np.nan) for name, size in
                  (('col_value', e['num_col']), ('col_dual', e['num_col']),
                   ('row_value', e['num_row']), ('row_dual', e['num_row']))}
        capi.checked(lp.lib.Highs_getSolution(lp.handle, *(lp._ptr(arrays[k]) for k in
                     ('col_value', 'col_dual', 'row_value', 'row_dual'))), 'Highs_getSolution')
        info = {}
        for name in ('mip_dual_bound', 'objective_function_value', 'mip_gap', 'max_primal_infeasibility'):
            value = C.c_double(math.nan)
            capi.checked(lp.lib.Highs_getDoubleInfoValue(lp.handle, name.encode(), C.byref(value)), name)
            model.require(math.isfinite(value.value), 'Nonfinite native '+name)
            info[name] = value.value
        for name, wanted in (('primal_solution_status', 2), ('num_primal_infeasibilities', 0)):
            value = C.c_int32(-1)
            capi.checked(lp.lib.Highs_getIntInfoValue(lp.handle, name.encode(), C.byref(value)), name)
            model.require(value.value == wanted, 'Invalid native '+name)
            info[name] = value.value
        check = integer_bridge.check_integer_values(e, dict(zip(e['col_names'], arrays['col_value'])))
        model.require(check['passed'], 'Independent tiny master primal/integrality check failed')
        x = check.pop('x')
        objective = check['linear_objective']
        model.require(abs(objective-info['objective_function_value']) <= max(1e-5, 1e-10*abs(objective)), 'Native/master objective mismatch')
        model.require(info['mip_dual_bound'] <= objective+1e-7 and 0 <= info['mip_gap'] <= .01 and info['max_primal_infeasibility'] <= 1e-6, 'Invalid tiny numerical MIP interval')
        diagnostics = lp._check_diagnostics()
        return x, dict(passed=True, run_status=status, model_status=native_status,
                       numerical_lower=info['mip_dual_bound'], point_check=check,
                       native_info=info, options={k:lp.get_option(k,type(v)) for k,v in options.items()},
                       native_seconds=lp.get_runtime(), solve_wall_seconds=wall,
                       native_identity=lp.identity, input_readback=readback, diagnostics=diagnostics,
                       exact_tree_bound_claimed=False, warm_start_supplied=False,
                       physical_dc_lower_bound_certified=False)
