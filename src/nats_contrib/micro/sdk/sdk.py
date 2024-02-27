from __future__ import annotations

import asyncio
import contextlib
import datetime
import signal
from typing import Any, AsyncContextManager, Awaitable, Callable, Coroutine, TypeVar

from nats.aio.client import Client as NATS
from nats_contrib.connect_opts import ConnectOption, connect

from ..api import Service, add_service
from .decorators import register_service

T = TypeVar("T")
E = TypeVar("E")


class Context:
    """A class to run micro services easily.

    This class is useful in a main function to manage ensure
    that all async resources are cleaned up properly when the
    program is cancelled.

    It also allows to listen to signals and cancel the program
    when a signal is received easily.
    """

    def __init__(self, client: NATS | None = None):
        self.exit_stack = contextlib.AsyncExitStack()
        self.cancel_event = asyncio.Event()
        self.client = client or NATS()
        self.services: list[Service] = []

    async def connect(self, *options: ConnectOption) -> None:
        """Connect to the NATS server. Does not raise an error when cancelled"""
        await self.wait_for(connect(client=self.client, *options))
        if not self.cancelled():
            await self.enter(self.client)

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
        id_generator: Callable[[], str] | None = None,
        api_prefix: str | None = None,
    ) -> Service:
        """Add a service to the context.

        This will start the service using the client used
        to connect to the NATS server.
        """
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
            id_generator,
            api_prefix,
        )
        await self.enter(service)
        self.services.append(service)
        return service

    async def register_service(
        self,
        service: Any,
        prefix: str | None = None,
        now: Callable[[], datetime.datetime] | None = None,
        id_generator: Callable[[], str] | None = None,
        api_prefix: str | None = None,
    ) -> Service:
        """Register a service in the context.

        This will start the service using the client used
        to connect to the NATS server.
        """
        service = register_service(
            self.client,
            service,
            prefix,
            now,
            id_generator,
            api_prefix,
        )
        await self.enter(service)
        self.services.append(service)
        return service

    def reset(self) -> None:
        """Reset all the services."""
        for service in self.services:
            service.reset()

    def cancel(self) -> None:
        """Set the cancel event."""
        self.cancel_event.set()

    def cancelled(self) -> bool:
        """Check if the context was cancelled."""
        return self.cancel_event.is_set()

    def add_disconnected_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Add a disconnected callback to the NATS client."""
        existing = self.client._disconnected_cb  # pyright: ignore[reportPrivateUsage]
        self.client._disconnected_cb = _chain0(  # pyright: ignore[reportPrivateUsage]
            existing, callback
        )

    def add_closed_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Add a closed callback to the NATS client."""
        existing = self.client._closed_cb  # pyright: ignore[reportPrivateUsage]
        self.client._closed_cb = _chain0(  # pyright: ignore[reportPrivateUsage]
            existing, callback
        )

    def add_reconnected_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Add a reconnected callback to the NATS client."""
        existing = self.client._reconnected_cb  # pyright: ignore[reportPrivateUsage]
        self.client._reconnected_cb = _chain0(  # pyright: ignore[reportPrivateUsage]
            existing, callback
        )

    def add_error_callback(
        self, callback: Callable[[Exception], Awaitable[None]]
    ) -> None:
        """Add an error callback to the NATS client."""
        existing = self.client._error_cb  # pyright: ignore[reportPrivateUsage]
        self.client._error_cb = _chain1(  # pyright: ignore[reportPrivateUsage]
            existing, callback
        )

    def trap_signal(self, *signals: signal.Signals) -> None:
        """Notify the context that a signal has been received."""
        if not signals:
            signals = (signal.Signals.SIGINT, signal.Signals.SIGTERM)
        loop = asyncio.get_event_loop()
        for sig in signals:
            loop.add_signal_handler(sig, self.cancel)

    async def enter(self, async_context: AsyncContextManager[T]) -> T:
        """Enter an async context."""
        return await self.exit_stack.enter_async_context(async_context)

    async def wait(self) -> None:
        """Wait for the cancel event to be set."""
        await self.cancel_event.wait()

    async def wait_for(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Run a coroutine in the context and cancel it context is cancelled.

        This method does not raise an exception if the coroutine is cancelled.
        You can use .cancelled() on the context to check if the coroutine was
        cancelled.
        """
        await _run_until_first_complete(coro, self.wait())

    async def __aenter__(self) -> "Context":
        await self.exit_stack.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        try:
            await self.exit_stack.__aexit__(None, None, None)
        finally:
            self.services.clear()

    async def run_forever(
        self,
        setup: Callable[[Context], Coroutine[Any, Any, None]],
        *options: ConnectOption,
        trap_signals: bool | tuple[signal.Signals, ...] = False,
    ) -> None:
        """Useful in a main function of a program.

        This method will first connect to the NATS server using the provided
        options. It will then run the setup function and finally enter any
        additional services provided.

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
            setup: A coroutine to setup the program.
            options: The options to pass to the connect method.
            trap_signals: If True, trap SIGINT and SIGTERM signals.
        """
        async with self as ctx:
            if trap_signals:
                if trap_signals is True:
                    trap_signals = (signal.Signals.SIGINT, signal.Signals.SIGTERM)
                ctx.trap_signal(*trap_signals)
            await ctx.wait_for(connect(client=ctx.client, *options))
            if ctx.cancelled():
                return
            await ctx.wait_for(setup(ctx))
            if ctx.cancelled():
                return
            await ctx.wait()


def _chain0(
    existing: Callable[[], Awaitable[None]] | None, new: Callable[[], Awaitable[None]]
) -> Callable[[], Awaitable[None]]:
    """Chain two coroutines."""
    if existing is None:
        return new

    async def chained() -> None:
        try:
            await new()
        finally:
            await existing()

    return chained


def _chain1(
    existing: Callable[[T], Awaitable[None]] | None, new: Callable[[T], Awaitable[None]]
) -> Callable[[T], Awaitable[None]]:
    """Chain two coroutines."""
    if existing is None:
        return new

    async def chained(arg: T) -> None:
        try:
            await new(arg)
        finally:
            await existing(arg)

    return chained


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
    setup: Callable[[Context], Coroutine[Any, Any, None]],
    *options: ConnectOption,
    trap_signals: bool | tuple[signal.Signals, ...] = False,
    client: NATS | None = None,
) -> None:
    """Helper function to run an async program."""

    asyncio.run(
        Context(client=client).run_forever(
            setup,
            *options,
            trap_signals=trap_signals,
        )
    )
