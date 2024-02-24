from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any, AsyncContextManager, Coroutine, TypeVar

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

    def cancel(self) -> None:
        """Set the cancel event."""
        self.cancel_event.set()

    def trap_signal(self, *signals: signal.Signals) -> None:
        """Notify the context that a signal has been received."""
        loop = asyncio.get_event_loop()
        for sig in signals:
            loop.add_signal_handler(sig, self.cancel)

    async def enter_context(self, async_context: AsyncContextManager[T]) -> T:
        """Enter an async context."""
        return await self.exit_stack.enter_async_context(async_context)

    async def wait(self) -> None:
        """Wait for the cancel event to be set."""
        await self.cancel_event.wait()

    async def __aenter__(self) -> "Context":
        await self.exit_stack.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.exit_stack.__aexit__(None, None, None)


async def run_until_first_complete(
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
