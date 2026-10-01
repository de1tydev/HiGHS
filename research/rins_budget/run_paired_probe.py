#!/usr/bin/env python3
"""Sequential paired fixture screen. Python 3.9+, standard library only.

This measures small bundled fixtures, not a representative SCUC distribution.
No compilation, downloading, or concurrent solving happens in this runner.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

PIN = "73cac48c5340d775a477087198611862559be250"
PACKAGE = Path(__file__).resolve().parent
EXPECTED = {
    "small_mip": 3.236842105263, "flugpl": 1201500, "lseu": 1120,
    "egout": 568.1007, "gt2": 21166, "rgn": 82.2,
    "bell5": 8966406.49152, "sp150x300d": 69, "p0548": 8691,
    "dcmulti": 188182,
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def final_json(stdout):
    """Profiling can prefix native text; the probe JSON is its final JSON line."""
    for line in reversed(stdout.splitlines()):
        if line.startswith("{"):
            value = json.loads(line)
            if isinstance(value, dict):
                return value
    raise ValueError("No probe JSON object in stdout")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="Clean baseline HiGHS checkout at the pinned commit")
    parser.add_argument("--baseline-probe", type=Path, required=True)
    parser.add_argument("--candidate-probe", type=Path,
                        help="Probe linked to the nested-RINS-off build")
    parser.add_argument("--comparison", choices=("global-rins-off", "nested-rins-off"),
                        default="global-rins-off")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New directory; existing directories are never overwritten")
    parser.add_argument("--models", default=",".join(EXPECTED))
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--limit", type=float, default=20.0)
    parser.add_argument("--gap", type=float, default=0.0)
    parser.add_argument("--abs-gap", type=float, default=0.0)
    parser.add_argument("--timeout-grace", type=float, default=20.0)
    args = parser.parse_args()
    try:
        args.seeds = [int(value) for value in args.seeds.split(",")]
    except ValueError:
        parser.error("--seeds must be comma-separated nonnegative integers")
    args.models = args.models.split(",")
    if not args.seeds or any(seed < 0 for seed in args.seeds):
        parser.error("at least one nonnegative seed is required")
    if len(args.seeds) != len(set(args.seeds)):
        parser.error("duplicate seeds are not allowed; use --repeats")
    if not args.models or len(args.models) != len(set(args.models)):
        parser.error("at least one model is required, without duplicates")
    if set(args.models) - EXPECTED.keys():
        parser.error("unknown fixture; choose from " + ",".join(EXPECTED))
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    for name in ("limit", "gap", "abs_gap", "timeout_grace"):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) < 0:
            parser.error(name + " must be finite and nonnegative")
    if args.limit == 0:
        parser.error("--limit must be positive")
    if (args.comparison == "nested-rins-off") != (args.candidate_probe is not None):
        parser.error("--candidate-probe is required only for --comparison nested-rins-off")
    if "HIGHS_PROBE_PROFILE" in os.environ or "HIGHS_RINS_DIAGNOSTICS" in os.environ:
        parser.error("unset profiling/diagnostic environment variables before timing")
    args.source_root = args.source_root.resolve(strict=True)
    args.baseline_probe = args.baseline_probe.resolve(strict=True)
    if args.candidate_probe:
        args.candidate_probe = args.candidate_probe.resolve(strict=True)
    args.output_dir = args.output_dir.resolve()
    return args


def main():
    args = parse_args()
    head = subprocess.check_output(
        ["git", "-C", str(args.source_root), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise SystemExit(f"Expected source {PIN}, found {head}")
    # Package files are allowed in the source tree; tracked source edits are not.
    subprocess.run(["git", "-C", str(args.source_root), "diff", "--exit-code", "HEAD"],
                   check=True)
    instances = args.source_root / "check" / "instances"
    model_hashes = {model: sha256(instances / (model + ".mps")) for model in args.models}
    baseline = {"probe": args.baseline_probe, "options": PACKAGE / "options/default.options"}
    candidate = {
        "probe": args.candidate_probe or args.baseline_probe,
        "options": PACKAGE / ("options/no-rins.options" if args.comparison == "global-rins-off"
                              else "options/default.options"),
    }
    arms = {"default": baseline, args.comparison: candidate}
    # Fail before any solves if inputs are absent or output would overwrite evidence.
    identities = {
        name: {"probe": str(arm["probe"]), "probe_sha256": sha256(arm["probe"]),
               "options": str(arm["options"]), "options_sha256": sha256(arm["options"])}
        for name, arm in arms.items()
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    logs = args.output_dir / "logs"
    logs.mkdir()
    plan = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": head, "source_root": str(args.source_root),
        "probe_source_sha256": sha256(PACKAGE / "milp_probe.cpp"),
        "runner_source_sha256": sha256(__file__), "arms": identities,
        "models_sha256": model_hashes, "seeds": args.seeds, "repeats": args.repeats,
        "comparison": args.comparison, "limit_seconds": args.limit,
        "settings": {"threads": 1, "parallel": "off", "mip_rel_gap": args.gap,
                     "mip_abs_gap": args.abs_gap, "mip_feasibility_tolerance": 1e-6},
        "platform": platform.platform(), "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "thread_environment": {key: os.environ.get(key) for key in
                               ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "ordering": "Sequential pairs; treatment order alternates by repeat + seed index + model index",
        "warmup": "One run per arm on the first selected model, excluded from measured rows",
        "limitations": "Small fixture screen; binary hashes do not prove build/source provenance. "
                       "Keep build manifests. Solver time excludes process startup/model read/checking. "
                       "No independent dual or intermediate-incumbent verification.",
    }
    if args.comparison == "nested-rins-off":
        plan["candidate_patch_sha256"] = sha256(PACKAGE / "nested-rins-off.patch")
    write_json(args.output_dir / "plan.json", plan)

    def run(model, variant, seed, name):
        arm = arms[variant]
        model_path = instances / (model + ".mps")
        if sha256(model_path) != model_hashes[model]:
            raise RuntimeError("Model bytes changed during experiment: " + model)
        command = [str(arm["probe"]), str(model_path), str(arm["options"]),
                   str(seed), str(args.limit), str(args.gap), str(args.abs_gap)]
        record = {"model_name": model, "variant": variant, "seed": seed, "command": command}
        start = time.monotonic()
        stdout, stderr = "", ""
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=args.limit + args.timeout_grace)
            stdout, stderr = process.stdout, process.stderr
            record["returncode"] = process.returncode
            record["result"] = final_json(stdout)
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            record["error"] = "process_timeout"
        except (OSError, ValueError) as exc:
            record["error"] = str(exc)
        record["process_seconds"] = time.monotonic() - start
        (logs / (name + ".stdout.log")).write_text(stdout)
        (logs / (name + ".stderr.log")).write_text(stderr)
        result = record.get("result", {})
        errors = []
        if record.get("returncode") != 0:
            errors.append("probe did not exit successfully")
        if not result.get("independent_feasibility_valid", False):
            errors.append("final original-model primal check did not pass")
        # 'Optimal' with a nonzero stopping gap does not promise this exact optimum.
        if args.gap == 0 and args.abs_gap == 0 and result.get("status") == "Optimal":
            objective = result.get("objective")
            if not isinstance(objective, (int, float)) or not math.isfinite(objective) or abs(
                    objective - EXPECTED[model]) > 1e-6 * (1 + abs(EXPECTED[model])):
                errors.append("objective differs from fixture's expected optimum")
        if "error" in record:
            errors.append(record["error"])
        record["validation_errors"] = errors
        record["target_reached"] = not errors and result.get("status") == "Optimal"
        return record

    warmups = [run(args.models[0], variant, args.seeds[0], "warmup-" + variant)
               for variant in arms]
    write_json(args.output_dir / "warmups.json", warmups)
    if any(row["validation_errors"] for row in warmups):
        raise SystemExit("Warm-up failed; inspect warmups.json. No measured arms were run.")

    rows = []
    with (args.output_dir / "paired_runs.jsonl").open("w") as stream:
        for repeat in range(args.repeats):
            for seed_index, seed in enumerate(args.seeds):
                for model_index, model in enumerate(args.models):
                    variants = list(arms)
                    if (repeat + seed_index + model_index) % 2:
                        variants.reverse()
                    for position, variant in enumerate(variants):
                        name = f"{model}-seed{seed}-repeat{repeat}-{variant}"
                        row = run(model, variant, seed, name)
                        row.update(repeat=repeat, position=position)
                        rows.append(row)
                        stream.write(json.dumps(row, allow_nan=False) + "\n")
                        stream.flush()
                    print(f"Recorded pair: {model}, seed {seed}, repeat {repeat}", flush=True)

    summary = []
    for model in args.models:
        group = [row for row in rows if row["model_name"] == model]
        comparable = all(row["target_reached"] for row in group)
        item = {"model": model, "all_arms_reached_target": comparable, "arms": {}}
        for variant in arms:
            subset = [row for row in group if row["variant"] == variant]
            item["arms"][variant] = {
                "runs": len(subset), "target_reached": sum(row["target_reached"] for row in subset),
                "invalid_or_failed": sum(bool(row["validation_errors"]) for row in subset),
                "median_solver_seconds": statistics.median(
                    row["result"]["solver_seconds"] for row in subset) if comparable else None,
            }
        base = item["arms"]["default"]["median_solver_seconds"]
        other = item["arms"][args.comparison]["median_solver_seconds"]
        item["candidate_over_default"] = other / base if comparable and base > 0 else None
        summary.append(item)
    write_json(args.output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0 if all(row["target_reached"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
