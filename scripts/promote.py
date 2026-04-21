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


def compute_diff(
    source_dir: Path, dest_dir: Path, detect_deletions: bool = False
) -> List[Tuple[str, Path, Path]]:
    """Return (action, src_path, dest_path) for files that differ between source and dest.

    Only inspects scripts/ and config/ subdirectories of source_dir (and dest_dir when
    detect_deletions=True). detect_deletions should only be True when source is a full
    snapshot (approach), not when source is a partial overlay (staging).
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

        if detect_deletions:
            dest_sub = dest_dir / subdir
            if dest_sub.exists():
                for dest_file in sorted(dest_sub.rglob("*")):
                    if not dest_file.is_file():
                        continue
                    rel = dest_file.relative_to(dest_dir)
                    if not (source_dir / rel).exists():
                        changes.append(("remove", None, dest_file))

    return changes


def apply_promotion(changes: List[Tuple[str, Path, Path]]) -> None:
    for action, src, dest in changes:
        if action == "remove":
            dest.unlink()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def auto_commit(repo_root: Path, source: str, dest: str, changed_paths: List[Path]) -> None:
    msg = f"chore: promote {source} to {dest}"
    rel_paths = [str(p.relative_to(repo_root)) for p in changed_paths]
    subprocess.run(["git", "add", "--", *rel_paths], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo_root, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote approach → staging or staging → prod")
    parser.add_argument("--from", dest="source", required=True, help="Source: 'staging' or an approach name")
    parser.add_argument("--to", dest="dest", required=True, choices=["staging", "prod"])
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without applying")
    args = parser.parse_args()

    validate_promotion(args.source, args.dest)

    source_dir = get_source_dir(REPO_ROOT, args.source)
    if not source_dir.exists():
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    dest_dir = get_dest_dir(REPO_ROOT, args.dest)
    # Detect deletions only for approach → staging (approach is a full snapshot;
    # staging is a partial overlay so staging → prod must not delete prod-only files).
    detect_deletions = args.source != "staging"
    changes = compute_diff(source_dir, dest_dir, detect_deletions=detect_deletions)

    if not changes:
        print("Nothing to promote — source and destination are already identical.")
        return

    print(f"\nPromotion: {args.source} → {args.dest}")
    for action, _src, dest_file in changes:
        print(f"  {action:6s}  {dest_file.relative_to(REPO_ROOT)}")

    if args.dry_run:
        print("\nDry run — no changes applied.")
        return

    if not args.yes:
        answer = input("\nApply promotion? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    apply_promotion(changes)
    changed_paths = [dest for _, _, dest in changes]
    auto_commit(REPO_ROOT, args.source, args.dest, changed_paths)
    print(f"\nDone. Promoted {args.source} → {args.dest}.")


if __name__ == "__main__":
    main()
