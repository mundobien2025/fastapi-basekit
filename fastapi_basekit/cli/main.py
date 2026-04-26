"""basekit CLI entry point.

Usage:
    basekit init                # interactive cookiecutter prompts
    basekit init --no-input     # use defaults (good for CI / testing)
    basekit init -o /path       # output dir
    basekit init --extra-context key=value
    basekit version
"""

from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence


def _template_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "project"


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        from cookiecutter.main import cookiecutter
    except ImportError:
        print(
            "Error: cookiecutter not installed. Install with:\n"
            "    pip install fastapi-basekit[init]\n"
            "or  pip install cookiecutter",
            file=sys.stderr,
        )
        return 1

    extra_context: dict[str, str] = {}
    for kv in args.extra_context or []:
        if "=" not in kv:
            print(f"Bad --extra-context value (expected key=value): {kv}", file=sys.stderr)
            return 2
        k, v = kv.split("=", 1)
        extra_context[k.strip()] = v.strip()

    try:
        cookiecutter(
            template=str(_template_dir()),
            no_input=args.no_input,
            output_dir=args.output_dir,
            extra_context=extra_context,
            overwrite_if_exists=args.overwrite,
        )
    except Exception as exc:  # pragma: no cover - cookiecutter raises various
        print(f"basekit init failed: {exc}", file=sys.stderr)
        return 3
    return 0


def _cmd_version(_: argparse.Namespace) -> int:
    try:
        v = metadata.version("fastapi-basekit")
    except metadata.PackageNotFoundError:  # pragma: no cover
        v = "unknown"
    print(f"fastapi-basekit {v}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="basekit",
        description="fastapi-basekit project scaffolder.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Scaffold a new project from the basekit template.")
    init.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Where to write the new project (default: current directory).",
    )
    init.add_argument(
        "--no-input",
        action="store_true",
        help="Skip interactive prompts; use cookiecutter.json defaults.",
    )
    init.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output directory if it already exists.",
    )
    init.add_argument(
        "--extra-context",
        action="append",
        metavar="KEY=VALUE",
        help="Override one cookiecutter variable; repeatable.",
    )
    init.set_defaults(func=_cmd_init)

    version = sub.add_parser("version", help="Print the installed version.")
    version.set_defaults(func=_cmd_version)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
