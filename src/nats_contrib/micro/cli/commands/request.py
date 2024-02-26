from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

from nats_contrib.connect_opts import ConnectOption

from ... import sdk
from ...client import Client as MicroClient
from ..flags import Flags

if TYPE_CHECKING:
    from ..utils import Subparser


def configure_request_cmd(parent: Subparser) -> None:
    parser = parent.add_parser("request", help="Send a request")
    Flags.add_subcommand_options(parser)
    parser.add_argument(
        "subject",
        type=str,
        help="Subject to send request to",
        nargs=1,
    )
    parser.add_argument(
        "payload",
        type=str,
        help="Payload to send with the request",
        nargs="?",
    )


def request_cmd(args: argparse.Namespace) -> None:
    subject = str(args.subject[0])
    payload = str(args.payload or "")
    # Gather options
    connect_options = Flags.get_connect_options(args)
    # Run the application
    asyncio.run(run(connect_options, subject, payload))


async def run(
    opts: list[ConnectOption],
    subject: str,
    payload: str,
) -> None:
    ctx = sdk.Context()
    async with ctx:
        await ctx.connect(*opts)
        if ctx.cancelled():
            return
        microclient = MicroClient(ctx.client)
        response = await microclient.request(subject, payload.encode())
        print(response.data.decode())
