#!/usr/bin/env python3
"""Explicit caller-triggered replay of the frozen six-slot v1 protocol."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("official-source", "candidate-source", "official-build", "candidate-build",
                 "research-root", "exporter", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for key, value in vars(args).items():
        setattr(args, key, value.resolve())
    here = Path(__file__).resolve().parent
    provenance = json.loads((here / "PROVENANCE.json").read_text())
    frozen = here / "frozen-source"
    if sha(frozen / "MANIFEST.json") != provenance["frozen_source_manifest_sha256"]:
        raise ValueError("Frozen source manifest changed")
    manifest = json.loads((frozen / "MANIFEST.json").read_text())
    for name, record in manifest["files"].items():
        if sha(frozen / name) != record["sha256"]:
            raise ValueError("Frozen source file changed: " + name)
    for source in (args.official_source, args.candidate_source):
        if git(source, "rev-parse", "HEAD") != provenance["official_commit"]:
            raise ValueError("Source HEAD is not the frozen official commit")
    if git(args.official_source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Official tracked source is not pristine")
    changed = set(git(args.candidate_source, "diff", "HEAD", "--name-only").splitlines())
    if changed != set(provenance["source_file_hashes"]):
        raise ValueError("Candidate must differ only in the two frozen observer files")
    for name, binding in provenance["source_file_hashes"].items():
        if sha(args.official_source / name) != binding["official_sha256"]:
            raise ValueError("Official source hash mismatch: " + name)
        if sha(args.candidate_source / name) != binding["candidate_sha256"]:
            raise ValueError("Candidate source hash mismatch: " + name)
    if git(args.research_root, "rev-parse", "HEAD") != provenance["research_commit"]:
        raise ValueError("Research checkout HEAD is not the recorded published commit")
    for name, binding in provenance["external_replay_dependencies"].items():
        if sha(args.research_root.parent / name) != binding["sha256"]:
            raise ValueError("Published replay dependency changed: " + name)
    for build in (args.official_build, args.candidate_build):
        for name in ("bin/highs", "lib/libhighs.so", "HConfig.h"):
            if not (build / name).is_file():
                raise ValueError("Missing caller-supplied build file: " + name)
    if not args.exporter.is_file():
        raise ValueError("Missing caller-supplied official-library exporter")
    if args.out.exists():
        raise ValueError("Output directory must be new")
    if os.environ.get("PRIMAL_CACHE_CONFIG"):
        raise ValueError("Use a clean environment without an unrelated PRIMAL_CACHE_CONFIG")
    outer = args.out.with_name(args.out.name + ".outer")
    outer.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.research_root.parent / "current_scuc"))
    from current_scuc import slot_envelope
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, slot_envelope.request_stop)
    command = [sys.executable, "-B", str(frozen / "run_probe.py"),
               "--official-source", str(args.official_source),
               "--official-build", str(args.official_build),
               "--candidate-build", str(args.candidate_build),
               "--research-root", str(args.research_root),
               "--exporter", str(args.exporter), "--out", str(args.out),
               "--highsint-bytes", "4"]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0",
                       OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    receipt = slot_envelope.supervise(command, environment, outer / "stdout.log", timeout=599)
    (outer / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    clean = (receipt["runner_returncode"] == 0 and receipt["total_slot_within_timeout"]
             and receipt["total_slot_elapsed_seconds"] <= 600
             and not any(receipt[k] for k in ("error", "interruption", "health_check_error",
                                             "hard_watchdog_killed", "adopted_checks_killed_and_reaped")))
    print("Replay receipts retained. Inspect results.json for the scientific gate decision.")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
