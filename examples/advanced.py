"""Minimal example of NATS micro usage."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nats_contrib.connect_opts import option

from nats_contrib import micro

LOG_CONFIG = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)-7s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "micro": {
            "level": "INFO",
            "handlers": [],
        },
        "uvicorn.error": {
            "level": "INFO",
            "handlers": [],
        },
        "uvicorn.access": {
            "level": "INFO",
            "handlers": [],
        },
        "uvicorn.asgi": {
            "level": "INFO",
            "handlers": [],
        },
    },
}

logger = logging.getLogger("micro")


async def echo_handler(req: micro.Request) -> None:
    """Echo the request data back to the client."""

    logger.info("Echoing request data")
    await req.respond(req.data())


class Watcher:
    """A class used to watch the connection to the NATS server."""

    def __init__(self, ctx: micro.sdk.Context) -> None:
        self.ctx = ctx

    async def on_disconnected(self) -> None:
        """Called when the connection to the NATS server is lost."""
        logger.warn("disconnected from nats server")

    async def on_close(self) -> None:
        """Called when the connection to the NATS server is closed."""
        if self.ctx.client.last_error:
            logger.error(
                "connection to nats server closed: %s", self.ctx.client.last_error
            )
        else:
            logger.info("connection to nats server closed")
        # Cancel the context
        self.ctx.cancel()

    async def on_reconnected(self) -> None:
        """Called when the connection to the NATS server is re-established."""
        logger.warn("reconnected to nats server")
        # Reset all services stats
        self.ctx.reset()

    def attach(self, ctx: micro.sdk.Context) -> None:
        """Attach the watcher to the context."""
        ctx.client._disconnected_cb = self.on_disconnected
        ctx.client._closed_cb = self.on_close
        ctx.client._reconnected_cb = self.on_reconnected


async def setup(
    ctx: micro.sdk.Context,
) -> None:
    """Connect to the NATS server and setup the service.

    Args:
        ctx: The context used to start/stop/cancel the service.
        url: The url of the NATS server.
        max_reconnect: The maximum number of reconnection attempts.
    """
    # Create and attach a new watcher
    watcher = Watcher(ctx)
    watcher.attach(ctx)
    # Create a new micro service
    service = await ctx.add_service(
        name="demo-service",
        version="1.0.0",
        description="Demo service",
    )
    # Add a group to the service
    group = service.add_group("demo")
    # Add an endpoint to the group
    ep = await group.add_endpoint(
        name="echo",
        subject="ECHO",
        handler=echo_handler,
    )
    # Start the HTTP server
    await setup_http_server(ctx)
    # Indicate that the service is ready to accept requests
    logger.info("service %s listenning on '%s'", service.info().name, ep.info.subject)


async def setup_http_server(ctx: micro.sdk.Context) -> None:
    # FastAPI Uvicorn override
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    class Server(uvicorn.Server):
        """A custom Uvicorn server that can be used as an async context manager."""

        def __init__(self, config: uvicorn.Config) -> None:
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
                await asyncio.wait([self.task])
                if self.task.cancelled():
                    return
                err = self.task.exception()
                if err:
                    raise err

    # Create a new starlette app
    app = Starlette()

    # Create a dummy route
    @app.route("/")
    async def index(request: Request) -> Response:
        return JSONResponse({"message": "Hello, World!"})

    # Create a new server
    server = Server(
        config=uvicorn.Config(
            app=app,
            loop="asyncio",
            access_log=True,
            log_config=LOG_CONFIG,
        )
    )
    # Run the server
    await ctx.enter(server)


if __name__ == "__main__":
    # Run the main event loop
    micro.sdk.run(
        setup,
        option.WithServer(url="nats://localhost:4222"),
        option.WithAllowReconnect(max_attempts=2),
    )
