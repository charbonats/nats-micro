from __future__ import annotations

import asyncio
import contextlib
import datetime
import signal
from typing import Any, AsyncContextManager, Callable, Coroutine, Iterable, TypeVar, Union

from nats.aio.client import Client as NATS

from ..api import Service, add_service
from .decorators import mount

T = TypeVar("T")


class Context:
    """A class to run micro services easily.

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

    async def run_forever(
        self,
        connect: Callable[[Context], Coroutine[Any, Any, None]] | None = None,
        setup: Callable[[Context], Coroutine[Any, Any, None]] | None = None,
        services: Callable[[Context], object | Iterable[object]] | Iterable[object] | None = None,
        trap_signals: bool | tuple[signal.Signals, ...] = False,
        **connect_opts: Any,
    ) -> None:
        """Useful in a main function of a program.

        This method will first connect to the NATS server, either
        using the connect function or the connect_opts. Then it will
        run the setup function and finally enter any additional services
        provided.

        If trap_signals is True, it will trap SIGINT and SIGTERM signals
        and cancel the context when one of these signals is received.

        Other signals can be trapped by providing a tuple of signals to
        trap.

        This method will not raise an exception if the context is cancelled.

        You can use .cancelled() on the context to check if the coroutine was
        cancelled.

        Warning:
            The context must not have been used as an async context manager
            before calling this method.

        Args:
            connect: A coroutine to connect to the NATS server.
            setup: A coroutine to setup the program.
            services: A list of services to enter or a lambda function as service factory with the context as argument.
            If the lambda function is passed, it needs to return list of services.
            trap_signals: If True, trap SIGINT and SIGTERM signals.
            connect_opts: The options to pass to the connect method.
        """
        async with self as ctx:
            if trap_signals:
                if trap_signals is True:
                    trap_signals = (signal.Signals.SIGINT, signal.Signals.SIGTERM)
                ctx.trap_signal(*trap_signals)
            if connect is None:
                await ctx.wait_for(ctx.client.connect(**connect_opts))
            else:
                await ctx.wait_for(connect(ctx))
            if ctx.cancelled():
                return
            if setup:
                await ctx.wait_for(setup(ctx))
                if ctx.cancelled():
                    return
            if services:
                for service in self._resolve_services(ctx, services):
                    await ctx.enter(mount(ctx.client, service))
                    if ctx.cancelled():
                        return
            await ctx.wait()

    def _resolve_services(self, ctx: Context, services: Callable[[Context], object|Iterable[object]] | Iterable[object] | None) -> Iterable[object]:
        if services is None:
            return []

        svcs = services(ctx) if callable(services) else services

        if not isinstance(svcs, Iterable):
            svcs = [svcs]

        return svcs # type: ignore

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
    services: Callable[[Context], object | Iterable[object]] | Iterable[object] | None = None,
    trap_signals: bool | tuple[signal.Signals, ...] = False,
    **connect_opts: Any,
) -> None:
    """Helper function to run an async program."""

    asyncio.run(
        Context().run_forever(
            connect,
            setup,
            services,
            trap_signals,
            **connect_opts,
        )
    )
