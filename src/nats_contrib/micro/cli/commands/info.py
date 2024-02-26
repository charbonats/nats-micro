from __future__ import annotations

import argparse
import asyncio
import json
from typing import TYPE_CHECKING

from nats_contrib.connect_opts import ConnectOption

from ... import sdk
from ...client import Client as MicroClient
from ..flags import Flags

if TYPE_CHECKING:
    from ..utils import Subparser


def configure_info_cmd(parent: Subparser) -> None:
    parser = parent.add_parser(
        "info", help="Discover services with detailed information"
    )
    Flags.add_subcommand_options(parser)
    parser.add_argument(
        "service",
        type=str,
        help="Name of service to discover",
        nargs="?",
    )


def info_cmd(args: argparse.Namespace) -> None:
    service = str(args.service or "")
    # Gather options
    connect_options = Flags.get_connect_options(args)
    # Run the application
    asyncio.run(run(connect_options, service))


async def run(
    opts: list[ConnectOption],
    service: str,
) -> None:
    ctx = sdk.Context()
    async with ctx:
        await ctx.connect(*opts)
        if ctx.cancelled():
            return
        microclient = MicroClient(ctx.client)
        response = await microclient.info(service or None)
        print(json.dumps([s.as_dict() for s in response], indent=2))
