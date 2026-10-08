"""Read and back up the Pilot/GAMA baseline without rewriting earlier evidence.

Run from the repository root with python3 -B. The local backup is separate from
Git; it is not an off-host disaster recovery copy. Existing backups are refused.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
SPRINT = ROOT / "experiments/gama_marlin_v1"
PILOT = ROOT / "experiments/gsd_pilot_v1"
BACKUP = ROOT / "artifacts/gama_marlin_v1/baseline_2026_10_08"
SKIP = {"_build", "extscache", "__pycache__", ".cache"}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(base):
    # Explicit pruning prevents traversal of generated trees, including symlinks.
    import os
    for directory, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix != ".pyc" and not path.is_symlink() and path.is_file():
                yield path


def main():
    if BACKUP.exists():
        raise SystemExit(f"Refusing to overwrite baseline backup: {BACKUP}")
    provenance = json.loads((PILOT / "qa/m8_provenance.json").read_text())
    checkpoint = ROOT / provenance["best_checkpoint"]["path"]
    if sha(checkpoint) != provenance["best_checkpoint"]["sha256"]:
        raise RuntimeError("Trained checkpoint does not match Pilot provenance")
    checks = []
    manifest = json.loads((PILOT / "qa/milestone_8_manifest.json").read_text())
    for row in manifest["outputs"]:
        path = PILOT / row["path"]
        checks.append({"path": str(path.relative_to(ROOT)),
                       "passed": path.is_file() and sha(path) == row["sha256"]})
    for name, expected in provenance["file_sha256"].items():
        path = PILOT / name
        checks.append({"path": str(path.relative_to(ROOT)),
                       "passed": path.is_file() and sha(path) == expected})
    dependencies = set()
    for record in provenance["assets"].values():
        for row in record["asset_dependencies"]:
            path = ROOT / row["path"]
            checks.append({"path": row["path"],
                           "passed": path.is_file() and sha(path) == row["sha256"]})
            dependencies.add(path)
    if not all(row["passed"] for row in checks):
        raise RuntimeError(json.dumps([row for row in checks if not row["passed"]]))
    files = set(dependencies)
    for name in ("experiments/gsd_pilot_v1", "source/apps", "source/extensions",
                 "tools", "integrations/gama", "artifacts/gama"):
        files.update(inventory(ROOT / name))
    files.add(ROOT / "Codex-Instructions/Current-Sprint/GAMA_MARLIN_SPRINT_SPECIFICATION.md")
    rows = [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
             "sha256": sha(path)} for path in sorted(files)]
    BACKUP.mkdir(parents=True)
    archive = BACKUP / "pilot_and_source.tar"
    with tarfile.open(archive, "x") as tar:
        for row in rows:
            tar.add(ROOT / row["path"], arcname=row["path"], recursive=False)
    # Verify every archived member by reading its bytes, not just the archive hash.
    with tarfile.open(archive, "r") as tar:
        for row in rows:
            digest = hashlib.sha256()
            with tar.extractfile(row["path"]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != row["sha256"]:
                raise RuntimeError(f"Backup mismatch: {row['path']}")
    saved_checkpoint = BACKUP / "checkpoint/best.pt"
    saved_checkpoint.parent.mkdir()
    shutil.copy2(checkpoint, saved_checkpoint)
    if sha(saved_checkpoint) != provenance["best_checkpoint"]["sha256"]:
        raise RuntimeError("Checkpoint backup verification failed")
    changed = [row["path"] for row in rows if sha(ROOT / row["path"]) != row["sha256"]]
    if changed:
        raise RuntimeError(f"Baseline changed during backup: {changed}")
    result = {
        "status": "passed", "backup_scope": "local_same_disk_not_off_host",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "initial_git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines(),
        "archive": {"path": str(archive.relative_to(ROOT)), "bytes": archive.stat().st_size,
                    "sha256": sha(archive), "all_members_verified": True},
        "checkpoint": {"original": str(checkpoint.relative_to(ROOT)),
                       "backup": str(saved_checkpoint.relative_to(ROOT)),
                       "bytes": checkpoint.stat().st_size, "sha256": sha(saved_checkpoint)},
        "pilot_provenance_checks": checks, "files": rows,
        "files_unchanged_after_backup": True,
    }
    output = SPRINT / "qa/preserved_output_manifest.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    (BACKUP / "preserved_output_manifest.json").write_bytes(output.read_bytes())
    print(json.dumps({"passed": True, "files": len(rows),
                      "pilot_provenance_checks": len(checks),
                      "checkpoint_sha256": result["checkpoint"]["sha256"],
                      "manifest": str(output.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
