from __future__ import annotations

import argparse
from typing import Sequence

from .commands.dev import configure_dev_cmd, dev_cmd
from .commands.info import configure_info_cmd, info_cmd
from .commands.ping import configure_ping_cmd, ping_cmd
from .commands.request import configure_request_cmd, request_cmd
from .commands.run import configure_run_cmd, run_cmd
from .commands.stats import configure_stats_cmd, stats_cmd
from .flags import Flags


def parser() -> argparse.ArgumentParser:
    # Root parser
    parser = argparse.ArgumentParser(prog="micro", description="NATS micro service")
    Flags.add_global_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Run command
    configure_run_cmd(subparsers)
    # Dev command
    configure_dev_cmd(subparsers)
    # Request command
    configure_request_cmd(subparsers)
    # Ping command
    configure_ping_cmd(subparsers)
    # Info command
    configure_info_cmd(subparsers)
    # Stats command
    configure_stats_cmd(subparsers)
    # Return parser
    return parser


def run(args: Sequence[str] | None = None) -> None:
    parsed_args = parser().parse_args(args)
    if parsed_args.command == "run":
        run_cmd(args=parsed_args)
    elif parsed_args.command == "dev":
        dev_cmd(args=parsed_args)
    elif parsed_args.command == "request":
        request_cmd(args=parsed_args)
    elif parsed_args.command == "ping":
        ping_cmd(args=parsed_args)
    elif parsed_args.command == "info":
        info_cmd(args=parsed_args)
    elif parsed_args.command == "stats":
        stats_cmd(args=parsed_args)
    else:
        raise ValueError(f"Unknown command: {parsed_args.command}")
