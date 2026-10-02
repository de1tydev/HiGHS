"""Fresh direct-DC separation at a verified current LP point, never a certificate.

The caller must first strict-parse a complete primal, verify source/model/DSO
identity and exact source-derived API readback, and audit every current row,
bound, objective coefficient and integrality declaration. ``identity`` carries
that matrix-check witness, bound to the exact values and artifacts below. A
successful witness is required; this module cannot silently replace that audit.
``separate`` requires a continuous model. ``separate_integer_network`` is an
additional diagnostic for already matrix-checked integer points; it does not
replace the frozen integer source checker.

Proof of selection scope: the source order defines incidence A, weights w and
the reference bus. Each topology is independently factored as
    (A[:, 1:].T diag(w) A[:, 1:]) theta = injection[1:].
Both its reduced residual and all reconstructed nodal balances are checked.
Only one specified outage weight changes to zero, and postflow is diag(w) A
theta. A pair is selected iff some finite source emergency limit is exceeded
by abs(postflow) minus that limit and the ORIGINAL monitored-line/hour overflow.
The eligible universe is the frozen generator's normal-or-emergency-rated
lines crossed with source-listed outages, excluding the outaged line. Thus
selection only requests existing original constraints; no point here proves
integer feasibility, and no omitted pair is declared globally redundant.

No generator, integer checker, optimizer, LODF, stored topology or historical
pair cache is imported. Every call factors the base and every specified outage
afresh. No commitment, startup or shutdown variable is rounded, and the only
cost reconstructed is the original LINEAR objective for consistency.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping

from pair_codec import Universe, PackedPairs, descriptor
from witness_store import WitnessSink

def _load_numerical_dependencies():
    global np, coo_matrix, diags, splu
    import numpy as np
    from scipy.sparse import coo_matrix, diags
    from scipy.sparse.linalg import splu


class SeparationError(ValueError):
    """Fatal malformed input, failed current-model gate or physical residual."""


HASH_FIELDS = ("source_sha256", "model_sha256", "expected_sha256",
               "solution_sha256", "pair_manifest_sha256")


def _finite(value, label):
    if isinstance(value, (bool, str, bytes)):
        raise SeparationError(f"Non-numeric {label}")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SeparationError(f"Non-numeric {label}") from exc
    if not math.isfinite(value):
        raise SeparationError(f"Nonfinite {label}")
    return value


def _at(value, hour, label, *, rating=False):
    if isinstance(value, list):
        if hour >= len(value):
            raise SeparationError(f"Missing hour {hour} in {label}")
        value = value[hour]
    if rating:
        if isinstance(value, (bool, str, bytes)):
            raise SeparationError(f"Non-numeric {label}")
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SeparationError(f"Non-numeric {label}") from exc
        # The frozen source treats either infinity as an absent rating. NaN is
        # corrupt input, never an excuse to silently omit a monitored hour.
        if math.isnan(value):
            raise SeparationError(f"NaN {label}")
        return value
    return _finite(value, label)


def _mapping(value, label, *, nonempty=False):
    if not isinstance(value, Mapping) or (nonempty and not value):
        raise SeparationError(f"Invalid {label}")
    if any(not isinstance(key, str) or not key for key in value):
        raise SeparationError(f"Invalid {label} IDs")
    return value


def point_sha256(values):
    """Bind the current matrix-check witness to normalized finite primal values."""
    _mapping(values, "primal", nonempty=True)
    normalized = {name: _finite(values[name], f"column {name}") for name in sorted(values)}
    return hashlib.sha256(json.dumps(normalized, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def source_data_sha256(data):
    """Bind parsed source INCLUDING its bus/line/generator/contingency order.

    Raw file identity is separately mandatory. Infinity in a source rating is
    permitted by source semantics; source_scope rejects NaNs and bad physics.
    """
    try:
        payload = json.dumps(data, separators=(",", ":"), allow_nan=True)
    except (TypeError, ValueError) as exc:
        raise SeparationError("Source data is not serializable") from exc
    return hashlib.sha256(payload.encode()).hexdigest()


def _pairs(pairs, scope):
    try:
        if isinstance(pairs, PackedPairs):
            if pairs.scope_sha256 != scope['descriptor_sha256']:
                raise SeparationError('Active pair scope identity mismatch')
            return pairs
        return PackedPairs(scope, pairs)
    except ValueError as exc:
        raise SeparationError(str(exc)) from exc


def source_scope(data, hours, *, source_sha256=None):
    """Derive the exact source-order outage IDs and original eligible universe.

    This only validates source fields and enumerates indices; it does not load
    a model, factor a topology or optimize. Production case counts belong to
    the driver's frozen case manifest, allowing independent tiny fixtures here.
    """
    _mapping(data, "source", nonempty=True)
    params = _mapping(data.get("Parameters"), "parameters", nonempty=True)
    if (params.get("Version") != "0.3" or params.get("Time step (min)", 60) != 60 or
            data.get("Price-sensitive loads")):
        raise SeparationError("Unsupported source schema")
    horizon = params.get("Time horizon (h)")
    if (type(hours) is not int or hours < 1 or type(horizon) is not int or hours > horizon):
        raise SeparationError("Invalid source/requested horizon")
    buses = _mapping(data.get("Buses"), "buses", nonempty=True)
    lines = _mapping(data.get("Transmission lines"), "lines", nonempty=True)
    generators = _mapping(data.get("Generators"), "generators", nonempty=True)
    contingencies = _mapping(data.get("Contingencies"), "contingencies")
    reserves = _mapping(data.get("Reserves", {}), "reserves")
    if len(buses) < 2:
        raise SeparationError("Direct DC checker requires at least two buses")
    line_ids = list(lines)
    line_index = {name: index for index, name in enumerate(line_ids)}
    rated, emergency_rated, finite_hours = [], [], {}
    for name, bus in buses.items():
        _mapping(bus, f"bus {name}")
        for hour in range(hours):
            if _at(bus.get("Load (MW)"), hour, f"load {name}") < 0:
                raise SeparationError("Negative source load")
            _at(params.get("Power balance penalty ($/MW)", 1000), hour, "shedding penalty")
    for index, (name, line) in enumerate(lines.items()):
        _mapping(line, f"line {name}")
        source, target = line.get("Source bus"), line.get("Target bus")
        if source not in buses or target not in buses or source == target:
            raise SeparationError(f"Invalid endpoints for line {name}")
        _finite(line.get("Susceptance (S)"), f"susceptance {name}")
        any_normal = False
        finite_hours[index] = []
        for hour in range(hours):
            normal = _at(line.get("Normal flow limit (MW)", math.inf), hour,
                         f"normal rating {name}", rating=True)
            emergency = _at(line.get("Emergency flow limit (MW)", math.inf), hour,
                            f"emergency rating {name}", rating=True)
            any_normal |= math.isfinite(normal)
            if math.isfinite(emergency):
                finite_hours[index].append(hour)
            _at(line.get("Flow limit penalty ($/MW)", 5000), hour, f"overflow penalty {name}")
        if finite_hours[index]:
            emergency_rated.append(index)
        if any_normal or finite_hours[index]:
            rated.append(index)
    for name, generator in generators.items():
        _mapping(generator, f"generator {name}")
        if generator.get("Bus") not in buses:
            raise SeparationError(f"Invalid bus for generator {name}")
        bp, bc = generator.get("Production cost curve (MW)"), generator.get("Production cost curve ($)")
        if not isinstance(bp, list) or not isinstance(bc, list) or len(bp) != len(bc) or len(bp) < 1:
            raise SeparationError(f"Invalid production cost curve for {name}")
        bp = [_finite(v, f"power breakpoint {name}") for v in bp]
        [_finite(v, f"cost breakpoint {name}") for v in bc]
        if any(b <= a for a, b in zip(bp, bp[1:])):
            raise SeparationError(f"Unordered production breakpoints for {name}")
        eligibility = generator.get("Reserve eligibility", [])
        if not isinstance(eligibility, list) or len(eligibility) != len(set(eligibility)):
            raise SeparationError(f"Invalid reserve eligibility for {name}")
        if any(reserve not in reserves for reserve in eligibility):
            raise SeparationError(f"Unknown reserve for {name}")
    for name, reserve in reserves.items():
        _mapping(reserve, f"reserve {name}")
        for hour in range(hours):
            _at(reserve.get("Shortfall penalty ($/MW)", -1), hour, f"reserve penalty {name}")
    outage_ids, outage_lines, outages = [], [], []
    for name, contingency in contingencies.items():
        _mapping(contingency, f"contingency {name}")
        affected = contingency.get("Affected lines")
        if (contingency.get("Affected generators") or contingency.get("Affected units") or
                not isinstance(affected, list) or len(affected) != 1 or affected[0] not in lines):
            raise SeparationError(f"Unsupported contingency {name}")
        outage_ids.append(name)
        outage_lines.append(affected[0])
        outages.append(line_index[affected[0]])
    if len(outages) != len(set(outages)):
        raise SeparationError("Duplicate outage topology in source contingency list")
    scope = {"hours": hours, "buses": list(buses), "generators": list(generators),
            "lines": line_ids, "checked_outage_ids": outage_ids,
            "outage_line_ids": outage_lines, "outage_indices": outages,
            "rated_line_indices": rated, "emergency_rated_line_indices": emergency_rated,
            "source_data_sha256": source_data_sha256(data),
            "finite_emergency_line_hours": sum(len(v) for v in finite_hours.values())}
    if source_sha256 is not None: scope["source_sha256"]=source_sha256
    return descriptor(scope, finite_hours)


def expected_column_names(data, hours, scope=None):
    """Source-derived full names, including non-network columns, without build()."""
    scope = source_scope(data, hours) if scope is None else scope
    names = []
    for name, generator in data["Generators"].items():
        for hour in range(hours):
            names.extend(f"{kind}_{name}_{hour}" for kind in ("u", "y", "z", "p", "sc"))
            names.extend(f"seg_{name}_{hour}_{segment}" for segment in range(len(generator["Production cost curve (MW)"]) - 1))
            names.extend(f"reserve_{reserve}_{name}_{hour}" for reserve in generator.get("Reserve eligibility", []))
    names.extend(f"shed_{name}_{hour}" for name in scope["buses"] for hour in range(hours))
    names.extend(f"short_{name}_{hour}" for name in data.get("Reserves", {}) for hour in range(hours))
    names.extend(f"theta_{name}_{hour}" for name in scope["buses"] for hour in range(hours))
    rated = set(scope["rated_line_indices"])
    for index, name in enumerate(scope["lines"]):
        for hour in range(hours):
            names.append(f"f_{name}_{hour}")
            if index in rated:
                names.append(f"over_{name}_{hour}")
    if len(set(names)) != len(names):
        raise SeparationError("Source produces duplicate column names")
    return names


def _matrix_gate(data, values, hours, active, identity, tolerance, integrality_scope, scope):
    _mapping(values, "primal", nonempty=True)
    names = expected_column_names(data, hours, scope)
    if set(values) != set(names):
        missing, extra = sorted(set(names) - set(values)), sorted(set(values) - set(names))
        raise SeparationError(f"Exact current column-name mismatch: missing={missing[:10]}, extra={extra[:10]}")
    normalized = {name: _finite(values[name], f"column {name}") for name in names}
    _mapping(identity, "current LP identity", nonempty=True)
    if identity.get("hours") != hours or identity.get("active_pairs_sha256") != active.content_sha256():
        raise SeparationError("Current horizon/pair-manifest identity mismatch")
    if identity.get("source_data_sha256") != source_data_sha256(data):
        raise SeparationError("Current parsed-source identity mismatch")
    report = _mapping(identity.get("matrix_check"), "current matrix check", nonempty=True)
    for field in HASH_FIELDS:
        digest = identity.get(field)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SeparationError(f"Missing/invalid current {field}")
        if report.get(field) != digest:
            raise SeparationError(f"Current matrix/artifact hash mismatch: {field}")
    if (report.get("passed") is not True or report.get("exact_column_names") is not True or
            report.get("integrality_scope") != integrality_scope):
        raise SeparationError("Current full matrix check missing, failed or wrong integrality scope")
    checked_tolerance = _finite(report.get("tolerance"), "matrix-check tolerance")
    if checked_tolerance <= 0 or checked_tolerance > tolerance:
        raise SeparationError("Matrix-check tolerance is weaker than separator tolerance")
    maxima = report.get("max_violation_by_category")
    if (not isinstance(maxima, Mapping) or
            set(maxima) != {"row", "lower_bound", "upper_bound", "integrality"} or
            report.get("violations_by_category") != {}):
        raise SeparationError("Incomplete/contradictory current matrix residual audit")
    for category, maximum in maxima.items():
        maximum = _finite(maximum, f"matrix {category} maximum")
        if maximum < 0. or maximum > checked_tolerance:
            raise SeparationError(f"Failed current matrix {category} maximum")
    if report.get("point_sha256") != point_sha256(normalized):
        raise SeparationError("Current matrix/primal point hash mismatch")
    _finite(report.get("linear_objective"), "matrix linear objective")
    try:
        json.dumps(report, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SeparationError("Nonfinite/non-JSON current matrix witness") from exc
    return normalized, report


def _maximum_abs(array, label):
    array = np.asarray(array, dtype=float)
    if not np.isfinite(array).all():
        raise SeparationError(f"Nonfinite {label}")
    return float(np.max(np.abs(array), initial=0.))


def _require_residual(value, label, tolerance):
    value = _finite(value, label)
    if value > tolerance:
        raise SeparationError(f"{label} residual {value:.17g} exceeds {tolerance:.17g}")
    return value


def _direct_topology(incidence, reduced, weights, injection, endpoints, label, tolerance):
    # Verify graph connectivity even for zero injections, where a singular
    # topology can otherwise hide behind an accidentally small residual.
    neighbors = [[] for _ in range(injection.shape[0])]
    for weight, (source, target) in zip(weights, endpoints):
        if weight != 0:
            neighbors[source].append(target)
            neighbors[target].append(source)
    seen, pending = {0}, [0]
    while pending:
        for neighbor in neighbors[pending.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    if len(seen) != injection.shape[0]:
        raise SeparationError(f"Singular/disconnected topology: {label}")
    laplacian = (reduced.T @ diags(weights) @ reduced).tocsc()
    if not np.isfinite(laplacian.data).all():
        raise SeparationError(f"Nonfinite Laplacian: {label}")
    try:
        angles = np.asarray(splu(laplacian).solve(injection[1:]), dtype=float)
    except Exception as exc:
        raise SeparationError(f"Direct factorization/solve failed for {label}: {exc}") from exc
    if angles.shape != injection[1:].shape:
        raise SeparationError(f"Direct angle shape mismatch: {label}")
    _maximum_abs(angles, f"angles {label}")
    flows = weights[:, None] * (reduced @ angles)
    _maximum_abs(flows, f"flows {label}")
    reduced_residual = _require_residual(_maximum_abs(laplacian @ angles - injection[1:],
        f"reduced system {label}"), f"reduced system {label}", tolerance)
    nodal_residual = _require_residual(_maximum_abs(incidence.T @ flows - injection,
        f"full nodal balance {label}"), f"full nodal balance {label}", tolerance)
    return flows, {"reduced_system_MW": reduced_residual, "full_nodal_balance_MW": nodal_residual}


def _linear_cost(data, x, hours, scope):
    components = {"production_linear": 0., "startup_epigraph": 0., "shedding": 0.,
                  "shared_overflow": 0., "reserve_shortfall": 0.}
    for name, generator in data["Generators"].items():
        bp, bc = generator["Production cost curve (MW)"], generator["Production cost curve ($)"]
        for hour in range(hours):
            components["production_linear"] += bc[0] * x[f"u_{name}_{hour}"]
            components["startup_epigraph"] += x[f"sc_{name}_{hour}"]
            for segment in range(len(bp) - 1):
                slope = (bc[segment + 1] - bc[segment]) / (bp[segment + 1] - bp[segment])
                components["production_linear"] += slope * x[f"seg_{name}_{hour}_{segment}"]
    for name in scope["buses"]:
        for hour in range(hours):
            components["shedding"] += x[f"shed_{name}_{hour}"] * _at(data["Parameters"].get("Power balance penalty ($/MW)", 1000), hour, "shedding penalty")
    for index in scope["rated_line_indices"]:
        name = scope["lines"][index]
        for hour in range(hours):
            components["shared_overflow"] += x[f"over_{name}_{hour}"] * _at(data["Transmission lines"][name].get("Flow limit penalty ($/MW)", 5000), hour, "overflow penalty")
    for name, reserve in data.get("Reserves", {}).items():
        for hour in range(hours):
            components["reserve_shortfall"] += x[f"short_{name}_{hour}"] * max(0., _at(reserve.get("Shortfall penalty ($/MW)", -1), hour, "reserve penalty"))
    for name, cost in components.items():
        _finite(cost, f"linear cost component {name}")
    return _finite(sum(components.values()), "source linear objective"), components


def _separate(data, values, hours, active_pairs, *, tolerance, identity, integrality_scope, witness_directory):
    tolerance = _finite(tolerance, "separation tolerance")
    if tolerance <= 0 or tolerance > 1e-5:
        raise SeparationError("Separation tolerance must be positive and no weaker than 1e-5")
    scope = source_scope(data, hours, source_sha256=identity.get("source_sha256") if identity else None)
    universe = Universe(scope)
    active = _pairs(active_pairs, scope)
    x, matrix_report = _matrix_gate(data, values, hours, active, identity, tolerance, integrality_scope, scope)
    _load_numerical_dependencies()
    # Do not reach numerical topology construction before the complete matrix
    # witness has passed and has been bound to this exact source/point/model.
    buses, lines = scope["buses"], scope["lines"]
    bus_index = {name: index for index, name in enumerate(buses)}
    injection = np.zeros((len(buses), hours))
    shed_total = 0.
    for name, bus in data["Buses"].items():
        for hour in range(hours):
            load = _at(bus["Load (MW)"], hour, f"load {name}")
            shed = x[f"shed_{name}_{hour}"]
            _require_residual(max(-shed, shed - load, 0.), "shed bounds", tolerance)
            injection[bus_index[name], hour] = shed - load
            shed_total += shed
    for name, generator in data["Generators"].items():
        for hour in range(hours):
            dispatch = x[f"p_{name}_{hour}"]
            _require_residual(max(-dispatch, 0.), "dispatch nonnegative", tolerance)
            injection[bus_index[generator["Bus"]], hour] += dispatch
    _maximum_abs(injection, "injection")
    system_balance = _require_residual(_maximum_abs(injection.sum(axis=0), "system balance"), "system balance", tolerance)
    rows, columns, coefficients, endpoints, weights = [], [], [], [], []
    for index, name in enumerate(lines):
        line = data["Transmission lines"][name]
        source, target = bus_index[line["Source bus"]], bus_index[line["Target bus"]]
        endpoints.append((source, target))
        rows.extend((index, index)); columns.extend((source, target)); coefficients.extend((1., -1.))
        weights.append(_finite(line["Susceptance (S)"], f"susceptance {name}"))
    incidence = coo_matrix((coefficients, (rows, columns)), shape=(len(lines), len(buses))).tocsr()
    reduced, weights = incidence[:, 1:], np.asarray(weights, dtype=float)
    base, base_residuals = _direct_topology(incidence, reduced, weights, injection, endpoints, "base", tolerance)
    angles = np.asarray([[x[f"theta_{name}_{hour}"] for hour in range(hours)] for name in buses])
    source_flows = np.asarray([[x[f"f_{name}_{hour}"] for hour in range(hours)] for name in lines])
    reference = _require_residual(_maximum_abs(angles[0], "reference angle"), "reference angle", tolerance)
    direct_error = _require_residual(_maximum_abs(base - source_flows, "direct base flow"), "direct base flow", tolerance)
    phase_error = _require_residual(_maximum_abs(weights[:, None] * (incidence @ angles) - source_flows,
        "phase-angle flow"), "phase-angle flow", tolerance)
    source_nodal = _require_residual(_maximum_abs(incidence.T @ source_flows - injection,
        "primal full nodal balance"), "primal full nodal balance", tolerance)
    overflow = np.zeros_like(base)
    for index in scope["rated_line_indices"]:
        name = lines[index]
        overflow[index] = [x[f"over_{name}_{hour}"] for hour in range(hours)]
    _require_residual(max(0., -float(np.min(overflow, initial=0.))), "overflow nonnegative", tolerance)
    base_raw, base_after = 0., 0.
    for index, name in enumerate(lines):
        line = data["Transmission lines"][name]
        for hour in range(hours):
            limit = _at(line.get("Normal flow limit (MW)", math.inf), hour, f"normal rating {name}", rating=True)
            if math.isfinite(limit):
                raw = _finite(abs(base[index, hour]) - limit, "base unrelaxed overload")
                excess = _finite(raw - overflow[index, hour], "base shared-slack excess")
                base_raw, base_after = max(base_raw, raw), max(base_after, excess)
                _require_residual(max(0., excess), "normal line limit", tolerance)
    linear_cost, cost_components = _linear_cost(data, x, hours, scope)
    matrix_cost = matrix_report["linear_objective"]
    objective_error = abs(linear_cost - matrix_cost)
    objective_tolerance = max(tolerance, max(abs(linear_cost), abs(matrix_cost)) * 1e-9)
    _require_residual(objective_error, "original linear objective", objective_tolerance)
    sink = WitnessSink(witness_directory, scope)
    outage_residuals, checked_ids = [], []
    security_raw, security_after, violated_hours, checked_hours = 0., 0., 0, 0
    for outage_id, outage_line, outage in zip(scope["checked_outage_ids"], scope["outage_line_ids"], scope["outage_indices"]):
        outage_weights = weights.copy()
        outage_weights[outage] = 0.
        post, residuals = _direct_topology(incidence, reduced, outage_weights, injection, endpoints, f"outage {outage_id}", tolerance)
        if np.any(post[outage] != 0.):
            raise SeparationError(f"Outaged line carries nonzero flow: {outage_id}")
        checked_ids.append(outage_id)
        outage_residuals.append({"outage_id": outage_id, "outage_line_id": outage_line,
                                "outage_index": outage, **residuals})
        for monitored, name in enumerate(lines):
            if monitored == outage:
                continue
            line, worst = data["Transmission lines"][name], None
            for hour in range(hours):
                limit = _at(line.get("Emergency flow limit (MW)", math.inf), hour,
                            f"emergency rating {name}", rating=True)
                if not math.isfinite(limit):
                    continue
                checked_hours += 1
                raw = _finite(abs(post[monitored, hour]) - limit, "security unrelaxed overload")
                excess = _finite(raw - overflow[monitored, hour], "security shared-slack excess")
                security_raw, security_after = max(security_raw, raw), max(security_after, excess)
                if excess > tolerance:
                    violated_hours += 1
                if worst is None or excess > worst["worst_excess_MW"]:
                    worst = {"pair": [monitored, outage], "monitored_line_id": name,
                             "outage_id": outage_id, "outage_line_id": outage_line,
                             "worst_excess_MW": excess, "hour": hour,
                             "flow_MW": float(post[monitored, hour]), "rating_MW": limit,
                             "shared_overflow_MW": float(overflow[monitored, hour]),
                             "unrelaxed_overload_MW": raw}
            if worst is not None and worst["worst_excess_MW"] > tolerance:
                pair = (monitored, outage)
                if pair not in universe:
                    raise SeparationError("Selected pair outside source-derived universe")
                if pair in active:
                    raise SeparationError(f"Already-active pair still violates: {pair}")
                sink.add(worst)
    if checked_ids != scope["checked_outage_ids"] or checked_hours != scope["eligible_pair_hours"]:
        raise SeparationError("Exact outage/eligible-hour coverage mismatch")
    artifacts = sink.finalize()
    result = {"separation_only": True, "upper_bound_eligible": False, "certificate_bound_eligible": False,
              "integrality_scope": integrality_scope, "hours": hours, "tolerance": tolerance,
              "checked_outage_ids": checked_ids, "outage_line_ids": scope["outage_line_ids"],
              "outage_indices": scope["outage_indices"], "scope_sha256": scope["descriptor_sha256"],
              "eligible_pair_count": scope["eligible_pair_count"], "checked_pair_hours": checked_hours,
              "outages_checked": len(checked_ids), "violated_pairs": artifacts["violated_pairs"],
              "per_pair_worst": artifacts["witnesses"], "violated_line_hours": violated_hours,
              "max_violation_after_shared_slack_MW": security_after,
              "max_unrelaxed_overload_MW": security_raw,
              "base_unrelaxed_overload_MW": base_raw, "base_max_after_shared_slack_MW": base_after,
              "total_shed_MWh": shed_total, "max_overflow_MW": float(np.max(overflow, initial=0.)),
              "total_shared_overflow_MW_hours": float(np.sum(overflow)),
              "linear_model_cost": linear_cost, "linear_cost_components": cost_components,
              "objective_error": objective_error, "objective_consistency_tolerance": objective_tolerance,
              "matrix_check": dict(matrix_report), "active_pairs_sha256": active.content_sha256(),
              "base_residuals": {**base_residuals, "system_balance_MW": system_balance,
                                 "reference_angle": reference, "direct_base_flow_MW": direct_error,
                                 "phase_angle_flow_MW": phase_error, "primal_full_nodal_balance_MW": source_nodal},
              "outage_residuals": outage_residuals, "factorizations_per_call": 1 + len(checked_ids),
              "source_data_sha256": identity["source_data_sha256"],
              **{field: identity[field] for field in HASH_FIELDS}}
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SeparationError("Nonfinite/non-JSON separation output") from exc
    return result


def separate(data, values, hours, active_pairs, *, tolerance=1e-5, identity=None, witness_directory=None):
    """Separate a verified current CONTINUOUS LP; no source integer acceptance."""
    return _separate(data, values, hours, active_pairs, tolerance=tolerance,
                     identity=identity, integrality_scope="continuous", witness_directory=witness_directory)


def separate_integer_network(data, values, hours, active_pairs, *, tolerance=1e-5, identity=None, witness_directory=None):
    """Direct network evidence at a verified MIP point; frozen check still needed."""
    return _separate(data, values, hours, active_pairs, tolerance=tolerance,
                     identity=identity, integrality_scope="original_integer", witness_directory=witness_directory)
