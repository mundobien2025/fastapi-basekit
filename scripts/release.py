#!/usr/bin/env python3
"""
release.py — single-command release helper for fastapi-basekit.

Usage:
    python scripts/release.py 0.3.0                  # full release (PyPI + docs)
    python scripts/release.py 0.3.0 --no-docs        # PyPI only (manual dispatch later)
    python scripts/release.py 0.3.0 --docs-only      # docs only (no PyPI)
    python scripts/release.py 0.3.0 --dry-run        # show what would change
    python scripts/release.py --bump patch           # auto-increment from current
    python scripts/release.py --bump minor
    python scripts/release.py --bump major

What it does (default mode):
    1. Validate semver + clean working tree
    2. Bump version in pyproject.toml, plugin.json, marketplace.json
    3. Prepend changelog stub to CHANGELOG.md
    4. Commit "chore: release vX.Y.Z"
    5. Create annotated tag vX.Y.Z
    6. git push origin <branch> --follow-tags
    7. Print URLs to monitor the workflow

The remote publish.yml workflow handles PyPI + docs deployment.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PLUGIN = ROOT / "plugin.json"
MARKETPLACE = ROOT / "marketplace.json"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def fail(msg: str, code: int = 1) -> None:
    print(f"\033[31m✗ {msg}\033[0m", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    print(f"\033[36m→ {msg}\033[0m")


def ok(msg: str) -> None:
    print(f"\033[32m✓ {msg}\033[0m")


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True, cwd=ROOT)


def current_version() -> str:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def bump_semver(current: str, kind: str) -> str:
    parts = current.split(".")
    if len(parts) != 3:
        fail(f"Cannot bump non-standard semver: {current}")
    major, minor, patch = (int(p) for p in parts)
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    fail(f"Unknown bump kind: {kind}")


def update_pyproject(version: str, dry: bool) -> None:
    text = PYPROJECT.read_text()
    new = re.sub(
        r'^(version\s*=\s*)"[^"]*"',
        f'\\1"{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if new == text:
        fail("Could not patch pyproject.toml — version line not found")
    if not dry:
        PYPROJECT.write_text(new)
    ok(f"pyproject.toml → {version}")


def update_json(path: Path, version: str, dry: bool, label: str) -> None:
    data = json.loads(path.read_text())
    if "version" in data:
        data["version"] = version
    elif "plugins" in data and isinstance(data["plugins"], list):
        for p in data["plugins"]:
            p["version"] = version
    else:
        fail(f"{path.name}: no version field found")
    if not dry:
        path.write_text(json.dumps(data, indent=2) + "\n")
    ok(f"{label} → {version}")


def update_changelog(version: str, dry: bool) -> None:
    if not CHANGELOG.exists():
        info("CHANGELOG.md missing — skipping")
        return
    text = CHANGELOG.read_text()
    if f"## {version}" in text or f"## [{version}]" in text:
        info(f"CHANGELOG already mentions {version} — skipping")
        return
    today = date.today().isoformat()
    stub = f"## {version} — {today}\n\n- TODO: describe changes\n\n"
    # Insert after first heading line
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = i + 1
            break
    new_text = "".join(lines[:insert_at]) + "\n" + stub + "".join(lines[insert_at:])
    if not dry:
        CHANGELOG.write_text(new_text)
    ok(f"CHANGELOG.md → stub for {version} prepended")


def assert_clean_tree() -> None:
    res = run(["git", "status", "--porcelain"], capture=True)
    if res.stdout.strip():
        fail("Working tree not clean. Commit or stash before releasing:\n" + res.stdout)


def assert_tag_free(version: str) -> None:
    tag = f"v{version}"
    res = run(["git", "tag", "-l", tag], capture=True)
    if res.stdout.strip() == tag:
        fail(f"Tag {tag} already exists locally. Pick a different version.")
    res = run(["git", "ls-remote", "--tags", "origin", tag], capture=True, check=False)
    if res.returncode == 0 and tag in res.stdout:
        fail(f"Tag {tag} already exists on remote. Pick a different version.")


def current_branch() -> str:
    res = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture=True)
    return res.stdout.strip()


def commit_and_tag(version: str, mode: str) -> None:
    tag = f"v{version}"
    suffix = {
        "full": "",
        "no-docs": " [skip-docs]",
        "docs-only": " [docs-only]",
    }[mode]
    msg = f"chore: release {tag}{suffix}"
    run(["git", "add", "pyproject.toml", "plugin.json", "marketplace.json", "CHANGELOG.md"], check=False)
    run(["git", "commit", "-m", msg])
    run(["git", "tag", "-a", tag, "-m", msg])
    ok(f"Committed + tagged {tag}")


def push(version: str) -> None:
    branch = current_branch()
    run(["git", "push", "origin", branch, "--follow-tags"])
    ok(f"Pushed {branch} + tag v{version}")


def dispatch_workflow(version: str, deploy_docs: bool, pypi: bool) -> None:
    """Use gh CLI to fire workflow_dispatch instead of relying on tag."""
    if not subprocess.run(["which", "gh"], capture_output=True).stdout.strip():
        fail("gh CLI required for --no-docs / --docs-only modes")
    args = [
        "gh", "workflow", "run", "publish.yml",
        "-f", f"version={version}",
        "-f", f"deploy_docs={'true' if deploy_docs else 'false'}",
        "-f", f"pypi={'true' if pypi else 'false'}",
    ]
    run(args)
    ok(f"Dispatched publish.yml — pypi={pypi} deploy_docs={deploy_docs}")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command release helper.")
    parser.add_argument("version", nargs="?", help="Target version (e.g. 0.3.0)")
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Auto-increment from current version (mutually exclusive with positional)",
    )
    parser.add_argument(
        "--no-docs",
        action="store_true",
        help="Tag-based release WITHOUT docs deploy. Bumps + commits + tags as usual but tag message contains [skip-docs]; publish.yml still runs but you'd dispatch manually for PyPI-only behavior. To be 100% docs-free, use --pypi-only.",
    )
    parser.add_argument(
        "--pypi-only",
        action="store_true",
        help="Bump + commit (NO tag, NO push). Then dispatch publish.yml via gh CLI with deploy_docs=false.",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Bump + commit (NO tag, NO push). Then dispatch publish.yml via gh CLI with pypi=false.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing or running git",
    )
    parser.add_argument(
        "--no-changelog",
        action="store_true",
        help="Do not prepend stub to CHANGELOG.md",
    )
    args = parser.parse_args()

    # Resolve version
    if args.bump and args.version:
        fail("Use either positional version OR --bump, not both")
    if args.bump:
        version = bump_semver(current_version(), args.bump)
        info(f"--bump {args.bump}: {current_version()} → {version}")
    elif args.version:
        version = args.version
    else:
        fail("Pass version: scripts/release.py 0.3.0  (or --bump patch|minor|major)")

    if not SEMVER.match(version):
        fail(f"Invalid semver: {version}")

    cur = current_version()
    if version == cur:
        fail(f"Version unchanged ({cur}). Nothing to release.")

    # Decide mode
    mutually_exclusive = sum([args.pypi_only, args.docs_only])
    if mutually_exclusive > 1:
        fail("--pypi-only and --docs-only are mutually exclusive")

    if args.pypi_only:
        mode = "no-docs"
    elif args.docs_only:
        mode = "docs-only"
    else:
        mode = "full"

    info(f"Mode: {mode}  | Current: {cur}  → New: {version}  | Dry: {args.dry_run}")

    # Pre-flight
    if not args.dry_run:
        assert_clean_tree()
        assert_tag_free(version)

    # Bump files
    update_pyproject(version, args.dry_run)
    update_json(PLUGIN, version, args.dry_run, "plugin.json")
    update_json(MARKETPLACE, version, args.dry_run, "marketplace.json")
    if not args.no_changelog:
        update_changelog(version, args.dry_run)

    if args.dry_run:
        info("Dry run — no git actions taken.")
        return

    if mode == "full":
        # Tag-based release: tag triggers publish.yml automatically
        commit_and_tag(version, mode)
        push(version)
        print()
        ok("Release dispatched. Monitor:")
        print(f"  Actions: https://github.com/mundobien2025/fastapi-basekit/actions")
        print(f"  PyPI:    https://pypi.org/project/fastapi-basekit/{version}/")
        major_minor = ".".join(version.split(".")[:2])
        print(f"  Docs:    https://mundobien2025.github.io/fastapi-basekit/{major_minor}/")
        return

    # PyPI-only or docs-only: commit but do NOT tag — dispatch via gh
    msg = f"chore: bump v{version} ({mode})"
    run(["git", "add", "pyproject.toml", "plugin.json", "marketplace.json", "CHANGELOG.md"], check=False)
    run(["git", "commit", "-m", msg])
    run(["git", "push", "origin", current_branch()])
    ok(f"Committed + pushed (no tag, mode={mode})")

    if mode == "no-docs":
        dispatch_workflow(version, deploy_docs=False, pypi=True)
    else:  # docs-only
        dispatch_workflow(version, deploy_docs=True, pypi=False)


if __name__ == "__main__":
    main()
