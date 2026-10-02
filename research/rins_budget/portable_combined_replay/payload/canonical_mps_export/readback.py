#!/usr/bin/env python3
"""Read-only ctypes binding and exact source-to-loaded HiGHS fidelity audit.

No Highs_run, presolve, model mutation, or tolerance-based acceptance occurs.
Signatures are from highs/interfaces/highs_c_api.h. HighsInt is c_int32 and
the library-reported ABI width MUST be four bytes before any array call.
"""
import ctypes as C
import hashlib
from pathlib import Path
import re

import numpy as np

from export_v2 import intended_model, sha256, validate_bound_records

ARRAY_FIELDS = ("col_lower", "col_upper", "col_cost", "row_lower", "row_upper", "integrality", "a_start", "a_index", "a_value")
SCALAR_FIELDS = ("num_col", "num_row", "num_nz", "sense", "offset")


def symbol_provenance(library, names):
    """Resolve actual bound function addresses to their Linux ELF DSO via dladdr."""
    class DlInfo(C.Structure):
        _fields_ = [("filename", C.c_char_p), ("base", C.c_void_p), ("symbol", C.c_char_p), ("address", C.c_void_p)]
    process = C.CDLL(None)
    dladdr = process.dladdr
    dladdr.restype = C.c_int
    dladdr.argtypes = [C.c_void_p, C.POINTER(DlInfo)]
    result = {}
    for name in names:
        info = DlInfo()
        if dladdr(C.cast(getattr(library, name), C.c_void_p), C.byref(info)) == 0 or not info.filename:
            raise RuntimeError("Cannot establish actual loaded DSO for " + name)
        path = Path(info.filename.decode()).resolve()
        result[name] = {"path": str(path), "sha256": sha256(path), "symbol": info.symbol.decode() if info.symbol else None}
    return result


def load_model(path, library, log_path):
    """Diagnostic raw API read: returns warnings and actual data without masking.

    Acceptance belongs to compare_loaded/verify_model. Raw reads deliberately
    permit warning status so old-bug reproduction can inspect lost bounds.
    """
    if Path(log_path).exists():
        raise FileExistsError(log_path)
    # The C name-getter has no buffer-length argument. Bound the input tokens
    # before loading so every returned row/column name fits our buffer safely.
    with open(path, "rb") as stream:
        for line in stream:
            if any(len(token) >= 4096 for token in line.split()):
                raise ValueError("MPS token exceeds the readback name-buffer contract")
    I, D, P = C.c_int32, C.c_double, C.c_void_p
    IP, DP = C.POINTER(I), C.POINTER(D)
    lib = C.CDLL(str(Path(library).resolve()))
    signatures = {
        "Highs_create": (P, []), "Highs_destroy": (None, [P]),
        "Highs_getSizeofHighsInt": (I, [P]), "Highs_version": (C.c_char_p, []),
        "Highs_setBoolOptionValue": (I, [P, C.c_char_p, I]),
        "Highs_setStringOptionValue": (I, [P, C.c_char_p, C.c_char_p]),
        "Highs_readModel": (I, [P, C.c_char_p]),
        "Highs_getNumCol": (I, [P]), "Highs_getNumRow": (I, [P]), "Highs_getNumNz": (I, [P]),
        "Highs_getHessianNumNz": (I, [P]), "Highs_getInfinity": (D, [P]),
        "Highs_getLp": (I, [P, I, IP, IP, IP, IP, DP, DP, DP, DP, DP, DP, IP, IP, DP, IP]),
        "Highs_getColName": (I, [P, I, C.c_char_p]), "Highs_getRowName": (I, [P, I, C.c_char_p]),
    }
    for name, (restype, argtypes) in signatures.items():
        function = getattr(lib, name)
        function.restype, function.argtypes = restype, argtypes
    supplied_path, supplied_sha = str(Path(library).resolve()), sha256(library)
    provenance = symbol_provenance(lib, ("Highs_create", "Highs_readModel", "Highs_getLp", "Highs_getColName", "Highs_getRowName"))
    if any(item["path"] != supplied_path or item["sha256"] != supplied_sha for item in provenance.values()):
        raise RuntimeError("Bound C API symbols do not originate in the supplied library")
    handle = lib.Highs_create()
    if not handle:
        raise RuntimeError("Highs_create failed")
    result = {"library_path": supplied_path, "library_sha256": supplied_sha, "loaded_symbol_provenance": provenance,
              "highs_version": lib.Highs_version().decode(), "mps_sha256": sha256(path)}
    def checked(status, action):
        if status != 0:
            raise RuntimeError(f"{action}: unexpected status {status}")
    try:
        size = lib.Highs_getSizeofHighsInt(handle)
        if size != C.sizeof(I):
            raise RuntimeError(f"HighsInt ABI width {size}, expected c_int32")
        result["highs_int_bytes"] = size
        checked(lib.Highs_setBoolOptionValue(handle, b"log_to_console", 0), "disable console log")
        checked(lib.Highs_setBoolOptionValue(handle, b"output_flag", 1), "enable diagnostic output")
        checked(lib.Highs_setStringOptionValue(handle, b"log_file", str(Path(log_path).resolve()).encode()), "set log path")
        result["read_status"] = lib.Highs_readModel(handle, str(Path(path).resolve()).encode())
        if result["read_status"] < 0:
            raise RuntimeError(f"Highs_readModel failed: {result['read_status']}")
        n, m, nz = lib.Highs_getNumCol(handle), lib.Highs_getNumRow(handle), lib.Highs_getNumNz(handle)
        result["hessian_num_nz"] = lib.Highs_getHessianNumNz(handle)
        result["infinity"] = lib.Highs_getInfinity(handle)
        arrays = {name: np.zeros(length, dtype=np.int32 if name in ("integrality", "a_start", "a_index") else np.float64)
                  for name, length in (("col_cost", n), ("col_lower", n), ("col_upper", n), ("row_lower", m), ("row_upper", m),
                                       ("integrality", n), ("a_start", n + 1), ("a_index", nz), ("a_value", nz))}
        ni, mi, nzi, sense, offset = I(), I(), I(), I(), D()
        ptr = lambda name: arrays[name].ctypes.data_as(IP if arrays[name].dtype == np.int32 else DP)
        checked(lib.Highs_getLp(handle, 1, C.byref(ni), C.byref(mi), C.byref(nzi), C.byref(sense), C.byref(offset),
                                ptr("col_cost"), ptr("col_lower"), ptr("col_upper"), ptr("row_lower"), ptr("row_upper"),
                                ptr("a_start"), ptr("a_index"), ptr("a_value"), ptr("integrality")), "Highs_getLp")
        if (ni.value, mi.value, nzi.value) != (n, m, nz):
            raise RuntimeError("Dimensions changed during readback")
        # C API copies n start entries; the documented nnz supplies the final endpoint.
        arrays["a_start"][n] = nz
        result.update(num_col=n, num_row=m, num_nz=nz, sense=sense.value, offset=offset.value, **arrays)
        for field, size, getter in (("col_names", n, lib.Highs_getColName), ("row_names", m, lib.Highs_getRowName)):
            result[field] = []
            for i in range(size):
                buffer = C.create_string_buffer(4096)
                checked(getter(handle, i, buffer), field)
                result[field].append(buffer.value.decode())
    finally:
        lib.Highs_destroy(handle)
    result["log_path"] = str(Path(log_path).resolve())
    result["log_sha256"] = sha256(log_path)
    log = Path(log_path).read_text()
    result["diagnostics"] = [line for line in log.splitlines() if re.search(r"warning|error|ignored|dropped", line, re.I)]
    if sha256(library) != supplied_sha:
        raise RuntimeError("Library bytes changed during readback")
    return result


def array_digest(array):
    array = np.asarray(array)
    dtype = "<i4" if array.dtype.kind in "ib" else "<f8"
    return hashlib.sha256(array.astype(dtype, copy=False).tobytes()).hexdigest()


def compare_loaded(expected, loaded):
    failures, fields = [], {}
    if loaded["read_status"] != 0:
        failures.append(f"Highs_readModel returned non-OK status {loaded['read_status']}")
    if loaded["diagnostics"]:
        failures.append("Model-definition diagnostics are fatal: " + " | ".join(loaded["diagnostics"]))
    if loaded["hessian_num_nz"] != 0:
        failures.append("Unexpected quadratic objective")
    for field in SCALAR_FIELDS:
        passed = expected[field] == loaded[field]
        fields[field] = {"passed": bool(passed), "expected": expected[field], "loaded": loaded[field]}
        if not passed:
            failures.append("Mismatch: " + field)
    for field in ("col_names", "row_names"):
        a, b = expected[field], loaded[field]
        passed = a == b
        fields[field] = {"passed": passed, "count": len(a),
                         "expected_sha256": hashlib.sha256("\n".join(a).encode()).hexdigest(),
                         "loaded_sha256": hashlib.sha256("\n".join(b).encode()).hexdigest()}
        if not passed:
            failures.append("Mismatch: " + field)
    for field in ARRAY_FIELDS:
        a, b = np.asarray(expected[field]), np.asarray(loaded[field])
        # HiGHS infinity is documented by its API; do not use a loose tolerance.
        if field in ("col_lower", "col_upper", "row_lower", "row_upper"):
            a = np.where(a == np.inf, loaded["infinity"], np.where(a == -np.inf, -loaded["infinity"], a))
        passed = a.shape == b.shape and np.array_equal(a, b)
        details = {"passed": bool(passed), "count_expected": int(a.size), "count_loaded": int(b.size),
                   "expected_sha256": array_digest(a), "loaded_sha256": array_digest(b)}
        if not passed:
            failures.append("Mismatch: " + field)
            if a.shape == b.shape:
                mismatch = np.flatnonzero(a != b)
                details["mismatch_count"] = len(mismatch)
                details["first_mismatches"] = [{"index": int(i), "expected": float(a[i]), "loaded": float(b[i]),
                    **({"column": expected["col_names"][i]} if field.startswith("col_") or field == "integrality" else {})} for i in mismatch[:10]]
        fields[field] = details
    return {"passed": not failures, "comparison": "exact elementwise equality; only API infinity normalization",
            "fields": fields, "failures": failures, "read_status": loaded["read_status"],
            "diagnostics": loaded["diagnostics"], "hessian_num_nz": loaded["hessian_num_nz"],
            **{field: loaded[field] for field in ("library_path", "library_sha256", "loaded_symbol_provenance", "highs_version", "highs_int_bytes", "mps_sha256", "log_path", "log_sha256")},
            "optimization_or_presolve_called": False}


def verify_expected(expected, path, library, log_path):
    """Audit an existing canonical MPS against a complete strict parsed model.

    The caller owns independent construction of expected, using the same keys
    returned by intended_model. This supports fixed-commitment continuous LPs.
    No expected field is inferred from the loaded API model.
    """
    record_audit = validate_bound_records(path)
    result = compare_loaded(expected, load_model(path, library, log_path))
    result["bound_record_audit"] = record_audit
    result["checker_sha256"] = sha256(__file__)
    return result


def verify_model(model, path, library, log_path):
    """Fail-closed acceptance report for a source Model and its actual API load."""
    return verify_expected(intended_model(model), path, library, log_path)
