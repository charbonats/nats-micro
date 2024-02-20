from __future__ import annotations

import asyncio
from typing import Any, AsyncContextManager, AsyncIterator, Callable, Generic, TypeVar

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription
from nats.errors import BadSubscriptionError

T = TypeVar("T")
R = TypeVar("R")


class RequestManyIterator:

    def __init__(
        self,
        nc: Client,
        subject: str,
        payload: bytes,
        inbox: str,
        headers: dict[str, str] = {},
        max_wait: float | None = None,
        max_interval: float | None = None,
        max_count: int | None = None,
        stop_on_sentinel: bool = False,
    ) -> None:
        if max_wait is None and max_interval is None:
            max_wait = 0.5
        # Save all the arguments as instance variables.
        self.nc = nc
        self.subject = subject
        self.payload = payload
        self.headers = headers
        self.inbox = inbox
        self.max_wait = max_wait
        self.max_count = max_count
        self.max_interval = max_interval
        self.stop_on_sentinel = stop_on_sentinel
        # Initialize the state of the request many iterator
        self._sub: Subscription | None = None
        self._iterator: AsyncIterator[Msg] | None = None
        self._did_unsubscribe = False
        self._total_received = 0
        self._last_received = asyncio.get_event_loop().time()
        self._tasks: list[asyncio.Task[object]] = []
        self._pending_task: asyncio.Task[Msg] | None = None

    def __aiter__(self) -> RequestManyIterator:
        return self

    async def __anext__(self) -> Msg:
        if not self._sub:
            raise RuntimeError(
                "RequestManyIterator must be used as an async context manager"
            )
        # Exit early if we've already unsubscribed
        if self._did_unsubscribe:
            raise StopAsyncIteration
        # Exit early if we received all the messages
        if self.max_count and self._total_received == self.max_count:
            if self._sub and not self._did_unsubscribe:
                self._did_unsubscribe = True
                await unsubscribe(self._sub)
            raise StopAsyncIteration
        # Create a task to wait for the next message
        task: asyncio.Task[Msg] = asyncio.create_task(self._iterator.__anext__())  # type: ignore
        self._pending_task = task
        # Wait for the next message or any of the other tasks to complete
        await asyncio.wait(
            [self._pending_task, *self._tasks],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if self._pending_task.cancelled():
            raise StopAsyncIteration
        if not self._pending_task.done():
            self._pending_task.cancel()
            raise StopAsyncIteration
        # if err := self._pending_task.exception():
        #     raise err
        # This will raise an exception if an error occurred within the task
        msg = self._pending_task.result()
        # Always increment the total received count
        self._total_received += 1
        # Check if this is a sentinel message
        if self.stop_on_sentinel and msg.subject == "sentinel":
            if self._sub and not self._did_unsubscribe:
                self._did_unsubscribe = True
                await unsubscribe(self._sub)
            # In which case, raise StopAsyncIteration and don't return the message
            raise StopAsyncIteration
        # Return the message
        return msg

    async def __aenter__(self) -> RequestManyIterator:
        # Start the subscription
        sub = await self.nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
            self.inbox,
            max_msgs=self.max_count or 0,
        )
        # Save the subscription and the iterator
        self._iterator = sub.messages
        self._sub = sub
        # Add a task to wait for the max_wait time if needed
        if self.max_wait:
            self._tasks.append(asyncio.create_task(asyncio.sleep(self.max_wait)))
        # Add a task to check the interval if needed
        if self.max_interval:
            interval = self.max_interval

            async def check_interval() -> None:
                while True:
                    await asyncio.sleep(interval)
                    if asyncio.get_event_loop().time() - self._last_received > interval:
                        if self._sub and not self._did_unsubscribe:
                            self._did_unsubscribe = True
                            await unsubscribe(self._sub)
                        return

            self._tasks.append(asyncio.create_task(check_interval()))

        # Publish the request
        await self.nc.publish(
            self.subject, self.payload, reply=self.inbox, headers=self.headers
        )
        # At this point the subscription is ready and all tasks are submitted
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        if self._sub and not self._did_unsubscribe:
            await unsubscribe(self._sub)


class TransformAsyncIterator(Generic[T, R]):
    def __init__(
        self,
        source: AsyncContextManager[AsyncIterator[T]],
        map: Callable[[T], R],
    ) -> None:
        self.factory = source
        self.iterator: AsyncIterator[T] | None = None
        self.transform = map

    def __aiter__(self) -> TransformAsyncIterator[T, R]:
        return self

    async def __anext__(self) -> R:
        if not self.iterator:
            raise RuntimeError(
                "TransformAsyncIterator must be used as an async context manager"
            )
        next_value = await self.iterator.__anext__()
        return self.transform(next_value)

    async def __aenter__(self) -> AsyncIterator[R]:
        self.iterator = await self.factory.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.factory.__aexit__(*args, **kwargs)


def request_many_iterator(
    nc: Client,
    subject: str,
    payload: bytes,
    headers: dict[str, str] = {},
    reply_inbox: str | None = None,
    max_wait: float | None = 1,
    max_count: int | None = None,
    max_interval: float | None = None,
    stop_on_sentinel: bool = False,
) -> AsyncContextManager[AsyncIterator[Msg]]:
    """Request many responses from the same subject.

    This function does not return an error when no responses are received.

    Responses are received until one of the following conditions is met:
    - max_wait seconds have passed.
    - max_count responses have been received.
    - max_interval seconds have passed between responses.
    - A sentinel message is received and stop_on_sentinel is True.

    Args:
        subject: The subject to send the request to.
        payload: The payload to send with the request.
        headers: The headers to send with the request.
        reply_inbox: The inbox to receive the responses in. A new inbox is created if None.
        max_wait: The maximum amount of time to wait for responses. 1 second by default.
        max_count: The maximum number of responses to accept. No limit by default.
        max_interval: The maximum amount of time between responses. No limit by default.
        stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
    """
    return RequestManyIterator(
        nc,
        subject,
        payload,
        inbox=reply_inbox or nc.new_inbox(),
        headers=headers,
        max_wait=max_wait,
        max_interval=max_interval,
        max_count=max_count,
        stop_on_sentinel=stop_on_sentinel,
    )


async def request_many(
    nc: Client,
    subject: str,
    payload: bytes,
    headers: dict[str, str] = {},
    reply_inbox: str | None = None,
    max_wait: float | None = None,
    max_count: int | None = None,
    max_interval: float | None = None,
    stop_on_sentinel: bool = False,
) -> list[Msg]:
    """Request many responses from the same subject.

    This function does not return an error when no responses are received.

    Responses are received until one of the following conditions is met:
    - max_wait seconds have passed.
    - max_count responses have been received.
    - max_interval seconds have passed between responses.
    - A sentinel message is received and stop_on_sentinel is True.

    Args:
        subject: The subject to send the request to.
        payload: The payload to send with the request.
        headers: The headers to send with the request.
        reply_inbox: The inbox to receive the responses in. A new inbox is created if None.
        max_wait: The maximum amount of time to wait for responses. 1 second by default.
        max_count: The maximum number of responses to accept. No limit by default.
        max_interval: The maximum amount of time between responses. No limit by default.
        stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
    """
    if max_wait is None and max_interval is None:
        max_wait = 0.5
    # Create an inbox for the responses if one wasn't provided.
    if reply_inbox is None:
        reply_inbox = nc.new_inbox()
    # Create an empty list to store the responses.
    responses: list[Msg] = []
    # Get the event loop
    loop = asyncio.get_event_loop()
    # Create an event to signal when the request is complete.
    event = asyncio.Event()
    # Create a marker to indicate that a message was received
    # and the interval has passed.
    last_received = loop.time()

    # Define a callback to handle the responses.
    async def callback(msg: Msg) -> None:
        # Update the last received time.
        nonlocal last_received
        last_received = loop.time()
        # If we're stopping on a sentinel message, check for it
        # and don't append the message to the list of responses.
        if stop_on_sentinel and msg.data == b"":
            event.set()
            return
        # In all other cases, append the message to the list of responses.
        responses.append(msg)
        # And check if we've received all the responses.
        if len(responses) == max_count:
            event.set()

    # Subscribe to the inbox.
    sub = await nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
        reply_inbox,
        cb=callback,
        max_msgs=max_count or 0,
    )
    # Initialize a list of tasks to wait for.
    tasks: list[asyncio.Task[object]] = []
    # Enter try/finally clause to ensure that the subscription is
    # unsubscribed from even if an error occurs.
    try:
        # Create task to wait for the stop event.
        tasks.append(asyncio.create_task(event.wait()))

        # Add a task to wait for the max_wait time if needed
        if max_wait:
            tasks.append(asyncio.create_task(asyncio.sleep(max_wait)))

        # Add a task to check the interval if needed
        if max_interval:

            async def check_interval() -> None:
                nonlocal last_received
                while True:
                    await asyncio.sleep(max_interval)
                    if loop.time() - last_received > max_interval:
                        event.set()
                        return

            tasks.append(asyncio.create_task(check_interval()))

        # At this point the subscription is ready and all tasks are submitted
        # Publish the request.
        await nc.publish(subject, payload, reply=reply_inbox, headers=headers)
        # Wait for the first task to complete.
        await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
    # Always cancel tasks and unsubscribe from the inbox.
    finally:
        # Cancel the remaining tasks as soon as first one completes.
        for task in tasks:
            if not task.done():
                task.cancel()
        # Unsubscribe from the inbox.
        await unsubscribe(sub)

    # Return the list of responses.
    return responses


async def unsubscribe(sub: Subscription) -> None:
    try:
        await sub.unsubscribe()
    except BadSubscriptionError:
        # It's possible that auto-unsubscribe has already been called.
        pass
