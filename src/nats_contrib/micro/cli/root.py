from __future__ import annotations

import argparse
from typing import Sequence

from .commands.run import configure_run_cmd, run_cmd
from .flags import Flags


def parser() -> argparse.ArgumentParser:
    # Root parser
    parser = argparse.ArgumentParser(prog="micro", description="NATS micro service")
    Flags.add_global_options(parser)
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Run command
    configure_run_cmd(subparsers)
    # Return parser
    return parser


def run(args: Sequence[str] | None = None) -> None:
    parsed_args = parser().parse_args(args)
    if parsed_args.command == "run":
        run_cmd(args=parsed_args)
    else:
        raise ValueError(f"Unknown command: {parsed_args.command}")
