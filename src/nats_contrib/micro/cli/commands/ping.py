from __future__ import annotations

import argparse
import asyncio
import json
from typing import TYPE_CHECKING

from nats_contrib.connect_opts import ConnectOption

from ...client import Client as MicroClient
from ...context import Context
from ..flags import Flags, RequestFlags

if TYPE_CHECKING:
    from ..utils import Subparser


def configure_ping_cmd(parent: Subparser) -> None:
    parser = parent.add_parser("ping", help="Discover services")
    Flags.add_subcommand_options(parser)
    RequestFlags.add_subcommand_options(parser)
    parser.add_argument(
        "service",
        type=str,
        help="Name of service to discover",
        nargs="?",
    )


def ping_cmd(args: argparse.Namespace) -> None:
    service = str(args.service or "")
    # Gather options
    connect_options = Flags.get_connect_options(args)
    max_wait = RequestFlags.timeout.get(args)
    max_count = RequestFlags.max_count.get(args)
    max_interval = RequestFlags.max_interval.get(args)
    # Run the application
    asyncio.run(run(connect_options, service, max_wait, max_count, max_interval))


async def run(
    opts: list[ConnectOption],
    service: str,
    max_wait: float,
    max_count: int | None,
    max_interval: float | None,
) -> None:
    ctx = Context()
    async with ctx:
        await ctx.connect(*opts)
        if ctx.cancelled():
            return
        microclient = MicroClient(ctx.client)
        response = await microclient.ping(
            service or None,
            max_wait=max_wait,
            max_count=max_count,
            max_interval=max_interval,
        )
        print(json.dumps([s.as_dict() for s in response], indent=2))
