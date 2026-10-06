"""Connect fresh full-oracle output to the immutable per-line emitter.

Only the bounded, within-run installed rows live in this module. No archived
points, cuts, factors, starts, line lists or upper endpoints are accepted.
"""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from fractions import Fraction as Q
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import time
import numpy as np

ROOT = PACKAGE_ROOT
EMITTER_SHA = source_sha('adaptive-line-emitter-v1/emitter.py')
path = ROOT / 'science/emitter.py'
if hashlib.sha256(path.read_bytes()).hexdigest() != EMITTER_SHA:
    raise ValueError('Frozen emitter changed')
emitter = load_module('emitter', path)
require, exact = emitter.require, emitter.exact


def fraction(pair):
    require(isinstance(pair, (list, tuple)) and len(pair) == 2
            and all(type(v) is str for v in pair), 'Malformed exact oracle receipt')
    return Q(int(pair[0]), int(pair[1]))


def check_deadline(deadline):
    require(math.isfinite(deadline) and time.monotonic() < deadline,
            'Adaptive support wall deadline exhausted')


def fresh_cache(oracle, metadata, out):
    source = getattr(oracle, 'source_identity', oracle.pins.get('source_sha256'))
    require(source == metadata['source_identity'], 'Fresh oracle/source mismatch')
    require(oracle.full_scope_identity_sha256 == metadata['scope_identity'], 'Fresh cache scope mismatch')
    require(oracle.evaluation_count == 0, 'Previously evaluated oracle cannot initialize adaptive run')
    run = emitter.identity(dict(source=source, scope=metadata['scope_identity'],
                               output=str(Path(out).resolve()), started=time.monotonic_ns()))
    geometry = emitter.identity(dict(endpoints=hashlib.sha256(np.asarray(oracle.endpoints, dtype='<i8').tobytes()).hexdigest(),
                                    weights=hashlib.sha256(np.asarray(oracle.weights, dtype='<f8').tobytes()).hexdigest()))
    coefficients = hashlib.sha256(oracle.lodf.tobytes(order='C')).hexdigest()
    return emitter.ElementaryAdjoints(run_identity=run, source_identity=source,
        scope_identity=metadata['scope_identity'], topology_identity=geometry,
        coefficient_identity=coefficients, buses=len(oracle.buses), solve=oracle.lu.solve)


def cache_receipt(cache):
    return dict(context=list(cache.context), requests=cache.requests, entries=len(cache.cache),
        raw_pi_bytes=cache.raw_bytes, accounted_metadata_bytes=cache.metadata_bytes,
        maximum_requests=emitter.MAX_ADJOINTS, maximum_raw_pi_bytes=emitter.MAX_PI_BYTES,
        maximum_metadata_bytes=emitter.MAX_CACHE_METADATA_BYTES,
        historical_cache_used=False)


def query_data(prepared, evaluated, raw, deadline):
    """Validate/reuse existing query enclosures; no forward solve or row scan."""
    cert = evaluated['certificate']
    require(cert['full_scope_identity_sha256'] == prepared.full_scope_identity_sha256,
            'Adaptive query scope mismatch')
    hours = cert['hour_certificates']
    require(len(hours) == prepared.hours and [r['hour'] for r in hours] == list(range(prepared.hours)),
            'Missing/reordered fresh query hours')
    upper = np.asarray(evaluated['arrays']['line_value_upper'])
    require(upper.dtype == np.float64 and upper.shape == (prepared.hours, len(prepared.lines))
            and np.all(np.isfinite(upper)) and np.all(upper >= 0), 'Invalid full-line upper array')
    qstars, supports = [], []
    for t, record in enumerate(hours):
        check_deadline(deadline)
        q = [exact(raw[j]) - load for j, load in zip(prepared.shed_indices[t], prepared.loads[t])]
        for j, bus in zip(prepared.p_indices[t], prepared.generator_bus):
            q[int(bus)] += exact(raw[j])
        q, imbalance, delta = emitter.v2.balanced_probe(q)
        require(q == [fraction(v) for v in record['qstar']]
                and imbalance == fraction(record['raw_imbalance'])
                and delta == fraction(record['reference_delta']), 'Current raw/query binding mismatch')
        require(sum((exact(v) for v in upper[t]), Q(0)) == fraction(record['value_upper_MW']),
                'Full-line upper receipt mismatch')
        qstars.append(q)
        supports.append(record['selected_rows'])
    return supports, qstars, {(l, t): exact(upper[t, l]) for l in prepared.rated for t in range(prepared.hours)}


def installed_bank_debit(bank, prepared, evaluated, raw, deadline):
    """Exact bank-versus-ideal loss at this raw point, never a box substitute.

    A current theta witness supplies the already-computed exact forward flow.
    Its Qres enclosure is widened by the serialization error of stored flow.
    This is the same debit algebra used by the frozen offline evidence.
    """
    require(len(bank) <= emitter.MAX_BATCHES, 'Historical/oversized support bank')
    emitted_values, ideal_values, comparisons = {}, {}, []
    hours = evaluated['certificate']['hour_certificates']
    lift = evaluated['original_network_lift']
    theta, flow = np.asarray(lift['theta_hat']), np.asarray(lift['flow_hat'])
    require(theta.shape == (prepared.hours, len(prepared.buses))
            and flow.shape == (prepared.hours, len(prepared.lines))
            and np.all(np.isfinite(theta)) and np.all(np.isfinite(flow)), 'Invalid current flow witness')
    witness = {}
    for anchor, saved in enumerate(bank):
        require(len(saved['supports']) == prepared.hours, 'Incomplete bank support hours')
        for row in saved['rows']:
            check_deadline(deadline)
            l, t = row['line'], row['hour']
            selected = [r for r in saved['supports'][t]
                        if r['monitored'] == l and emitter.rational(r['multiplier']) > 0]
            require(selected, 'Bank support lost selected source rows')
            lower, upper = Q(0), Q(0)
            for source_row in selected:
                indices = [l] + ([source_row['outage']] if source_row['kind'] == 'contingency' else [])
                for j in indices:
                    if (t, j) not in witness:
                        a, b = prepared.endpoints[j]
                        f = exact(prepared.weights[j]) * (exact(theta[t, a]) - exact(theta[t, b]))
                        stored = exact(flow[t, j])
                        require(float(f) == float(flow[t, j]), 'Fresh flow serialization mismatch')
                        radius = fraction(hours[t]['Qres']) + abs(stored - f)
                        require(radius >= 0, 'Negative current query radius')
                        witness[t, j] = (stored, radius)
                value, radius = witness[t, l]
                if source_row['kind'] == 'contingency':
                    k = source_row['outage']; d = exact(prepared.lodf[l, k])
                    other, error = witness[t, k]
                    value += d * other; radius += abs(d) * error
                    rating = prepared.emergency[t, l]
                else:
                    require(source_row['kind'] == 'normal', 'Unknown selected kind')
                    rating = prepared.normal[t, l]
                value = source_row['sign'] * value - exact(rating)
                weight = emitter.rational(source_row['multiplier'])
                lower += weight * (value - radius); upper += weight * (value + radius)
            emitted = emitter.affine_value(row, raw)
            key = l, t
            emitted_values[key] = max(emitted_values.get(key, Q(0)), emitted)
            ideal_values[key] = max(ideal_values.get(key, Q(0)), upper)
            comparisons.append(dict(anchor=anchor, line=l, hour=t, emitted_MW=emitted,
                                    ideal_lower_MW=lower, ideal_upper_MW=upper))
    emitted = emitter.PRICE * sum(emitted_values.values(), Q(0))
    ideal = emitter.PRICE * sum(ideal_values.values(), Q(0))
    debit = emitter.cross_query_debit(emitted, ideal)
    check_deadline(deadline)
    return dict(passed=True, installed_anchor_count=len(bank), row_comparisons=comparisons,
        emitted_bank_dollars=emitted, ideal_upper_bank_dollars=ideal, debit_dollars=debit,
        allowance_dollars=100, source_box_debit_used_for_raw_claim=False,
        query_enclosures='current full oracle theta/flow/Qres, no extra solve or scan')


def evaluate_supports(state, prepared, evaluated, raw, bank, cache, deadline):
    supports, qstars, upper = query_data(prepared, evaluated, raw, deadline)
    # Preflight all positive lines before any cache request, even on evaluation5
    # and an otherwise closed endpoint. New columns are never installed here.
    state.preflight(supports, admit=False)
    debit = installed_bank_debit(bank, prepared, evaluated, raw, deadline)
    def pi_provider(selected, c):
        check_deadline(deadline)
        answer = cache.get(selected, c, prepared.endpoints, prepared.weights)
        check_deadline(deadline)
        return answer
    emitted = emitter.emit_batch(state, prepared, supports, raw, qstars, upper, pi_provider, admit=False)
    emitted['supports'] = supports
    check_deadline(deadline)
    return emitted, debit
