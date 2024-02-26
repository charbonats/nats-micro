from __future__ import annotations

import argparse

from nats_contrib.connect_opts import ConnectOption, option

from .utils import Flag


class Flags:
    server = Flag(
        name="server",
        short_option="-s",
        metavar="URL",
        type=str,
        help="NATS server URL",
        env="NATS_SERVER",
        default="nats://localhost:4222",
    )

    max_reconnect = Flag(
        name="max_reconnect",
        metavar="COUNT",
        type=int,
        help="Maximum number of reconnect attempts",
        env="NATS_MAX_RECONNECT",
        default=60,
    )

    reconnect_delay = Flag(
        name="reconnect_delay",
        metavar="SECONDS",
        type=float,
        help="Delay between reconnect attempts",
        env="NATS_RECONNECT_DELAY",
        default=2.0,
    )

    username = Flag(
        name="username",
        metavar="USERNAME",
        type=str,
        help="Username for authentication",
        env="NATS_USERNAME",
        default=None,
    )

    password = Flag(
        name="password",
        metavar="PASSWORD",
        type=str,
        help="Password for authentication",
        env="NATS_PASSWORD",
        default=None,
    )

    token = Flag(
        name="token",
        metavar="TOKEN",
        type=str,
        help="Token for authentication",
        env="NATS_TOKEN",
        default=None,
    )

    @classmethod
    def add_global_options(cls, parser: argparse.ArgumentParser) -> None:
        cls.server.add_as_global_option(parser)
        cls.max_reconnect.add_as_global_option(parser)
        cls.reconnect_delay.add_as_global_option(parser)
        cls.username.add_as_global_option(parser)
        cls.password.add_as_global_option(parser)
        cls.token.add_as_global_option(parser)

    @classmethod
    def add_subcommand_options(cls, parser: argparse.ArgumentParser) -> None:
        cls.server.add_as_subcommand_option(parser)
        cls.max_reconnect.add_as_subcommand_option(parser)
        cls.reconnect_delay.add_as_subcommand_option(parser)
        cls.username.add_as_subcommand_option(parser)
        cls.password.add_as_subcommand_option(parser)
        cls.token.add_as_subcommand_option(parser)

    @classmethod
    def get_connect_options(cls, args: argparse.Namespace) -> list[ConnectOption]:
        connect_options: list[ConnectOption] = [
            option.WithServer(cls.server.get(args)),
            option.WithAllowReconnect(
                max_attempts=cls.max_reconnect.get(args),
                delay_seconds=cls.reconnect_delay.get(args),
            ),
        ]
        if username := cls.username.get(args):
            connect_options.append(option.WithUsername(username))
        if password := cls.password.get(args):
            connect_options.append(option.WithPassword(password))
        if token := cls.token.get(args):
            connect_options.append(option.WithToken(token))
        return connect_options
