from __future__ import annotations

import asyncio
import contextlib
import datetime
import signal
from typing import Any, AsyncContextManager, Callable, Coroutine, Iterable, TypeVar

from nats.aio.client import Client as NATS

from ..api import Service, add_service
from .decorators import mount

T = TypeVar("T")


class Context:
    """A class to manage async resources.

    This class is useful in a main function to manage ensure
    that all async resources are cleaned up properly when the
    program is cancelled.

    It also allows to listen to signals and cancel the program
    when a signal is received easily.
    """

    def __init__(self):
        self.exit_stack = contextlib.AsyncExitStack()
        self.cancel_event = asyncio.Event()
        self.client = NATS()

    async def connect(self, *args: Any, **kwargs: Any) -> None:
        """Connect to the NATS server. Does not raise an error when cancelled"""
        await self.wait_for(self.client.connect(*args, **kwargs))

    async def add_service(
        self,
        name: str,
        version: str,
        description: str | None = None,
        metadata: dict[str, str] | None = None,
        queue_group: str | None = None,
        pending_bytes_limit_by_endpoint: int | None = None,
        pending_msgs_limit_by_endpoint: int | None = None,
        now: Callable[[], datetime.datetime] | None = None,
        generate_id: Callable[[], str] | None = None,
        api_prefix: str | None = None,
    ) -> Service:
        """Add a service to the context."""
        service = add_service(
            self.client,
            name,
            version,
            description,
            metadata,
            queue_group,
            pending_bytes_limit_by_endpoint,
            pending_msgs_limit_by_endpoint,
            now,
            generate_id,
            api_prefix,
        )
        await self.enter(service)
        return service

    def cancel(self) -> None:
        """Set the cancel event."""
        self.cancel_event.set()

    def cancelled(self) -> bool:
        """Check if the context was cancelled."""
        return self.cancel_event.is_set()

    def trap_signal(self, *signals: signal.Signals) -> None:
        """Notify the context that a signal has been received."""
        loop = asyncio.get_event_loop()
        for sig in signals:
            loop.add_signal_handler(sig, self.cancel)

    async def enter(self, async_context: AsyncContextManager[T]) -> T:
        """Enter an async context."""
        return await self.exit_stack.enter_async_context(async_context)

    async def wait(self) -> None:
        """Wait for the cancel event to be set."""
        await self.cancel_event.wait()

    async def wait_for(self, coro: Coroutine[Any, Any, None]) -> None:
        """Run a coroutine in the context and cancel it context is cancelled.

        This method does not raise an exception if the coroutine is cancelled.
        You can use .cancelled() on the context to check if the coroutine was
        cancelled.
        """
        await _run_until_first_complete(coro, self.wait())

    async def __aenter__(self) -> "Context":
        await self.exit_stack.__aenter__()
        await self.exit_stack.enter_async_context(self.client)
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.exit_stack.__aexit__(None, None, None)


async def _run_until_first_complete(
    *coros: Coroutine[Any, Any, Any],
) -> None:
    """Run a bunch of coroutines and stop as soon as the first stops."""
    tasks: list[asyncio.Task[Any]] = [asyncio.create_task(coro) for coro in coros]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
    # Make sure all tasks are cancelled AND finished
    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    # Check for exceptions
    for task in tasks:
        if task.cancelled():
            continue
        if err := task.exception():
            raise err


def run(
    connect: Callable[[Context], Coroutine[Any, Any, None]] | None = None,
    setup: Callable[[Context], Coroutine[Any, Any, None]] | None = None,
    services: Iterable[object] | None = None,
    trap_signals: bool | tuple[signal.Signals, ...] = False,
    **connect_opts: Any,
) -> None:
    """Helper function to run an async program."""

    async def main() -> None:
        trap = trap_signals
        async with Context() as ctx:
            if trap:
                if trap is True:
                    trap = (signal.Signals.SIGINT, signal.Signals.SIGTERM)
                ctx.trap_signal(*trap)
            if connect is None:
                await _run_until_first_complete(
                    ctx.wait(), ctx.client.connect(**connect_opts)
                )
            else:
                await _run_until_first_complete(ctx.wait(), connect(ctx))
            if ctx.cancelled():
                return
            if setup:
                await ctx.wait_for(setup(ctx))
                if ctx.cancelled():
                    return
            if services:
                for service in services:
                    await ctx.enter(mount(ctx.client, service))
            await ctx.wait()

    asyncio.run(main())
