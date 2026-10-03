#!/usr/bin/env python3
"""Verify publication/package/source bytes using only the Python standard library."""
import argparse
import hashlib
import json
from pathlib import Path

PACKAGE_SHA256 = "13d4857ffae6b6565c66d27c2190d8b8829ff1236d79230787c8d2fa50178373"
MEASURED_PACKAGE_SHA256 = "f48ac4f80167e2eb677ad5167864fde02c8208334ef5a7e2c6c3c5ffee28daec"
SOURCE_SHA256 = "efe7df3ad01442deb3be411ea903d24b073db219f62b9d6abe15981e1a0a7cc5"
ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(root, ignore_git=False):
    require(root.is_dir(), "Missing directory: " + str(root))
    result = set()
    for path in root.rglob("*"):
        name = path.relative_to(root)
        if ignore_git and name.parts[0] == ".git":
            continue
        require(not path.is_symlink(), "Symlink is not a frozen regular file: " + str(name))
        if path.is_file():
            result.add(name.as_posix())
        else:
            require(path.is_dir(), "Unexpected filesystem entry: " + str(name))
    return result


def verify_map(root, expected, allowed_extra=(), ignore_git=False):
    require(inventory(root, ignore_git) == set(expected) | set(allowed_extra),
            "Missing or unexpected files in " + str(root))
    for name, expected_hash in expected.items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts,
                "Unsafe manifest filename")
        require(sha(root / relative) == expected_hash, "SHA256 mismatch: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        help="Also verify a pristine, unbuilt official source checkout")
    args = parser.parse_args()
    release = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text())
    verify_map(ROOT, release["files"], ("RELEASE_MANIFEST.json",))
    package = ROOT / "replay"
    require(sha(package / "PACKAGE_MANIFEST.json") == PACKAGE_SHA256,
            "Replay package manifest differs from the published identity")
    manifest = json.loads((package / "PACKAGE_MANIFEST.json").read_text())
    require(len(manifest["files"]) + 1 == 45, "Unexpected replay file count")
    require(sum(name.startswith("payload/") for name in manifest["files"]) == 33,
            "Unexpected replay payload count")
    require(manifest["external_files"] == {}, "Unexpected external package dependency")
    verify_map(package, manifest["files"], ("PACKAGE_MANIFEST.json",))
    equivalence = json.loads((ROOT / "EXECUTABLE_EQUIVALENCE.json").read_text())
    require(equivalence["measured_package_manifest_sha256"] == MEASURED_PACKAGE_SHA256,
            "Unexpected measured package identity")
    require(equivalence["public_package_manifest_sha256"] == PACKAGE_SHA256,
            "Unexpected public package identity")
    changed_docs = {"README.md", "SOURCE_LINEAGE.json", "VALIDATION_PLAN.md"}
    require(set(equivalence["documentation_changes"]) == changed_docs,
            "Unexpected documentation delta")
    unchanged = {name: digest for name, digest in manifest["files"].items()
                 if name not in changed_docs}
    require(len(unchanged) == 41 and unchanged == equivalence["unchanged_files_sha256"],
            "Non-documentation bytes differ from the measured-file record")
    require(sha(package / "SOURCE_TREE.sha256") == SOURCE_SHA256,
            "Unexpected source inventory")
    output = {"publication_files_verified": len(release["files"]) + 1,
              "replay_files_verified": 45, "payload_files_verified": 33,
              "package_manifest_sha256": PACKAGE_SHA256,
              "unchanged_measured_files_verified": len(unchanged),
              "native_import_or_execution": False}
    if args.source is not None:
        expected = {}
        for line in (package / "SOURCE_TREE.sha256").read_text().splitlines():
            digest, name = line.split("  ", 1)
            require(name not in expected, "Duplicate source filename")
            expected[name] = digest
        require(len(expected) == 1006, "Incomplete official source inventory")
        verify_map(args.source.resolve(), expected, ignore_git=True)
        output["source_files_verified"] = len(expected)
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
