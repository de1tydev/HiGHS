#!/usr/bin/env python3
"""Six fixed serial slots: four fresh qualification calls, then two diagnostics."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from parse_probe import combine_models, parse_log

MODEL_HASHES = {
    "dcmulti": "a9552af8f0fd228851352ba60b62a64639f8ffd4a01f217afc095eaac4c29a75",
    "gesa2": "fe43df9f95b79fbceae3b4c5f8a152e9498facf5adf750f6255fe4c693af02c3",
}
PATCH_HASH = "ebf898a0f1b18e956121eedd325352350f57af3e067bde42545b504e1b7151c2"
FIELDS = {
    "status": r"^\s*Status\s+(.+)$",
    "primal": r"^\s*Primal bound\s+(.+)$",
    "dual": r"^\s*Dual bound\s+(.+)$",
    "gap": r"^\s*Gap\s+(.+)$",
    "nodes": r"^\s*Nodes\s+(.+)$",
    "iterations": r"^\s*LP iterations\s+(.+)$",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read_status(text):
    result = {}
    for field, pattern in FIELDS.items():
        matches = re.findall(pattern, text, re.M)
        if not matches:
            raise ValueError("Missing solver field: " + field)
        result[field] = matches[-1].strip()
    if result["status"] != "Optimal":
        raise ValueError("Expected Optimal, received " + result["status"])
    for field in ("primal", "dual"):
        if not math.isfinite(float(result[field])):
            raise ValueError("Nonfinite solver field: " + field)
    gap = float(result["gap"].split("%", 1)[0])
    if not math.isfinite(gap) or gap < 0 or gap > 0.01:
        raise ValueError("Invalid or out-of-tolerance gap")
    for field in ("nodes", "iterations"):
        if not result[field].isdigit():
            raise ValueError("Invalid solver counter: " + field)
    return result


def parity(reference, candidate):
    differences = {
        field: {"official": reference.get(field), "candidate": candidate.get(field)}
        for field in tuple(FIELDS) + ("solution_sha256",)
        if reference.get(field) != candidate.get(field)
    }
    return {"passed": not differences, "differences": differences}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-build", type=Path, required=True)
    p.add_argument("--candidate-build", type=Path, required=True)
    p.add_argument("--official-source", type=Path, required=True)
    p.add_argument("--research-root", type=Path, required=True,
                   help="Published cmir_cache_20261006 directory")
    p.add_argument("--exporter", type=Path, required=True,
                   help="Published export_model.cpp built against the official library")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--highsint-bytes", type=int, choices=(4, 8), default=4)
    a = p.parse_args()
    for name in ("official_build", "candidate_build", "official_source",
                 "research_root", "exporter", "out"):
        setattr(a, name, getattr(a, name).resolve())
    a.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    schedule = [(m, "qualification", arm, 0) for m in MODEL_HASHES
                for arm in ("official", "candidate")]
    schedule += [(m, "observer", "candidate", 2) for m in MODEL_HASHES]
    records = [dict(slot=i + 1, model=m, seed=1, stage=stage, arm=arm,
                    log_dev_level=level, outcome="not_run")
               for i, (m, stage, arm, level) in enumerate(schedule)]
    report = dict(outcome="prepared", schedule=records, exports={},
                  qualification_passed=False, solver_calls_launched=0,
                  budget=dict(native_seconds_per_call=60,
                              outer_seconds_per_call=75, maximum_calls=6,
                              total_native_seconds=360, total_outer_seconds=450),
                  materiality=None)

    def save():
        report["elapsed_total_seconds"] = time.monotonic() - started
        write_json(a.out / "results.json", report)

    save()
    current = None
    try:
        checker_path = a.research_root / "check_primal.py"
        guard_root = a.research_root.parent / "current_scuc"
        guard_path = guard_root / "current_scuc" / "slot_envelope.py"
        patch = Path(__file__).resolve().parent / "combined-diagnostic.patch"
        if sha(patch) != PATCH_HASH:
            raise ValueError("Frozen C++ diagnostic patch hash changed")
        spec = importlib.util.spec_from_file_location("probe_primal_check", checker_path)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        sys.path.insert(0, str(guard_root))
        from current_scuc import slot_envelope as envelope

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (7 * 1024**3, 7 * 1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, envelope.request_stop)
        shared_env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
                          MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
                          PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        builds = {"official": a.official_build, "candidate": a.candidate_build}
        report["provenance"] = {
            "runner_sha256": sha(__file__),
            "parser_sha256": sha(Path(__file__).with_name("parse_probe.py")),
            "patch_sha256": sha(patch), "checker_sha256": sha(checker_path),
            "guard_sha256": sha(guard_path), "exporter_sha256": sha(a.exporter),
            "highsint_bytes": a.highsint_bytes,
            "builds": {arm: dict(path=str(root), binary_sha256=sha(root / "bin/highs"),
                                 library_sha256=sha(root / "lib/libhighs.so"))
                       for arm, root in builds.items()},
        }

        def health():
            mem = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                           if line.startswith("MemAvailable:"))) * 1024
            if mem < 2 * 1024**3 or shutil.disk_usage(a.out).free < 2 * 1024**3:
                raise RuntimeError("Memory/disk headroom below 2 GiB")
            todo, seen, rss = [os.getpid()], set(), 0
            while todo:
                pid = todo.pop()
                if pid in seen:
                    continue
                seen.add(pid)
                todo.extend(envelope.children_of(pid))
                try:
                    status = Path(f"/proc/{pid}/status").read_text().splitlines()
                except FileNotFoundError:
                    continue
                rss += sum(int(line.split()[1]) * 1024 for line in status
                           if line.startswith("VmRSS:"))
            if rss > 6 * 1024**3:
                raise RuntimeError("Process-tree RSS exceeds 6 GiB")

        # Official-library original-matrix readbacks, not optimization calls.
        matrices = {}
        for name, expected in MODEL_HASHES.items():
            case = a.official_source / "check/instances" / (name + ".mps")
            if sha(case) != expected:
                raise ValueError("Input hash mismatch: " + name)
            health()
            matrix = a.out / (name + "-original.json")
            log = a.out / (name + "-export.log")
            export_record = dict(model_sha256=expected, outcome="running")
            report["exports"][name] = export_record
            save()
            export_start = time.monotonic()
            with log.open("xb") as stream:
                exported = subprocess.run(
                    [str(a.exporter), str(case), str(matrix)], stdout=stream,
                    stderr=subprocess.STDOUT, timeout=20,
                    env=dict(shared_env, LD_LIBRARY_PATH=str(a.official_build / "lib")))
            export_record.update(returncode=exported.returncode,
                                 seconds=time.monotonic() - export_start,
                                 log_sha256=sha(log))
            if exported.returncode != 0 or not matrix.is_file():
                export_record["outcome"] = "failed"
                raise ValueError("Official original-matrix export failed: " + name)
            export_record.update(outcome="completed", matrix_sha256=sha(matrix))
            matrices[name] = matrix
            save()

        references, parsed_models = {}, {}
        for current in records:
            name, arm, stage = current["model"], current["arm"], current["stage"]
            if stage == "observer" and not report["qualification_passed"]:
                raise ValueError("All four qualification calls must pass before observers")
            health()
            root = builds[arm]
            case = a.official_source / "check/instances" / (name + ".mps")
            directory = a.out / f"{current['slot']:02d}-{name}-s1-{stage}-{arm}"
            directory.mkdir()
            sol, options, log = (directory / filename for filename in
                                 ("point.sol", "options.txt", "stdout.log"))
            options.write_text(
                "time_limit = 60\nthreads = 2\nparallel = off\nrandom_seed = 1\n"
                "mip_rel_gap = 0.0001\nwrite_solution_to_file = true\n"
                f"solution_file = {sol}\nlog_dev_level = {current['log_dev_level']}\n")
            current.update(outcome="running", directory=str(directory),
                           model_sha256=MODEL_HASHES[name],
                           matrix_sha256=sha(matrices[name]), options_sha256=sha(options),
                           binary_sha256=sha(root / "bin/highs"),
                           library_sha256=sha(root / "lib/libhighs.so"))
            save()
            slot_start = time.monotonic()
            receipt = envelope.supervise(
                [str(root / "bin/highs"), str(case), "--options_file", str(options)],
                dict(shared_env, LD_LIBRARY_PATH=str(root / "lib")), log,
                timeout=74, health_check=health)
            current["process"] = receipt
            current["log_sha256"] = sha(log)
            report["solver_calls_launched"] += int(receipt["runner_launched"])
            write_json(directory / "process-receipt.json", receipt)
            save()
            clean = (receipt["runner_returncode"] == 0
                     and receipt["total_slot_within_timeout"]
                     and receipt["total_slot_elapsed_seconds"] <= 75
                     and not any(receipt[k] for k in (
                         "error", "interruption", "health_check_error",
                         "adopted_checks_killed_and_reaped", "hard_watchdog_killed")))
            if not clean:
                raise ValueError("Guard/process failure in slot " + str(current["slot"]))
            text = log.read_text(errors="replace")
            current.update(read_status(text))
            if not sol.is_file():
                raise ValueError("Missing point in slot " + str(current["slot"]))
            current["solution_sha256"] = sha(sol)
            checked = checker.check(matrices[name], sol)
            # Fail without writing nonstandard NaN/Infinity JSON on bad reports.
            try:
                json.dumps(checked, allow_nan=False)
            except ValueError:
                current["checker_nonfinite_report"] = repr(checked)
                raise ValueError("Nonfinite original-matrix checker report")
            current["check"] = checked
            write_json(directory / "primal-check.json", checked)
            save()
            if not checked.get("passed"):
                raise ValueError("Original-matrix primal check failed")
            if arm == "official":
                references[name] = current
            else:
                current["parity"] = parity(references[name], current)
                save()
                if not current["parity"]["passed"]:
                    raise ValueError("Reference parity mismatch: " + name + "/" + stage)
            if stage == "qualification":
                if re.search(r"^(?:PATH_MIX_|SEP_COST |SEP_SELECTED )", text, re.M):
                    raise ValueError("Unexpected default-off diagnostic output")
            else:
                parsed = parse_log(text, a.highsint_bytes)
                parsed_models[name] = parsed
                write_json(directory / "diagnostics.json", parsed)
                current["diagnostics"] = dict(summary=parsed["summary"],
                                              scopes=parsed["scopes"],
                                              materiality_pass=parsed["materiality_pass"])
            current.update(outcome="completed", whole_arm_seconds=time.monotonic() - slot_start)
            if current["slot"] == 4:
                report["qualification_passed"] = all(r["outcome"] == "completed" for r in records[:4])
            save()
            print(json.dumps({k: current[k] for k in
                              ("slot", "model", "stage", "arm", "outcome")}), flush=True)

        report["materiality"] = combine_models(parsed_models)
        report["all_process_primal_parity_accounting_checks_passed"] = True
        report["materiality"]["external_checks_passed"] = True
        report["materiality"]["gate_pass"] = report["materiality"]["both_models_materiality_pass"]
        report["materiality"]["gate_status"] = (
            "passed_for_separate_reuse_proposal" if report["materiality"]["gate_pass"]
            else "materiality_screen_failed")
        report["outcome"] = "completed"
        save()
        write_json(a.out / "diagnostic-summary.json", report["materiality"])
        return 0
    except Exception as exc:
        report["outcome"] = "stopped"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        for exported in report["exports"].values():
            if exported["outcome"] == "running":
                exported.update(outcome="failed_or_incomplete", error=report["error"])
        if current is not None and current["outcome"] != "completed":
            current.update(outcome="failed_or_incomplete", error=report["error"])
        for record in records:
            if record["outcome"] == "not_run":
                record["not_run_reason"] = "Stopped after: " + report["error"]
        save()
        print(report["error"], file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
