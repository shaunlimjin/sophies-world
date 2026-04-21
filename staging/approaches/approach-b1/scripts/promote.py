#!/usr/bin/env python3
"""Promote an approach to staging, or staging to prod.

Usage:
    python3 scripts/promote.py --from approach-b2-v2 --to staging
    python3 scripts/promote.py --from staging --to prod
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).parent.parent


def validate_promotion(source: str, dest: str) -> None:
    if source != "staging" and dest == "prod":
        print(
            f"Error: cannot promote approach '{source}' directly to prod. "
            "Promote to staging first with --to staging.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_source_dir(repo_root: Path, source: str) -> Path:
    if source == "staging":
        return repo_root / "staging"
    return repo_root / "staging" / "approaches" / source


def get_dest_dir(repo_root: Path, dest: str) -> Path:
    if dest == "prod":
        return repo_root
    return repo_root / "staging"


def compute_diff(source_dir: Path, dest_dir: Path) -> List[Tuple[str, Path, Path]]:
    """Return (action, src_path, dest_path) for files that differ between source and dest.

    Only inspects scripts/ and config/ subdirectories of source_dir.
    """
    changes: List[Tuple[str, Path, Path]] = []
    for subdir in ("scripts", "config"):
        src_sub = source_dir / subdir
        if not src_sub.exists():
            continue
        for src_file in sorted(src_sub.rglob("*")):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(source_dir)
            dest_file = dest_dir / rel
            if not dest_file.exists():
                changes.append(("add", src_file, dest_file))
            elif src_file.read_bytes() != dest_file.read_bytes():
                changes.append(("modify", src_file, dest_file))
    return changes


def apply_promotion(changes: List[Tuple[str, Path, Path]]) -> None:
    for _action, src, dest in changes:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def auto_commit(repo_root: Path, source: str, dest: str) -> None:
    msg = f"chore: promote {source} to {dest}"
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo_root, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote approach → staging or staging → prod")
    parser.add_argument("--from", dest="source", required=True, help="Source: 'staging' or an approach name")
    parser.add_argument("--to", dest="dest", required=True, choices=["staging", "prod"])
    args = parser.parse_args()

    validate_promotion(args.source, args.dest)

    source_dir = get_source_dir(REPO_ROOT, args.source)
    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir = get_dest_dir(REPO_ROOT, args.dest)
    changes = compute_diff(source_dir, dest_dir)

    if not changes:
        print("Nothing to promote — source and destination are already identical.")
        return

    print(f"\nPromotion: {args.source} → {args.dest}")
    for action, _src, dest_file in changes:
        print(f"  {action:6s}  {dest_file.relative_to(REPO_ROOT)}")

    answer = input("\nApply promotion? [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    apply_promotion(changes)
    auto_commit(REPO_ROOT, args.source, args.dest)
    print(f"\nDone. Promoted {args.source} → {args.dest}.")


if __name__ == "__main__":
    main()
