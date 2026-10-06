#!/usr/bin/env python3
"""Strict, standard-library-only parser for the frozen v1 allocation probe.

The materiality screen is not the complete diagnostic gate: the caller must
separately verify process, primal, reference and retained-evidence checks.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

UINT64_MAX = (1 << 64) - 1
INT32_MAX = (1 << 31) - 1
INT64_MAX = (1 << 63) - 1
TIME_TOLERANCE = 1e-9
VECTOR_NAMES = ("inds", "solval", "upper", "isIntegral", "rhs", "tmpUpper", "tmpSolval")
COUNTERS = (
    "eligible", "transform_calls", "transform_failed", "first_transform_failed",
    "rhs_first_rejected", "rhs_order_rejected", "truncated", "mixing_ready",
    "requested_rows", "usable_rows", "capacity_anomalies",
)
TIMES = (
    "scratch_init_seconds", "scratch_destroy_seconds", "path_body_seconds",
    "clock_pair_seconds",
)
VECTOR_COUNTERS = (
    "inferred_growth_requests", "requested_payload_bytes",
    "new_capacity_payload_bytes", "final_capacity_payload_bytes",
    "max_capacity_payload_bytes",
)
COST_FIELDS = set(COUNTERS + TIMES + (
    "submip", "depth", "num_col", "num_row", "clock_pair_samples",
))
VECTOR_FIELDS = set(VECTOR_COUNTERS + ("submip", "depth", "name"))
SEP_FIELDS = {"name", "submip", "depth", "seconds", "pool_delta", "lp_iterations"}
SEP_NAMES = {"implied", "clique", "tableau", "path", "modk", "machine", "lp_resolve"}
UINT_RE = re.compile(r"[0-9]+\Z", re.ASCII)
INT_RE = re.compile(r"-?[0-9]+\Z", re.ASCII)
FLOAT_RE = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z", re.ASCII)
EXTERNAL_CHECKS = [
    "process_guard_and_resource_bounds", "independent_original_matrix_primal_objective",
    "fresh_same_seed_reference_comparison", "required_evidence_and_schedule",
]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _uint(value, field, maximum=UINT64_MAX):
    _require(isinstance(value, str) and UINT_RE.fullmatch(value) is not None,
             f"{field}: expected an unsigned decimal integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid integer") from exc
    _require(result <= maximum, f"{field}: integer overflow or domain violation")
    return result


def _seconds(value, field):
    _require(isinstance(value, str) and FLOAT_RE.fullmatch(value) is not None,
             f"{field}: expected finite nonnegative seconds")
    result = float(value)
    _require(math.isfinite(result) and result >= 0,
             f"{field}: expected finite nonnegative seconds")
    return result


def _signed(value, field, bits):
    _require(isinstance(value, str) and INT_RE.fullmatch(value) is not None,
             f"{field}: expected a signed decimal integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid integer") from exc
    _require(-(1 << (bits - 1)) <= result < (1 << (bits - 1)),
             f"{field}: signed integer overflow")
    return result


def _fields(line, tag, expected):
    tokens = line.split()
    _require(tokens and tokens[0] == tag, f"malformed {tag} record")
    fields = {}
    for token in tokens[1:]:
        _require(token.count("=") == 1, f"malformed {tag} field {token!r}")
        key, value = token.split("=", 1)
        _require(key and value and key not in fields, f"empty or duplicate {tag} field {key!r}")
        fields[key] = value
    _require(set(fields) == expected,
             f"{tag}: missing fields {sorted(expected - set(fields))}; "
             f"unexpected fields {sorted(set(fields) - expected)}")
    return fields


def _scope(fields):
    fields["submip"] = _uint(fields["submip"], "submip", 1)
    fields["depth"] = _uint(fields["depth"], "depth", INT32_MAX)
    return fields


def _cost(line, highsint_bytes):
    fields = _scope(_fields(line, "PATH_MIX_COST", COST_FIELDS))
    limit = (1 << (8 * highsint_bytes - 1)) - 1
    for key in ("num_col", "num_row"):
        fields[key] = _uint(fields[key], key, limit)
    _require(fields["num_col"] + fields["num_row"] <= limit,
             "num_col + num_row overflows the configured HighsInt reserve expression")
    for key in COUNTERS:
        fields[key] = _uint(fields[key], key)
    fields["clock_pair_samples"] = _uint(fields["clock_pair_samples"], "clock_pair_samples", INT32_MAX)
    for key in TIMES:
        fields[key] = _seconds(fields[key], key)
    return fields


def _vector(line):
    fields = _scope(_fields(line, "PATH_MIX_VECTOR", VECTOR_FIELDS))
    _require(fields["name"] in VECTOR_NAMES, "unknown vector name")
    for key in VECTOR_COUNTERS:
        fields[key] = _uint(fields[key], key)
    return fields


def _separator(line):
    fields = _scope(_fields(line, "SEP_COST", SEP_FIELDS))
    _require(fields["name"] in SEP_NAMES, "unknown separator name")
    fields["seconds"] = _seconds(fields["seconds"], "seconds")
    fields["pool_delta"] = _signed(fields["pool_delta"], "pool_delta", 32)
    fields["lp_iterations"] = _signed(fields["lp_iterations"], "lp_iterations", 64)
    return fields


def _same_scope(left, right):
    return all(left[key] == right[key] for key in ("submip", "depth"))


def _finite_sum(values, label):
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label}: nonfinite aggregate") from exc
    _require(math.isfinite(result), f"{label}: nonfinite aggregate")
    return result


def _count_sum(values, label):
    result = sum(values)
    _require(result <= UINT64_MAX, f"{label}: aggregate counter overflow")
    return result


def _validate_group(group, highsint_bytes):
    cost, vectors, separator = group["cost"], group["vectors"], group["separator_cost"]
    _require(list(vectors) == list(VECTOR_NAMES), "missing, duplicate or reordered vector records")
    _require(_same_scope(cost, separator), "companion path separator scope mismatch")
    _require(cost["capacity_anomalies"] == 0, "capacity_anomalies must equal zero")
    _require(cost["clock_pair_samples"] == 32, "clock_pair_samples must equal 32")
    _require(cost["first_transform_failed"] <= cost["transform_failed"],
             "first_transform_failed exceeds transform_failed")
    _require(cost["mixing_ready"] <= cost["eligible"], "mixing_ready exceeds eligible")
    _require(cost["usable_rows"] <= cost["requested_rows"], "usable_rows exceeds requested_rows")
    _require(cost["truncated"] == cost["transform_failed"] + cost["rhs_first_rejected"] + cost["rhs_order_rejected"],
             "truncated partition identity failed")
    _require(cost["eligible"] <= cost["transform_calls"] <= cost["requested_rows"],
             "eligible <= transform_calls <= requested_rows failed")
    span = _finite_sum((cost["scratch_init_seconds"], cost["scratch_destroy_seconds"]), "scratch spans")
    _require(span <= cost["path_body_seconds"] + TIME_TOLERANCE,
             "setup plus destruction exceeds path-body span")
    _require(cost["path_body_seconds"] <= separator["seconds"] + TIME_TOLERANCE,
             "path-body span exceeds companion separator span")
    widths = dict(zip(VECTOR_NAMES, (highsint_bytes, 8, 8, 1, 8, 8, 8)))
    for name in VECTOR_NAMES:
        vector, width = vectors[name], widths[name]
        _require(_same_scope(cost, vector), f"{name}: vector scope mismatch")
        growth = vector["inferred_growth_requests"]
        requested = vector["requested_payload_bytes"]
        new = vector["new_capacity_payload_bytes"]
        final = vector["final_capacity_payload_bytes"]
        maximum = vector["max_capacity_payload_bytes"]
        for key in VECTOR_COUNTERS[1:]:
            _require(vector[key] % width == 0, f"{name}: {key} is not element-width aligned")
        _require(new >= requested, f"{name}: new-capacity payload is below requested payload")
        _require(final <= new, f"{name}: final payload exceeds summed new-capacity payload")
        _require(maximum <= final, f"{name}: maximum capacity exceeds final-capacity sum")
        _require((growth != 0 or new == final == requested == maximum == 0),
                 f"{name}: payload without a growth request")
        _require(growth == 0 or (new > 0 and maximum > 0),
                 f"{name}: growth request without capacity")
        if name in VECTOR_NAMES[:5]:
            _require(growth == cost["eligible"], f"{name}: growth count must equal eligible")
            elements = (cost["requested_rows"] if name == "rhs" else
                        cost["eligible"] * (cost["num_col"] + cost["num_row"]))
            expected = elements * width
            _require(expected <= UINT64_MAX, f"{name}: expected requested payload overflows uint64")
            _require(requested == expected, f"{name}: requested-payload identity failed")
        else:
            _require(growth <= cost["transform_calls"], f"{name}: growth exceeds transform_calls")
    _require(vectors["tmpUpper"]["inferred_growth_requests"] == vectors["tmpSolval"]["inferred_growth_requests"],
             "temporary-vector growth counts disagree")


def _aggregate(groups):
    counts = {key: _count_sum((group["cost"][key] for group in groups), key) for key in COUNTERS}
    times = {key: _finite_sum((group["cost"][key] for group in groups), key) for key in TIMES}
    vectors = {}
    for name in VECTOR_NAMES:
        vectors[name] = {}
        for key in VECTOR_COUNTERS:
            values = [group["vectors"][name][key] for group in groups]
            vectors[name][key] = (max(values, default=0) if key == "max_capacity_payload_bytes"
                                  else _count_sum(values, f"{name}.{key}"))
    scratch = _finite_sum((times["scratch_init_seconds"], times["scratch_destroy_seconds"]), "S")
    proxy = _finite_sum((2 * group["cost"]["eligible"] *
                         (group["cost"]["clock_pair_seconds"] / group["cost"]["clock_pair_samples"])
                         for group in groups), "O")
    path = times["path_body_seconds"]
    ratio = scratch / path if path > 0 else None
    _require(ratio is None or math.isfinite(ratio), "nonfinite S/P")
    checks = {
        "eligible_at_least_32": counts["eligible"] >= 32,
        "setup_destroy_at_least_5ms": scratch >= 0.005,
        "setup_destroy_at_least_10_clock_proxy": scratch >= 10 * proxy,
        "setup_destroy_fraction_at_least_5pct": ratio is not None and ratio >= 0.05,
        "first_five_requests_valid": True,
    }
    return {
        "invocation_count": len(groups), "A": counts["eligible"], "S": scratch,
        "P": path, "O": proxy, "S_over_P": ratio,
        "counters": counts, "times": times, "vectors": vectors,
        "separator_path_seconds": _finite_sum((g["separator_cost"]["seconds"] for g in groups), "separator_path_seconds"),
        "clock_pair_samples": _count_sum((g["cost"]["clock_pair_samples"] for g in groups), "clock_pair_samples"),
        "materiality_checks": checks, "materiality_pass": all(checks.values()),
    }


def parse_log(text, highsint_bytes=4):
    """Return complete validated groups and scope aggregates, or raise ValueError.

    Other solver output is ignored outside the contiguous cost-plus-seven-vector
    group. A later matching SEP_COST name=path closes each invocation. Repeated
    identical invocations are valid: the observer has no global invocation ID.
    Missing/extra fields, duplicate records within a group and orphan path
    companions are errors. No timing is subtracted from any other timing.
    """
    _require(isinstance(text, str), "log text must be a string")
    _require(type(highsint_bytes) is int and highsint_bytes in (4, 8), "highsint_bytes must be 4 or 8")
    groups, other_separators = [], []
    pending = None
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        tag = line.split(None, 1)[0] if line else ""
        try:
            if pending is not None and len(pending["vectors"]) < 7:
                _require(tag == "PATH_MIX_VECTOR", "interrupted or incomplete contiguous vector group")
            if tag == "PATH_MIX_COST":
                _require(pending is None, "new cost record before previous companion path record")
                cost = _cost(line, highsint_bytes)
                pending = {"index": len(groups), "line_number": line_number,
                           "submip": cost["submip"], "depth": cost["depth"],
                           "cost": cost, "vectors": {}, "raw_lines": [raw_line]}
            elif tag == "PATH_MIX_VECTOR":
                _require(pending is not None, "orphan vector record")
                vector = _vector(line)
                index = len(pending["vectors"])
                _require(index < 7 and vector["name"] == VECTOR_NAMES[index],
                         "missing, duplicate or reordered vector records")
                pending["vectors"][vector["name"]] = vector
                pending["raw_lines"].append(raw_line)
            elif tag == "SEP_COST":
                separator = _separator(line)
                if separator["name"] == "path":
                    _require(pending is not None, "orphan or duplicate companion path record")
                    pending["separator_cost"] = separator
                    pending["separator_line_number"] = line_number
                    pending["raw_lines"].append(raw_line)
                    _validate_group(pending, highsint_bytes)
                    groups.append(pending)
                    pending = None
                else:
                    _require(pending is None, "another separator precedes the pending path companion")
                    other_separators.append({"line_number": line_number, "record": separator, "raw_line": raw_line})
            elif any(marker in line for marker in ("PATH_MIX", "SEP_COST")):
                raise ValueError("malformed diagnostic record")
        except ValueError as exc:
            raise ValueError(f"line {line_number}: {exc}") from exc
    _require(pending is None, "incomplete invocation at end of log; vectors or path companion missing")
    _require(bool(groups), "no complete allocation-probe invocations found")
    summary = _aggregate(groups)
    by_depth, by_scope_depth = {}, {}
    for depth in sorted({group["depth"] for group in groups}):
        by_depth[str(depth)] = _aggregate([group for group in groups if group["depth"] == depth])
    for submip, depth in sorted({(g["submip"], g["depth"]) for g in groups}):
        key = f"{'submip' if submip else 'main'}:{depth}"
        by_scope_depth[key] = _aggregate([g for g in groups if (g["submip"], g["depth"]) == (submip, depth)])
    return {
        "schema_version": 1, "highsint_bytes": highsint_bytes,
        "element_width_bytes": dict(zip(VECTOR_NAMES, (highsint_bytes, 8, 8, 1, 8, 8, 8))),
        "accounting_valid": True, "invocations": groups, "summary": summary,
        "scopes": {"main": _aggregate([g for g in groups if g["submip"] == 0]),
                   "submip": _aggregate([g for g in groups if g["submip"] == 1]),
                   "by_depth": by_depth, "by_scope_depth": by_scope_depth},
        "other_separator_records": other_separators,
        "materiality_pass": summary["materiality_pass"],
        "external_checks_required": list(EXTERNAL_CHECKS),
        "interpretation": "O is an empty-clock-pair proxy; S is not pure or wholly avoidable allocation time.",
    }


def combine_models(models):
    """Combine exactly the two frozen models; never infer external gate checks."""
    _require(isinstance(models, dict) and set(models) == {"dcmulti", "gesa2"},
             "combine_models requires exactly dcmulti and gesa2")
    for name, parsed in models.items():
        _require(isinstance(parsed, dict) and parsed.get("schema_version") == 1 and
                 parsed.get("accounting_valid") is True and bool(parsed.get("invocations")),
                 f"{name}: not a valid parsed probe log")
        _require(type(parsed.get("materiality_pass")) is bool, f"{name}: missing materiality result")
    _require(models["dcmulti"]["highsint_bytes"] == models["gesa2"]["highsint_bytes"],
             "model HighsInt widths disagree")
    passed = all(model["materiality_pass"] for model in models.values())
    return {
        "schema_version": 1, "models": {name: models[name] for name in ("dcmulti", "gesa2")},
        "both_models_accounting_valid": True, "both_models_materiality_pass": passed,
        "gate_pass": None if passed else False,
        "gate_status": "external_checks_required" if passed else "materiality_screen_failed",
        "external_checks_required": list(EXTERNAL_CHECKS),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", help="UTF-8 solver log, or - for stdin")
    parser.add_argument("--highsint-bytes", type=int, choices=(4, 8), default=4)
    parser.add_argument("--output", help="write JSON to this path instead of stdout")
    args = parser.parse_args(argv)
    try:
        text = sys.stdin.read() if args.log == "-" else Path(args.log).read_text(encoding="utf-8")
        result = parse_log(text, highsint_bytes=args.highsint_bytes)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
    except (ValueError, OSError) as exc:
        print(f"invalid probe log: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
