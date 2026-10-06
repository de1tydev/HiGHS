#!/usr/bin/env python3
"""Portable bound-canonical SCUC MPS exporter; no solver run or source edits.

Call write_model(model, path) on either frozen generator's in-memory Model,
or use this CLI with one of the exact pinned generator revisions below.
"""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

import numpy as np
from scipy.sparse import coo_matrix

VERSION = "scuc-canonical-mps-v2"
GENERATOR_PINS = {source_sha('primal-cache-replay-v4.1/core/scuc/generate.py'): "fixed-output-v1"}
GENERATOR_PATH = Path(__file__).resolve().parent.parent / 'scuc/generate.py'



class ExportError(ValueError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_generator(path):
    path = Path(path).resolve()
    digest = sha256(path)
    if path != GENERATOR_PATH or digest not in GENERATOR_PINS:
        raise ExportError("Generator revision is not one of the frozen lineage pins")
    module = load_module("scuc_generator", path)
    return module, {"path": str(path), "sha256": digest, "revision": GENERATOR_PINS[digest]}


def intended_model(model):
    """Validate the source Model and expose every mathematical field, unrounded."""
    n, m = len(model.names), len(model.rhs)
    if not n or not m:
        raise ExportError("Empty models are outside this SCUC export contract")
    if any(len(getattr(model, field)) != n for field in ("lb", "ub", "obj", "binary")):
        raise ExportError("Inconsistent column arrays")
    if len(model.sense) != m or len(model.ri) != len(model.ci) or len(model.ri) != len(model.val):
        raise ExportError("Inconsistent row or matrix arrays")
    if len(set(model.names)) != n or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,254}", name) for name in model.names):
        raise ExportError("Duplicate or unsupported column name")
    reserved = {"OBJ", "RHS1", "BND1", "NAME", "ROWS", "COLUMNS", "RHS", "BOUNDS", "ENDATA", "MARKER"}
    if any(name in reserved or re.fullmatch(r"R[0-9]+|MARK[0-9]+", name) for name in model.names):
        raise ExportError("Column name collides with serializer namespace")
    lower, upper, cost = (np.asarray(getattr(model, field), dtype=np.float64) for field in ("lb", "ub", "obj"))
    if np.any(np.isnan(lower)) or np.any(np.isnan(upper)) or np.any(lower > upper) or np.any(lower == math.inf) or np.any(upper == -math.inf):
        raise ExportError("Invalid column bound")
    if not np.all(np.isfinite(cost)):
        raise ExportError("Nonfinite objective coefficient")
    if any(type(value) not in (bool, np.bool_) for value in model.binary):
        raise ExportError("Unsupported integrality marker (only bool binary is supported)")
    for j, binary in enumerate(model.binary):
        if binary and (lower[j], upper[j]) not in ((0, 1), (0, 0), (1, 1)):
            raise ExportError("Binary bounds must be [0,1], [0,0], or [1,1]: " + model.names[j])
    rhs = np.asarray(model.rhs, dtype=np.float64)
    if not np.all(np.isfinite(rhs)) or any(s not in ("L", "E", "G") for s in model.sense):
        raise ExportError("Unsupported row sense or nonfinite RHS")
    # Check Python/native integers before int32 coercion can wrap silently.
    if max(n, m, len(model.val)) > 2147483647 or any(type(i) is not int or i < 0 or i >= m for i in model.ri) or any(type(i) is not int or i < 0 or i >= n for i in model.ci):
        raise ExportError('32-bit ABI matrix index/count overflow')
    ri, ci = np.asarray(model.ri, dtype=np.int32), np.asarray(model.ci, dtype=np.int32)
    val = np.asarray(model.val, dtype=np.float64)
    if np.any(ri < 0) or np.any(ri >= m) or np.any(ci < 0) or np.any(ci >= n) or not np.all(np.isfinite(val)) or np.any(val == 0):
        raise ExportError("Invalid matrix index, zero, or nonfinite coefficient")
    matrix = coo_matrix((val, (ri, ci)), shape=(m, n)).tocsc()
    if matrix.nnz != len(val):
        raise ExportError("Duplicate matrix record is unsupported")
    row_lower = np.array([r if s != "L" else -math.inf for s, r in zip(model.sense, rhs)])
    row_upper = np.array([r if s != "G" else math.inf for s, r in zip(model.sense, rhs)])
    return {"num_col": n, "num_row": m, "num_nz": len(val), "sense": 1, "offset": 0.0,
            "col_names": list(model.names), "row_names": [f"R{i}" for i in range(m)],
            "col_lower": lower, "col_upper": upper, "col_cost": cost,
            "row_lower": row_lower, "row_upper": row_upper,
            "integrality": np.asarray(model.binary, dtype=np.int32),
            "a_start": matrix.indptr, "a_index": matrix.indices, "a_value": matrix.data}


def write_model(model, path, meta=None, *, expected=None):
    """Write a new file only. Non-bound serialization matches both v1 writers."""
    expected = intended_model(model) if expected is None else expected
    path = Path(path)
    n, m = expected["num_col"], expected["num_row"]
    starts, indices, values = (expected[field] for field in ("a_start", "a_index", "a_value"))
    with path.open("x", newline="\n") as stream:
        stream.write("NAME          SCUCBENCH\nROWS\n N  OBJ\n")
        for i, sense in enumerate(model.sense):
            stream.write(f" {sense}  R{i}\n")
        stream.write("COLUMNS\n")
        isint, marker = False, 0
        for j, name in enumerate(model.names):
            if model.binary[j] != isint:
                isint = model.binary[j]
                stream.write(f"    MARK{marker}  'MARKER'  '{'INTORG' if isint else 'INTEND'}'\n")
                marker += 1
            stream.write(f"    {name}  OBJ  {model.obj[j]:.17g}\n")
            for z in range(starts[j], starts[j + 1]):
                stream.write(f"    {name}  R{indices[z]}  {values[z]:.17g}\n")
        if isint:
            stream.write(f"    MARK{marker}  'MARKER'  'INTEND'\n")
        stream.write("RHS\n")
        for i, value in enumerate(model.rhs):
            if value:
                stream.write(f"    RHS1  R{i}  {value:.17g}\n")
        stream.write("BOUNDS\n")
        for j, name in enumerate(model.names):
            lo, up = model.lb[j], model.ub[j]
            # FX and BV each define BOTH endpoints. Never serialize both.
            # INTORG/INTEND already preserve the fixed column's integer type.
            if lo == up:
                stream.write(f" FX BND1  {name}  {lo:.17g}\n")
            elif model.binary[j]:
                stream.write(f" BV BND1  {name}\n")
            else:
                if lo == -math.inf:
                    stream.write(f" MI BND1  {name}\n")
                elif lo != 0:
                    stream.write(f" LO BND1  {name}  {lo:.17g}\n")
                if up != math.inf:
                    stream.write(f" UP BND1  {name}  {up:.17g}\n")
        stream.write("ENDATA\n")
    validate_bound_records(path)
    result = dict(meta or {})
    result.update(exporter_version=VERSION, exporter_sha256=sha256(__file__),
                  rows=m, columns=n, binaries=sum(model.binary), nonzeros=len(model.val),
                  fixed_binaries=sum(b and lo == up for b, lo, up in zip(model.binary, model.lb, model.ub)),
                  mps_bytes=path.stat().st_size, mps_sha256=sha256(path), api_fidelity_verified=False)
    return result


def validate_bound_records(path):
    """Reject ambiguous or unsupported records, before invoking the real loader.

    This is a strict validator of this writer's section/marker/bound subset, not
    a general MPS reader or an attempt to repair historical BV+FX files.
    """
    sections = ["NAME", "ROWS", "COLUMNS", "RHS", "BOUNDS", "ENDATA"]
    section, stage, isint = None, -1, False
    columns, seen_sides, seen_markers = {}, {}, set()
    bound_count = 0
    with open(path) as stream:
        for lineno, line in enumerate(stream, 1):
            words = line.split()
            if not words:
                raise ExportError(f"Blank record at line {lineno}")
            if not line[0].isspace():
                key = words[0]
                if stage + 1 >= len(sections) or key != sections[stage + 1]:
                    raise ExportError(f"Unsupported or repeated section at line {lineno}")
                if key != "NAME" and len(words) != 1:
                    raise ExportError(f"Malformed section at line {lineno}")
                if section == "COLUMNS" and isint:
                    raise ExportError("Unclosed INTORG marker")
                stage += 1
                section = key
                continue
            if section == "COLUMNS":
                if len(words) != 3:
                    raise ExportError(f"Malformed column record at line {lineno}")
                name, row, value = words
                if row == "'MARKER'":
                    if name in seen_markers or value not in ("'INTORG'", "'INTEND'") or (value == "'INTORG'") == isint:
                        raise ExportError(f"Malformed or duplicate integer marker at line {lineno}")
                    seen_markers.add(name)
                    isint = value == "'INTORG'"
                elif name in columns:
                    if columns[name] != isint:
                        raise ExportError(f"Ambiguous integer type at line {lineno}")
                else:
                    columns[name] = isint
            elif section == "BOUNDS":
                if len(words) not in (3, 4):
                    raise ExportError(f"Malformed bound record at line {lineno}")
                kind, boundset, name = words[:3]
                sides = {"BV": "lu", "FX": "lu", "MI": "l", "LO": "l", "UP": "u"}.get(kind)
                if sides is None or boundset != "BND1" or name not in columns:
                    raise ExportError(f"Unsupported bound type, set or column at line {lineno}")
                numeric = kind in ("FX", "LO", "UP")
                if len(words) != (4 if numeric else 3):
                    raise ExportError(f"Malformed bound arity at line {lineno}")
                if numeric:
                    try:
                        value = float(words[3])
                    except ValueError as error:
                        raise ExportError(f"Invalid bound number at line {lineno}") from error
                    if not math.isfinite(value):
                        raise ExportError(f"Nonfinite bound record at line {lineno}")
                if kind == "BV" and not columns[name]:
                    raise ExportError("BV outside INTORG is outside this writer's contract")
                if columns[name] and not (kind == "BV" or (kind == "FX" and value in (0, 1))):
                    raise ExportError("Unsupported binary bound representation")
                previous = seen_sides.setdefault(name, set())
                if previous.intersection(sides):
                    raise ExportError(f"Duplicate bound endpoint at line {lineno}: {name}")
                previous.update(sides)
                bound_count += 1
            elif section == "ENDATA" or section is None:
                raise ExportError(f"Unexpected content at line {lineno}")
    if stage != len(sections) - 1:
        raise ExportError("Incomplete MPS sections")
    if any(integral and seen_sides.get(name) != {"l", "u"} for name, integral in columns.items()):
        raise ExportError("Integer column without explicit complete bounds")
    return {"columns": len(columns), "integer_columns": sum(columns.values()), "bound_records": bound_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--generator", required=True)
    parser.add_argument("--mode", choices=("uc", "network", "n1"), required=True)
    parser.add_argument("--hours", type=int)
    parser.add_argument("--pairs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--library", required=True, help="Unchanged HiGHS shared library for mandatory readModel/getLp fidelity check")
    args = parser.parse_args()
    output = Path(args.output)
    for path in (output, Path(str(output) + ".meta.json"), Path(str(output) + ".readback.json"), Path(str(output) + ".readback.log")):
        if path.exists():
            raise ExportError(f"Refusing to overwrite existing artifact: {path}")
    raise ExportError("Direct exporter CLI disabled; use the exact source-guarded transfer stage")
    generator, lineage = load_generator(args.generator)
    if lineage["revision"] == "network-single-point-v1" and args.mode != "network":
        raise ExportError("The frozen network extension CLI is network-only")
    data = generator.read(args.input)
    hours = args.hours or int(data["Parameters"]["Time horizon (h)"])
    if not 1 <= hours <= data["Parameters"]["Time horizon (h)"]:
        raise ExportError("Hours outside source horizon")
    pairs = json.loads(Path(args.pairs).read_text()) if args.pairs else None
    model, netinfo = generator.build(data, hours, args.mode, pairs)
    meta = write_model(model, output, {"input_path": str(Path(args.input).resolve()), "input_sha256": sha256(args.input),
        "generator": lineage, "hours": hours, "mode": args.mode, "network": netinfo,
        "pairs_sha256": sha256(args.pairs) if args.pairs else None,
        "formulation": "custom-three-binary-convex-segments-startup-epigraph-dc-v1"})
    from current_scuc.core.canonical_mps_export.readback import verify_model
    report = verify_model(model, output, args.library, str(output) + ".readback.log")
    Path(str(output) + ".readback.json").write_text(json.dumps(report, indent=2) + "\n")
    meta["api_fidelity_verified"] = report["passed"]
    meta["readback_sha256"] = sha256(str(output) + ".readback.json")
    Path(str(output) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    if not report["passed"]:
        raise SystemExit("FAIL CLOSED: actual HiGHS model does not exactly match source; inspect readback report")


if __name__ == "__main__":
    main()
