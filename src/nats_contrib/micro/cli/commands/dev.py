from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Iterable

from nats_contrib.connect_opts import ConnectOption

from ...context import Context
from ..flags import Flags

if TYPE_CHECKING:
    from ..utils import Subparser


def configure_dev_cmd(parent: Subparser) -> None:
    parser = parent.add_parser("dev", help="Run the service")
    Flags.add_subcommand_options(parser)
    parser.add_argument(
        "setup",
        type=str,
        help=(
            "Import path to the setup function. "
            "The value can also be a valid file path to a Python "
            "file containing a setup function. "
            "In such case, the setup function must be named 'setup'."
        ),
    )
    parser.add_argument(
        "--watch",
        action="append",
        nargs="?",
        metavar="DIRECTORY",
        help="Watch directory for changes (default: working directory)",
    )


def dev_cmd(args: argparse.Namespace) -> None:
    # Import setup function
    setup = _import(args.setup)
    # Gather options
    connect_options = Flags.get_connect_options(args)
    # Run the application
    watch_directories = args.watch
    if not watch_directories:
        watch_directories = [os.getcwd()]
    asyncio.run(
        run_with_watcher(
            watch_directories,
            connect_options,
            setup,
        )
    )


async def run_with_watcher(
    watch_directories: list[str],
    connect_options: Iterable[ConnectOption],
    setup: Callable[[Context], Coroutine[None, None, None]],
) -> None:

    while True:
        async with Context() as ctx:
            ctx.trap_signal()
            watcher = _Watcher(ctx, *watch_directories)
            await ctx.connect(*connect_options)
            # Context can be cancelled at any time
            if ctx.cancelled():
                return
            await ctx.wait_for(setup(ctx))
            # Context can be cancelled at any time
            if ctx.cancelled():
                return
            await watcher.next_change()
            if not ctx.cancelled():
                continue
            return


class _Watcher:
    def __init__(
        self,
        ctx: Context,
        *path: str,
    ) -> None:
        try:
            import watchfiles
        except (ImportError, ModuleNotFoundError):
            print(
                "watchfiles must be installed in order to use the dev command",
                file=sys.stderr,
            )
            sys.exit(1)
        self.ctx = ctx
        self.path = path
        for p in self.path:
            if not Path(p).is_dir():
                raise ValueError(f"Path {p} is not a directory")
        self.iterator = watchfiles.awatch(*self.path)  # type: ignore

    async def _next_change(self) -> set[tuple[Any, str]]:
        return await self.iterator.__anext__()

    async def next_change(
        self,
    ) -> set[tuple[Any, str]] | None:
        next_task = asyncio.create_task(self._next_change())
        wait_task = asyncio.create_task(self.ctx.wait())
        await asyncio.wait([next_task, wait_task], return_when=asyncio.FIRST_COMPLETED)
        for task in [next_task, wait_task]:
            if not task.done():
                task.cancel()
        await asyncio.wait([next_task, wait_task], return_when=asyncio.ALL_COMPLETED)
        if next_task.done() and not next_task.cancelled():
            return next_task.result()
        return None


def _import(path: str) -> Callable[[Context], Coroutine[None, None, None]]:
    filename = Path(path)
    if filename.is_file():
        mod = filename.resolve(True).stem
        parent = filename.parent.resolve(True).as_posix()
        sys.path.insert(0, parent)
        setup = getattr(importlib.import_module(mod), "setup")
    else:
        try:
            mod, func = path.rsplit(":", 1)
        except ValueError:
            raise ValueError(f"Invalid setup (not an import path): {path}")
        fileparts = mod.split(".")
        fileparts[-1] += ".py"
        filepath = Path(*fileparts)
        if filepath.is_file():
            mod = filepath.stem
            parent = filepath.parent.resolve(True).as_posix()
            sys.path.insert(0, parent)
            setup = getattr(importlib.import_module(mod), func)
        else:
            setup = getattr(importlib.import_module(mod), func)
    if setup is None:
        raise ValueError(f"Could not import {path}")
    if not callable(setup):
        raise ValueError(f"{path} is not callable")
    return setup
