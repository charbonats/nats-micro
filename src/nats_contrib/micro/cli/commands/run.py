from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Coroutine

from ... import sdk
from ..flags import Flags
from ..utils import Flag

if TYPE_CHECKING:
    import watchfiles

    from ..utils import Subparser
else:
    try:
        import watchfiles
    except ImportError:
        watchfiles = None


watch = Flag(
    name="watch",
    metavar="DIRECTORY",
    type=str,
    help="Watch directory for changes",
    env="WATCH_DIR",
    default=None,
    repeat=True,
)


def configure_run_cmd(parent: Subparser) -> None:
    parser = parent.add_parser("run", help="Run the service")
    Flags.add_subcommand_options(parser)
    parser.add_argument(
        "setup",
        type=str,
        help="Import path to the setup function",
    )
    watch.add_as_subcommand_option(parser)


def run_cmd(args: argparse.Namespace) -> None:
    # Import setup function
    setup = _import(args.setup)
    # Gather options
    connect_options = Flags.get_connect_options(args)
    # Run the application
    watch_directories = watch.get(args)
    if watch_directories:
        if watchfiles is None:  # pyright: ignore[reportUnnecessaryComparison]
            raise ImportError("watchfiles is not installed")

        async def main() -> None:
            while True:
                async with sdk.Context() as ctx:
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

        asyncio.run(main())
    else:
        sdk.run(
            setup,
            *connect_options,
            trap_signals=True,
        )


class _Watcher:
    def __init__(
        self,
        ctx: sdk.Context,
        *path: str,
    ) -> None:

        self.ctx = ctx
        self.path = path
        for p in self.path:
            if not Path(p).is_dir():
                raise ValueError(f"Path {p} is not a directory")
        self.iterator = watchfiles.awatch(*self.path)  # type: ignore

    async def _next_change(self) -> set[tuple[watchfiles.Change, str]]:
        return await self.iterator.__anext__()

    async def next_change(
        self,
    ) -> set[tuple[watchfiles.Change, str]] | None:
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


def _import(path: str) -> Callable[[sdk.Context], Coroutine[None, None, None]]:
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
