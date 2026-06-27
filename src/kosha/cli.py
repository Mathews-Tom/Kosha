"""Command-line entrypoint for Kosha.

This is a thin surface for the milestone-1 verification target: ``--version``
prints the package version and bare invocation prints help. Domain commands are
added by later milestones.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from kosha import __version__


def build_parser() -> argparse.ArgumentParser:
    """Construct the root argument parser."""
    parser = argparse.ArgumentParser(
        prog="kosha",
        description="Self-maintaining OKF knowledge engine.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. With no subcommand, print help and exit cleanly."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
