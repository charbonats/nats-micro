"""Minimal example of NATS micro usage."""

import asyncio
import contextlib
import logging
import signal

from nats.aio.client import Client

import micro

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("micro")


async def echo(req: micro.Request) -> None:
    """Echo the request data back to the client."""
    logger.info("Echoing request data")
    await req.respond(req.data())


async def setup(service: micro.Service) -> None:
    """Set up a micro service."""
    # Add a group to the service
    group = service.add_group("demo")
    # Add an endpoint to the group
    ep = await group.add_endpoint(
        name="echo",
        handler=echo,
    )
    # Indicate that the service is ready to accept requests
    logger.info("service %s listenning on '%s'", service.info().name, ep.info.subject)


async def main(
    url: str = "nats://localhost:4222",
):
    """Boilerplate for running the micro service as a long-running process."""
    # Define an event to signal when to quit
    quit_event = asyncio.Event()

    # Create a new nats client
    nc = Client()

    # Create a new micro service
    service = micro.add_service(
        nc,
        name="demo-service",
        version="1.0.0",
        description="Demo service",
    )

    # Define a closed_cb callback for nats
    async def on_close() -> None:
        if nc.last_error:
            logger.error("connection to nats server closed: %s", nc.last_error)
        else:
            logger.warning("connection to nats server closed")
        if not quit_event.is_set():
            quit_event.set()

    # Define a reconnected_cb callback for nats
    async def on_reconnected() -> None:
        logger.warn("reconnected to nats server")
        service.reset()

    # Attach signal handler to the event loop
    loop = asyncio.get_event_loop()
    for sig in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
        loop.add_signal_handler(sig, lambda *_: quit_event.set())

    # Enter an async exit stack
    async with contextlib.AsyncExitStack() as stack:
        # Kick off the connection to the NATS server
        cancel_task = asyncio.create_task(quit_event.wait())
        connect_task = asyncio.create_task(
            nc.connect(
                url,
                closed_cb=on_close,
                reconnected_cb=on_reconnected,
                max_reconnect_attempts=1,
            )
        )
        # Wait for either the connection to be established or the quit event to be set
        logger.info("connecting to %s", url)
        await asyncio.wait(
            [connect_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
        )
        # Exit early if the quit event is set before the connection is established
        if cancel_task.done():
            connect_task.cancel()
            return
        # Ensure connect_task succeeded
        if err := connect_task.exception():
            raise err
        # Push the client.close() method into the stack to be called on exit
        stack.push_async_callback(nc.close)

        # Setup the micro service
        setup_task = asyncio.create_task(setup(service))
        logger.info("setting up service: %s", service.info().name)
        await asyncio.wait(
            [setup_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
        )
        # Exit early if the quit event is set before the connection is established
        if cancel_task.done():
            setup_task.cancel()
            return
        # Ensure setup_task succeeded
        if err := setup_task.exception():
            raise err

        # Wait for the quit event
        await cancel_task
        # Log that the service is shutting down
        logger.warning("shutting down")


if __name__ == "__main__":
    asyncio.run(main(url="nats://localhost:4222"))
