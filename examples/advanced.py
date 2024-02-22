"""Minimal example of NATS micro usage."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from nats.aio.client import Client
from uvicorn import Config

from nats_contrib import micro
from nats_contrib.micro.utils import Context, run_until_first_complete

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("micro")


async def echo_handler(req: micro.Request) -> None:
    """Echo the request data back to the client."""

    logger.info("Echoing request data")
    await req.respond(req.data())


async def setup_service(
    ctx: Context,
    url: str,
    max_reconnect: int,
) -> None:
    """Connect to the NATS server and setup the service.

    Args:
        ctx: The context used to start/stop/cancel the service.
        url: The url of the NATS server.
        max_reconnect: The maximum number of reconnection attempts.
    """

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
            logger.info("connection to nats server closed")
        # Cancel the context
        ctx.cancel()

    # Define a reconnected_cb callback for nats
    async def on_reconnected() -> None:
        logger.warn("reconnected to nats server")
        service.reset()

    # Connect to the nats server
    logger.info("connecting to %s", url)
    await nc.connect(
        url,
        closed_cb=on_close,
        reconnected_cb=on_reconnected,
        max_reconnect_attempts=max_reconnect,
    )

    # Push the client.close() method into the stack to be called on exit
    await ctx.enter_context(nc)

    # Ensure that the service is closed on exit
    await ctx.enter_context(service)

    # Add a group to the service
    group = service.add_group("demo")
    # Add an endpoint to the group
    ep = await group.add_endpoint(
        name="echo",
        handler=echo_handler,
    )
    # Indicate that the service is ready to accept requests
    logger.info("service %s listenning on '%s'", service.info().name, ep.info.subject)


async def setup_http_server(ctx: Context) -> None:
    # FastAPI Uvicorn override
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    class Server(uvicorn.Server):
        """A custom Uvicorn server that can be used as an async context manager."""

        def __init__(self, config: Config) -> None:
            super().__init__(config)
            # Track the asyncio task used to run the server
            self.task: asyncio.Task[None] | None = None

        # Override because we're catching signals ourselves
        def install_signal_handlers(self) -> None:
            pass

        async def __aenter__(self) -> "Server":
            self.task = asyncio.create_task(self.serve())
            return self

        async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
            self.should_exit = True
            if self.task:
                await self.task

    # Create a new starlette app
    app = Starlette()

    # Create a dummy route
    @app.route("/")
    async def index(request: Request) -> Response:
        return JSONResponse({"message": "Hello, World!"})

    # Create a new server
    server = Server(config=uvicorn.Config(app=app, loop="asyncio"))
    # Run the server
    await ctx.enter_context(server)


async def main(
    url: str = "nats://localhost:4222",
    max_reconnect: int = 1,
):
    """Run the main event loop."""
    # Create a new context
    async with Context() as ctx:
        # Trap the SIGINT and SIGTERM signals
        ctx.trap_signal(signal.Signals.SIGINT, signal.Signals.SIGTERM)
        # Setup the service
        await run_until_first_complete(
            setup_service(ctx, url, max_reconnect),
            ctx.wait(),
        )
        # Setup the http server
        await setup_http_server(ctx)
        # Wait for the context to be cancelled
        await ctx.wait()


if __name__ == "__main__":
    # Run the main event loop
    asyncio.run(main(url="nats://localhost:4222"))
